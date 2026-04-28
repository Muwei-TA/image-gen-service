import { useCallback, useEffect, useMemo, useState } from 'react';
import { ImageCard } from './components/ImageCard';
import { Sidebar } from './components/Sidebar';
import { cancelJob, deleteUpload, getBatch, getBatches, getHealth, getUploads, submitBatch, uploadImage } from './lib/api';
import type { Batch, HealthStatus } from './lib/api';
import { generatedToAsset, uploadToAsset, type AssetItem } from './lib/assets';

const DEFAULT_WORKDIR = import.meta.env.VITE_IMAGE_GEN_DEFAULT_WORKDIR || undefined;

export default function App() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [selectedAssetIds, setSelectedAssetIds] = useState<Set<string>>(new Set());
  const [activeBatchIds, setActiveBatchIds] = useState<Set<string>>(new Set());
  const [isUploading, setIsUploading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [prompt, setPrompt] = useState('');
  const [hiddenFailedJobIds, setHiddenFailedJobIds] = useState<Set<string>>(() => {
    try {
      return new Set(JSON.parse(window.localStorage.getItem('image-gen-hidden-failed-jobs') || '[]'));
    } catch {
      return new Set();
    }
  });

  const loadWorkspace = useCallback(async () => {
    setError('');
    try {
      const serviceHealth = await getHealth();
      setHealth(serviceHealth);
      const [{ uploads }, { batches: savedBatches }] = await Promise.all([getUploads(), getBatches()]);
      setAssets((current) => mergeAssets(current, uploads.map(uploadToAsset)));
      const orderedBatches = [...savedBatches].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
      const detailedBatches = await Promise.all(orderedBatches.slice(0, 30).map((batch) => getBatch(batch.batch_id)));
      setBatches(detailedBatches);
        setActiveBatchIds(
          new Set(
            detailedBatches
              .filter((batch) => batch.status === 'queued' || batch.status === 'running')
              .map((batch) => batch.batch_id),
          ),
        );
    } catch (err) {
      const message = err instanceof Error ? err.message : '工作区读取失败';
      setError(message);
    }
  }, []);

  useEffect(() => {
    loadWorkspace();
  }, [loadWorkspace]);

  useEffect(() => {
    if (activeBatchIds.size === 0) return;
    const timer = window.setInterval(async () => {
      try {
        const updates = await Promise.all(Array.from(activeBatchIds).map((batchId) => getBatch(batchId)));
        setBatches((current) => current.map((batch) => updates.find((item) => item.batch_id === batch.batch_id) || batch));
        setActiveBatchIds((current) => {
          const next = new Set(current);
          updates.forEach((batch) => {
            if (batch.status === 'completed' || batch.status === 'finished_with_errors') next.delete(batch.batch_id);
          });
          return next;
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : '队列状态刷新失败');
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [activeBatchIds]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      getHealth()
        .then(setHealth)
        .catch(() => undefined);
    }, 10000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const generated = batches
      .flatMap((batch) => batch.jobs || [])
      .flatMap((job) => job.result_paths || [])
      .map(generatedToAsset);
    if (generated.length) {
      setAssets((current) => mergeAssets(current, generated));
    }
  }, [batches]);

  useEffect(() => {
    const failedJobs = batches.flatMap((batch) => batch.jobs || []).filter((job) => job.status === 'failed');
    const freshFailures = failedJobs.filter((job) => !hiddenFailedJobIds.has(job.job_id));
    if (!freshFailures.length) return;
    const first = freshFailures[0];
    const next = new Set(hiddenFailedJobIds);
    freshFailures.forEach((job) => next.add(job.job_id));
    setHiddenFailedJobIds(next);
    window.localStorage.setItem('image-gen-hidden-failed-jobs', JSON.stringify(Array.from(next).slice(-500)));
    setError(`任务生成失败：${first.error || '没有检测到输出图片'}`);
  }, [batches, hiddenFailedJobIds]);

  const allJobs = useMemo(() => {
    return batches
      .flatMap((batch) => batch.jobs || [])
      .filter((job) => job.status !== 'failed' || !hiddenFailedJobIds.has(job.job_id))
      .slice(0, 80);
  }, [batches, hiddenFailedJobIds]);
  const runningCount = useMemo(() => allJobs.filter((job) => job.status === 'queued' || job.status === 'running').length, [allJobs]);

  const selectedAssets = useMemo(
    () => assets.filter((asset) => selectedAssetIds.has(asset.id)),
    [assets, selectedAssetIds],
  );

  const handleGenerate = useCallback(
    async (prompt: string, count: number, ratio: string) => {
      setError('');
      if (health?.codex && (!health.codex.available || !health.codex.authenticated)) {
        setError('Codex 未登录或不可用，请先在容器内完成 Codex 登录。');
        return;
      }
      setIsSubmitting(true);
      const promptWithRatio = `${prompt.trim()} --ar ${ratio}`;
      const referenceImageIds = selectedAssets.flatMap((asset) => (asset.imageId ? [asset.imageId] : []));
      const referenceImages = selectedAssets.filter((asset) => !asset.imageId).map((asset) => asset.path);
      try {
        const batch = await submitBatch({
          prompt: promptWithRatio,
          count,
          workdir: DEFAULT_WORKDIR,
          reference_image_ids: referenceImageIds,
          reference_images: referenceImages,
        });
        setBatches((current) => [batch, ...current]);
        setActiveBatchIds((current) => new Set(current).add(batch.batch_id));
      } catch (err) {
        setError(err instanceof Error ? err.message : '提交失败');
      } finally {
        setIsSubmitting(false);
      }
    },
    [health, selectedAssets],
  );

  const handleUploadFiles = useCallback(
    async (files: File[]) => {
      const existingSignatures = new Set(assets.map((asset) => asset.signature).filter(Boolean));
      const uniqueFiles = files.filter((file) => !existingSignatures.has(`${file.name}:${file.size}`));
      if (!uniqueFiles.length) return;
      setIsUploading(true);
      setError('');
      try {
        const uploads = await Promise.all(uniqueFiles.map((file) => uploadImage(file)));
        const newAssets = uploads.map(uploadToAsset);
        setAssets((current) => mergeAssets(current, newAssets));
        setSelectedAssetIds((current) => {
          const next = new Set(current);
          newAssets.forEach((asset) => next.add(asset.id));
          return next;
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : '上传失败');
      } finally {
        setIsUploading(false);
      }
    },
    [assets],
  );

  const handleToggleAsset = useCallback((assetId: string) => {
    setSelectedAssetIds((current) => {
      const next = new Set(current);
      if (next.has(assetId)) next.delete(assetId);
      else next.add(assetId);
      return next;
    });
  }, []);

  const handleUseAsReference = useCallback((path: string) => {
    const asset = generatedToAsset(path);
    setAssets((current) => mergeAssets(current, [asset]));
    setSelectedAssetIds((current) => new Set(current).add(asset.id));
  }, []);

  const handleReusePrompt = useCallback((nextPrompt: string) => {
    setPrompt(nextPrompt);
  }, []);

  const handleCancelJob = useCallback(async (jobId: string) => {
    setError('');
    try {
      const updatedJob = await cancelJob(jobId);
      setBatches((current) =>
        current.map((batch) => {
          if (batch.batch_id !== updatedJob.batch_id) return batch;
          return {
            ...batch,
            jobs: (batch.jobs || []).map((job) => (job.job_id === updatedJob.job_id ? updatedJob : job)),
          };
        }),
      );
      setActiveBatchIds((current) => {
        const next = new Set(current);
        const batch = batches.find((item) => item.batch_id === updatedJob.batch_id);
        const jobs = (batch?.jobs || []).map((job) => (job.job_id === updatedJob.job_id ? updatedJob : job));
        if (!jobs.some((job) => job.status === 'queued' || job.status === 'running')) next.delete(updatedJob.batch_id);
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '取消任务失败');
    }
  }, [batches]);

  const handleDeleteAsset = useCallback(async (assetId: string) => {
    const asset = assets.find((item) => item.id === assetId);
    if (!asset || !asset.imageId) return;
    setError('');
    try {
      await deleteUpload(asset.imageId);
      setAssets((current) => current.filter((item) => item.id !== assetId));
      setSelectedAssetIds((current) => {
        const next = new Set(current);
        next.delete(assetId);
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '删除素材失败');
    }
  }, [assets]);

  return (
    <div className="flex h-screen overflow-hidden bg-[#0b1120] text-slate-100">
      <Sidebar
        assets={assets}
        selectedAssetIds={selectedAssetIds}
        prompt={prompt}
        onPromptChange={setPrompt}
        onGenerate={handleGenerate}
        onToggleAsset={handleToggleAsset}
        onUploadFiles={handleUploadFiles}
        onDeleteAsset={handleDeleteAsset}
        onClearSelection={() => setSelectedAssetIds(new Set())}
        isGenerating={activeBatchIds.size > 0}
        isSubmitting={isSubmitting}
        isUploading={isUploading}
      />

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[1500px] px-7 py-6">
          <header className="mb-6 flex flex-col gap-4 border-b border-slate-800 pb-5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-cyan-300/80">Batch Queue</p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight text-white">生图任务工作台</h2>
              <p className="mt-2 text-sm text-slate-400">提交后每张图会进入独立任务卡，完成前保留所选比例的等待画面。</p>
            </div>
            <div className="grid grid-cols-3 gap-3 text-right">
          <Metric label="队列中" value={runningCount} />
              <Metric label="素材" value={assets.length} />
              <Metric label="参考" value={selectedAssetIds.size} />
            </div>
          </header>

          {health?.codex && (!health.codex.available || !health.codex.authenticated) && (
            <div className="mb-5 rounded-lg border border-amber-400/30 bg-amber-950/25 px-4 py-3 text-sm text-amber-100">
              Codex {health.codex.available ? '尚未登录' : '不可用'}。生图前请在容器内执行：
              <code className="ml-2 rounded bg-black/35 px-2 py-1 text-amber-50">codex</code>
            </div>
          )}

          {error && (
            <div className="mb-5 rounded-lg border border-red-500/30 bg-red-950/30 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}

          {allJobs.length === 0 ? (
            <div className="flex min-h-[520px] items-center justify-center rounded-lg border border-dashed border-slate-800 bg-slate-950/30">
              <div className="max-w-sm text-center">
                <div className="mx-auto mb-5 h-24 w-40 rounded-md border border-cyan-300/40 bg-[radial-gradient(circle_at_50%_0%,rgba(34,211,238,0.2),transparent_46%),linear-gradient(135deg,#111827,#020617)]" />
                <h3 className="text-lg font-medium text-white">还没有排队任务</h3>
                <p className="mt-2 text-sm leading-6 text-slate-500">输入提示词、选择比例和数量，也可以先上传或选择参考图。</p>
              </div>
            </div>
          ) : (
            <div className="grid auto-rows-[minmax(180px,auto)] grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              {allJobs.map((job) => (
                <ImageCard
                  key={job.job_id}
                  job={job}
                  onUseAsReference={handleUseAsReference}
                  onCancel={handleCancelJob}
                  onReusePrompt={handleReusePrompt}
                />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-24 rounded-lg border border-slate-800 bg-slate-950/40 px-4 py-3">
      <div className="text-xl font-semibold text-white">{value}</div>
      <div className="mt-1 text-xs text-slate-500">{label}</div>
    </div>
  );
}

function mergeAssets(current: AssetItem[], incoming: AssetItem[]): AssetItem[] {
  const seen = new Set(current.map((asset) => asset.id));
  const next = [...current];
  incoming.forEach((asset) => {
    if (!seen.has(asset.id)) {
      seen.add(asset.id);
      next.unshift(asset);
    }
  });
  return next.slice(0, 300);
}
