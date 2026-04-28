import { DownloadSimple, FileZip, Plus, SpinnerGap, Stop, TextT, WarningCircle } from '@phosphor-icons/react';
import type { Job } from '../lib/api';
import { batchDownloadUrl, fileUrl } from '../lib/api';
import { cn } from '../lib/utils';

interface ImageCardProps {
  job: Job;
  onUseAsReference: (path: string) => void;
  onCancel: (jobId: string) => void;
  onReusePrompt: (prompt: string) => void;
}

const RATIO_CLASSES: Record<string, string> = {
  '1:1': 'aspect-square',
  '4:3': 'aspect-[4/3]',
  '16:9': 'aspect-video',
  '21:9': 'aspect-[21/9] md:col-span-2',
  '9:16': 'aspect-[9/16]',
};

export function ImageCard({ job, onUseAsReference, onCancel, onReusePrompt }: ImageCardProps) {
  const isPending = job.status === 'queued' || job.status === 'running';
  const isFailed = job.status === 'failed';
  const resultPath = job.result_paths?.[0];
  const ratio = parseRatio(job.prompt);
  const imageSrc = resultPath ? fileUrl(resultPath) : '';

  return (
    <article
      className={cn(
        'group relative overflow-hidden rounded-lg border bg-slate-950 transition duration-300',
        RATIO_CLASSES[ratio] || 'aspect-square',
        isPending
          ? 'border-slate-700 shadow-[inset_0_0_0_1px_rgba(148,163,184,0.08)]'
          : isFailed
            ? 'border-red-500/50 bg-red-950/20'
            : 'border-slate-800 hover:border-cyan-400/70',
      )}
    >
      {isPending && (
        <div className="absolute inset-0 overflow-hidden bg-[radial-gradient(circle_at_50%_0%,rgba(34,211,238,0.18),transparent_42%),linear-gradient(135deg,#111827,#020617)]">
          <div className="absolute inset-x-0 top-0 h-px animate-scanline bg-cyan-300/70" />
          <div className="absolute inset-5 rounded-md border border-slate-700/70" />
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-slate-300">
            <div className="relative flex h-14 w-14 items-center justify-center rounded-full border border-cyan-300/30 bg-cyan-300/5">
              <SpinnerGap size={28} className="animate-spin text-cyan-200" />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium">{job.status === 'running' ? '正在生成' : '等待队列'}</p>
          <p className="mt-1 text-xs text-slate-500">{ratio}</p>
              {job.stage && <p className="mt-1 text-[11px] text-cyan-200/70">{stageText(job.stage)}</p>}
            </div>
          </div>
          <button
            type="button"
            onClick={() => onCancel(job.job_id)}
            className="absolute right-3 top-3 rounded-full bg-black/55 p-2 text-white backdrop-blur transition hover:bg-red-500"
            title="取消任务"
          >
            <Stop size={18} weight="bold" />
          </button>
        </div>
      )}

      {isFailed && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-5 text-center text-red-300">
          <WarningCircle size={34} />
          <p className="text-sm font-medium">生成失败</p>
          <p className="max-w-full truncate text-xs text-red-200/70">{job.error || '未知错误'}</p>
        </div>
      )}

      {job.status === 'canceled' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-5 text-center text-slate-400">
          <Stop size={34} />
          <p className="text-sm font-medium">已取消</p>
          <p className="max-w-full truncate text-xs text-slate-500">{job.error || '任务已释放 worker'}</p>
        </div>
      )}

      {resultPath && (
        <>
          <img src={imageSrc} alt={job.prompt} className="absolute inset-0 h-full w-full object-cover" />
          <div className="absolute inset-0 bg-black/0 transition group-hover:bg-black/35" />
          <div className="absolute right-3 top-3 flex translate-y-1 gap-2 opacity-0 transition group-hover:translate-y-0 group-hover:opacity-100">
            <a
              href={imageSrc}
              download
              className="rounded-full bg-black/65 p-2 text-white backdrop-blur transition hover:bg-cyan-400 hover:text-slate-950"
              title="下载"
            >
              <DownloadSimple size={18} />
            </a>
            <button
              type="button"
              onClick={() => onUseAsReference(resultPath)}
              className="rounded-full bg-black/65 p-2 text-white backdrop-blur transition hover:bg-cyan-400 hover:text-slate-950"
              title="加入参考"
            >
              <Plus size={18} weight="bold" />
            </button>
            <a
              href={batchDownloadUrl(job.batch_id)}
              className="rounded-full bg-black/65 p-2 text-white backdrop-blur transition hover:bg-cyan-400 hover:text-slate-950"
              title="下载本批次"
            >
              <FileZip size={18} />
            </a>
          </div>
        </>
      )}

      {!isPending && (
        <button
          type="button"
          onClick={() => onReusePrompt(cleanPrompt(job.prompt))}
          className="absolute left-3 top-3 translate-y-1 rounded-full bg-black/65 p-2 text-white opacity-0 backdrop-blur transition hover:bg-cyan-400 hover:text-slate-950 group-hover:translate-y-0 group-hover:opacity-100"
          title="复用提示词"
        >
          <TextT size={18} weight="bold" />
        </button>
      )}

      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 via-black/30 to-transparent p-3">
        <div className="mb-2 flex items-center justify-between text-[11px] text-slate-300">
          <span className="rounded bg-white/10 px-2 py-0.5">{statusText(job.status)}</span>
          <span>{ratio}</span>
        </div>
        <p className="line-clamp-2 text-xs leading-5 text-slate-200">{cleanPrompt(job.prompt)}</p>
      </div>
    </article>
  );
}

function parseRatio(prompt: string): string {
  const match = prompt.match(/--ar\s+(\d+:\d+)/) || prompt.match(/\b(21:9|16:9|9:16|4:3|1:1)\b/);
  return match?.[1] || '1:1';
}

function cleanPrompt(prompt: string): string {
  return prompt.replace(/\s*--ar\s+\d+:\d+\s*/g, ' ').trim();
}

function statusText(status: Job['status']): string {
  if (status === 'running') return '运行中';
  if (status === 'queued') return '排队中';
  if (status === 'failed') return '失败';
  if (status === 'canceled') return '已取消';
  return '完成';
}

function stageText(stage: string): string {
  if (stage === 'starting') return '启动中';
  if (stage === 'generating') return '生成中';
  if (stage === 'image_detected') return '已检测到图片';
  if (stage === 'waiting_login') return '等待登录';
  if (stage === 'timeout') return '已超时';
  return stage;
}
