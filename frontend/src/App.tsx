import { useCallback, useEffect, useMemo, useState } from 'react';
import { Header } from './components/Header';
import { ImageCard } from './components/ImageCard';
import { Sidebar } from './components/Sidebar';
import { cancelJob, deleteUpload, fileUrl, getBatch, getBatches, getHealth, getUploads, submitBatch, uploadImage } from './lib/api';
import type { Batch, HealthStatus } from './lib/api';
import { generatedToAsset, uploadToAsset, type AssetItem } from './lib/assets';

const DEFAULT_WORKDIR = import.meta.env.VITE_IMAGE_GEN_DEFAULT_WORKDIR || undefined;

type PreviewImage = {
  path: string;
  src: string;
  prompt: string;
};

export default function App() {
  const [isDarkMode, setIsDarkMode] = useState(() => {
    const saved = window.localStorage.getItem('image-gen-theme');
    if (saved) return saved === 'dark';
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
  });
  const [batches, setBatches] = useState<Batch[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [selectedAssetIds, setSelectedAssetIds] = useState<Set<string>>(new Set());
  const [activeBatchIds, setActiveBatchIds] = useState<Set<string>>(new Set());
  const [isUploading, setIsUploading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [prompt, setPrompt] = useState('');
  const [previewImage, setPreviewImage] = useState<PreviewImage | null>(null);
  const [hiddenFailedJobIds, setHiddenFailedJobIds] = useState<Set<string>>(() => {
    try {
      return new Set(JSON.parse(window.localStorage.getItem('image-gen-hidden-failed-jobs') || '[]'));
    } catch {
      return new Set();
    }
  });

  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDarkMode);
    window.localStorage.setItem('image-gen-theme', isDarkMode ? 'dark' : 'light');
  }, [isDarkMode]);

  useEffect(() => {
    let active = true;
    async function loadWorkspace() {
      try {
        const serviceHealth = await getHealth();
        const [{ uploads }, { batches: savedBatches }] = await Promise.all([getUploads(), getBatches()]);
        const orderedBatches = [...savedBatches].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
        const detailedBatches = await Promise.all(orderedBatches.slice(0, 30).map((batch) => getBatch(batch.batch_id)));
        if (!active) return;
        setError('');
        setHealth(serviceHealth);
        setAssets((current) => mergeAssets(current, uploads.map(uploadToAsset)));
        setBatches(detailedBatches);
        setActiveBatchIds(
          new Set(
            detailedBatches
              .filter(isBatchActive)
              .map((batch) => batch.batch_id),
          ),
        );
      } catch (err) {
        if (!active) return;
        const message = err instanceof Error ? err.message : '工作区读取失败';
        setError(message);
      }
    }
    void loadWorkspace();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (activeBatchIds.size === 0) return;
    const timer = window.setInterval(async () => {
      try {
        const updates = await Promise.all(Array.from(activeBatchIds).map((batchId) => getBatch(batchId)));
        setBatches((current) => current.map((batch) => updates.find((item) => item.batch_id === batch.batch_id) || batch));
        setActiveBatchIds((current) => {
          const next = new Set(current);
          updates.forEach((batch) => {
            if (!isBatchActive(batch)) next.delete(batch.batch_id);
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
    if (!previewImage) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setPreviewImage(null);
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [previewImage]);

  const generatedAssets = useMemo(() => {
    return batches
      .flatMap((batch) => batch.jobs || [])
      .flatMap((job) => job.result_paths || [])
      .map(generatedToAsset);
  }, [batches]);

  const visibleAssets = useMemo(() => mergeAssets(assets, generatedAssets), [assets, generatedAssets]);

  useEffect(() => {
    const failedJobs = batches.flatMap((batch) => batch.jobs || []).filter((job) => job.status === 'failed');
    const freshFailures = failedJobs.filter((job) => !hiddenFailedJobIds.has(job.job_id));
    if (!freshFailures.length) return;
    const timer = window.setTimeout(() => {
      const first = freshFailures[0];
      const next = new Set(hiddenFailedJobIds);
      freshFailures.forEach((job) => next.add(job.job_id));
      setHiddenFailedJobIds(next);
      window.localStorage.setItem('image-gen-hidden-failed-jobs', JSON.stringify(Array.from(next).slice(-500)));
      setError(`任务生成失败：${first.error || '没有检测到输出图片'}`);
    });
    return () => window.clearTimeout(timer);
  }, [batches, hiddenFailedJobIds]);

  const allJobs = useMemo(() => {
    return batches
      .flatMap((batch) => batch.jobs || [])
      .filter((job) => job.status !== 'failed' || !hiddenFailedJobIds.has(job.job_id))
      .slice(0, 80);
  }, [batches, hiddenFailedJobIds]);
  const runningCount = useMemo(() => allJobs.filter((job) => job.status === 'queued' || job.status === 'running').length, [allJobs]);
  const completedCount = useMemo(() => allJobs.filter((job) => job.status === 'succeeded').length, [allJobs]);
  const failedCount = useMemo(() => allJobs.filter((job) => job.status === 'failed').length, [allJobs]);
  const serviceReady = Boolean(health?.codex?.available && health.codex.authenticated);

  const selectedAssets = useMemo(
    () => visibleAssets.filter((asset) => selectedAssetIds.has(asset.id)),
    [visibleAssets, selectedAssetIds],
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
      const existingSignatures = new Set(visibleAssets.map((asset) => asset.signature).filter(Boolean));
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
    [visibleAssets],
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

  const handlePreviewImage = useCallback((path: string, nextPrompt: string) => {
    setPreviewImage({ path, src: fileUrl(path), prompt: nextPrompt });
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
    <div className="min-h-screen bg-background text-text transition-colors dark:bg-slate-950 dark:text-slate-100 lg:flex lg:h-screen lg:overflow-hidden">
      <Sidebar
        assets={visibleAssets}
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

      <main className="min-w-0 flex-1 overflow-y-auto">
        <Header
          runningCount={runningCount}
          assetCount={visibleAssets.length}
          selectedAssetCount={selectedAssetIds.size}
          isDarkMode={isDarkMode}
          onToggleTheme={() => setIsDarkMode((current) => !current)}
        />
        <div className="mx-auto max-w-[1540px] px-4 py-6 sm:px-6 lg:px-8">
          <section className="mb-6 rounded-[2rem] border border-white/80 bg-white/75 p-5 shadow-sm shadow-slate-200/70 backdrop-blur dark:border-slate-800 dark:bg-slate-900/75 dark:shadow-slate-950/30 sm:p-6">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cta">Image Generation Queue</p>
                <h2 className="mt-3 text-3xl font-semibold tracking-tight text-text dark:text-slate-100 sm:text-4xl">批量生图工作台</h2>
                <p className="mt-3 max-w-2xl text-sm leading-6 text-muted dark:text-slate-400">
                  输入提示词、选择参考图与图片比例，批量启动生成任务，并在同一工作区追踪队列、复用结果和下载图片。
                </p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-secondary dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                <span className="font-semibold text-text dark:text-slate-100">并发上限</span>
                <span className="ml-2 font-mono text-cta">{health?.codex?.max_concurrency ?? '—'}</span>
              </div>
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <KpiCard label="队列中" value={runningCount} helper="排队或生成中的 job" tone="blue" />
              <KpiCard label="已完成" value={completedCount} helper="可下载或加入参考图" tone="green" />
              <KpiCard label="参考图" value={selectedAssetIds.size} helper={`${visibleAssets.length} 个素材可用`} tone="violet" />
              <KpiCard
                label="服务状态"
                value={serviceReady ? 'Ready' : 'Check'}
                helper={serviceReady ? 'Codex 已登录，可生成' : failedCount ? `${failedCount} 个失败任务` : '等待登录或健康检查'}
                tone={serviceReady ? 'green' : 'amber'}
              />
            </div>
          </section>

          {health?.codex && (!health.codex.available || !health.codex.authenticated) && (
            <div className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 shadow-sm dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
              Codex {health.codex.available ? '尚未登录' : '不可用'}。生图前请在容器内执行：
              <code className="ml-2 rounded-lg bg-amber-100 px-2 py-1 text-amber-950">codex</code>
            </div>
          )}

          {error && (
            <div className="mb-5 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 shadow-sm dark:border-red-900 dark:bg-red-950/40 dark:text-red-100">
              {error}
            </div>
          )}

          {allJobs.length === 0 ? (
            <div className="flex min-h-[520px] items-center justify-center rounded-[2rem] border border-dashed border-slate-300 bg-white/80 p-6 shadow-sm shadow-slate-200/70 dark:border-slate-700 dark:bg-slate-900/80 dark:shadow-slate-950/30">
              <div className="max-w-xl text-center">
                <div className="mx-auto mb-6 grid h-32 max-w-md grid-cols-3 gap-3 rounded-3xl bg-slate-50 p-4 shadow-inner shadow-slate-200 dark:bg-slate-800 dark:shadow-slate-950">
                  <div className="rounded-2xl bg-gradient-to-br from-blue-100 to-white" />
                  <div className="rounded-2xl bg-gradient-to-br from-violet-100 to-white" />
                  <div className="rounded-2xl bg-gradient-to-br from-emerald-100 to-white" />
                </div>
                <h3 className="text-xl font-semibold tracking-tight text-text dark:text-slate-100">开始第一组批量生图任务</h3>
                <p className="mt-3 text-sm leading-6 text-muted dark:text-slate-400">
                  在左侧输入提示词，选择图片比例和生成数量；如需风格或构图参考，可先上传参考图再提交。
                </p>
                <div className="mt-6 grid gap-3 text-left text-sm text-secondary sm:grid-cols-3">
                  {['输入提示词', '选择比例与数量', '提交并追踪队列'].map((item, index) => (
                    <div key={item} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
                      <span className="mb-2 flex h-7 w-7 items-center justify-center rounded-full bg-blue-50 text-xs font-bold text-cta">{index + 1}</span>
                      {item}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="grid auto-rows-[minmax(180px,auto)] grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-4">
              {allJobs.map((job) => (
                <ImageCard
                  key={job.job_id}
                  job={job}
                  onUseAsReference={handleUseAsReference}
                  onCancel={handleCancelJob}
                  onReusePrompt={handleReusePrompt}
                  onPreview={handlePreviewImage}
                />
              ))}
            </div>
          )}
        </div>
      </main>

      {previewImage && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label="图片预览"
          onClick={() => setPreviewImage(null)}
        >
          <div className="flex max-h-[92vh] w-full max-w-6xl flex-col overflow-hidden rounded-[2rem] bg-white shadow-2xl shadow-slate-950/40 dark:bg-slate-900" onClick={(event) => event.stopPropagation()}>
            <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4 dark:border-slate-800">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-text dark:text-slate-100">图片预览</p>
                <p className="truncate text-xs text-muted dark:text-slate-400">{previewImage.path}</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <a
                  href={previewImage.src}
                  download
                  className="rounded-full bg-cta px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-ctaHover"
                >
                  下载图片
                </a>
                <button
                  type="button"
                  onClick={() => setPreviewImage(null)}
                  className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-white text-lg font-semibold text-slate-600 transition hover:bg-slate-50 hover:text-text dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:hover:bg-slate-700 cursor-pointer"
                  aria-label="关闭预览"
                >
                  ×
                </button>
              </div>
            </div>
            <div className="flex min-h-0 flex-1 items-center justify-center bg-slate-100 p-4 dark:bg-slate-950 sm:p-6">
              <img src={previewImage.src} alt={previewImage.prompt} className="max-h-[72vh] max-w-full rounded-2xl object-contain shadow-xl shadow-slate-300/70" />
            </div>
            <div className="border-t border-slate-200 px-5 py-4 dark:border-slate-800">
              <p className="line-clamp-2 text-sm leading-6 text-slate-700 dark:text-slate-300">{previewImage.prompt}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function KpiCard({ label, value, helper, tone }: { label: string; value: string | number; helper: string; tone: 'blue' | 'green' | 'violet' | 'amber' }) {
  const toneClass = {
    blue: 'bg-blue-50 text-blue-700 ring-blue-100',
    green: 'bg-emerald-50 text-emerald-700 ring-emerald-100',
    violet: 'bg-violet-50 text-violet-700 ring-violet-100',
    amber: 'bg-amber-50 text-amber-700 ring-amber-100',
  }[tone];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm shadow-slate-200/70 dark:border-slate-700 dark:bg-slate-800/80 dark:shadow-slate-950/30">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-[0.16em] text-muted dark:text-slate-400">{label}</p>
        <span className={`h-2.5 w-2.5 rounded-full ring-4 ${toneClass}`} />
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-tight text-text dark:text-slate-100">{value}</div>
      <p className="mt-1 text-xs text-muted dark:text-slate-400">{helper}</p>
    </div>
  );
}

function isBatchActive(batch: Batch): boolean {
  const jobs = batch.jobs || [];
  if (jobs.length) {
    return jobs.some((job) => job.status === 'queued' || job.status === 'running');
  }
  return batch.status === 'queued' || batch.status === 'running';
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
