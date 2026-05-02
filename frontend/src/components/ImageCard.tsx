import { DownloadSimple, FileZip, Plus, SpinnerGap, Stop, TextT, WarningCircle } from '@phosphor-icons/react';
import type { Job } from '../lib/api';
import { batchDownloadUrl, fileUrl } from '../lib/api';
import { cn } from '../lib/utils';

interface ImageCardProps {
  job: Job;
  onUseAsReference: (path: string) => void;
  onCancel: (jobId: string) => void;
  onReusePrompt: (prompt: string) => void;
  onPreview: (path: string, prompt: string) => void;
}

const RATIO_CLASSES: Record<string, string> = {
  '1:1': 'aspect-square',
  '4:3': 'aspect-[4/3]',
  '16:9': 'aspect-video',
  '21:9': 'aspect-[21/9] md:col-span-2',
  '9:16': 'aspect-[9/16]',
};

export function ImageCard({ job, onUseAsReference, onCancel, onReusePrompt, onPreview }: ImageCardProps) {
  const isPending = job.status === 'queued' || job.status === 'running';
  const isFailed = job.status === 'failed';
  const isCanceled = job.status === 'canceled';
  const resultPath = job.result_paths?.[0];
  const hasMissingResult = job.status === 'succeeded' && !resultPath;
  const ratio = parseRatio(job.prompt);
  const imageSrc = resultPath ? fileUrl(resultPath) : '';

  return (
    <article
      className={cn(
        'group relative overflow-hidden rounded-[1.5rem] border bg-white shadow-sm shadow-slate-200/70 transition duration-300 focus-within:shadow-xl hover:-translate-y-0.5 hover:shadow-xl hover:shadow-slate-200/90 dark:bg-slate-900 dark:shadow-slate-950/40 dark:hover:shadow-slate-950/70',
        RATIO_CLASSES[ratio] || 'aspect-square',
        isFailed || hasMissingResult
          ? 'border-red-200 bg-red-50/70 dark:border-red-900 dark:bg-red-950/30'
          : isCanceled
            ? 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800'
            : 'border-white ring-1 ring-slate-200/80 dark:border-slate-800 dark:ring-slate-700',
      )}
    >
      {isPending && (
        <div className="absolute inset-0 overflow-hidden bg-[radial-gradient(circle_at_50%_0%,rgba(219,234,254,0.95),transparent_45%),linear-gradient(135deg,#ffffff,#f8fafc)] dark:bg-[radial-gradient(circle_at_50%_0%,rgba(37,99,235,0.24),transparent_45%),linear-gradient(135deg,#0f172a,#020617)]">
          <div className="absolute inset-x-0 top-0 h-px animate-scanline bg-cta/40" />
          <div className="absolute inset-4 rounded-[1.25rem] border border-dashed border-blue-200 bg-white/55" />
          <StatusBadge status={job.status} ratio={ratio} />
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-center text-slate-700">
            <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-white shadow-lg shadow-blue-100 ring-1 ring-blue-100">
              <SpinnerGap size={30} className="animate-spin text-cta" />
            </div>
            <div>
              <p className="text-sm font-semibold text-text dark:text-slate-100">{job.status === 'running' ? '正在生成图片' : '等待进入队列'}</p>
              <p className="mt-1 text-xs text-muted dark:text-slate-400">{job.stage ? stageText(job.stage) : '准备 worker 与输出目录'}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => onCancel(job.job_id)}
            className="absolute right-3 top-3 rounded-full border border-slate-200 bg-white/90 p-2 text-slate-600 shadow-sm backdrop-blur transition hover:border-red-200 hover:bg-red-50 hover:text-danger cursor-pointer"
            title="取消任务"
          >
            <Stop size={18} weight="bold" />
          </button>
        </div>
      )}

      {isFailed && <TerminalState icon="error" title="生成失败" message={job.error || '未知错误'} />}
      {isCanceled && <TerminalState icon="canceled" title="已取消" message={job.error || '任务已释放 worker'} />}
      {hasMissingResult && <TerminalState icon="error" title="没有检测到图片" message="任务已完成，但没有可展示的结果路径" />}

      {resultPath && (
        <>
          <img src={imageSrc} alt={job.prompt} className="absolute inset-0 h-full w-full object-cover" />
          <button
            type="button"
            onClick={() => onPreview(resultPath, cleanPrompt(job.prompt))}
            className="absolute inset-0 cursor-zoom-in"
            aria-label="放大预览图片"
          />
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-slate-950/70 via-slate-950/10 to-transparent opacity-80" />
          <StatusBadge status={job.status} ratio={ratio} />
          <div className="absolute right-3 top-3 flex translate-y-1 gap-2 opacity-0 transition group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:translate-y-0 group-focus-within:opacity-100">
            <a
              href={imageSrc}
              download
              className="rounded-full bg-white/95 p-2 text-slate-700 shadow-sm backdrop-blur transition hover:bg-cta hover:text-white cursor-pointer"
              title="下载图片"
            >
              <DownloadSimple size={18} />
            </a>
            <button
              type="button"
              onClick={() => onUseAsReference(resultPath)}
              className="rounded-full bg-white/95 p-2 text-slate-700 shadow-sm backdrop-blur transition hover:bg-cta hover:text-white cursor-pointer"
              title="加入参考图"
            >
              <Plus size={18} weight="bold" />
            </button>
            <a
              href={batchDownloadUrl(job.batch_id)}
              className="rounded-full bg-white/95 p-2 text-slate-700 shadow-sm backdrop-blur transition hover:bg-cta hover:text-white cursor-pointer"
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
          className="absolute left-3 top-3 translate-y-1 rounded-full bg-white/95 p-2 text-slate-700 opacity-0 shadow-sm backdrop-blur transition hover:bg-cta hover:text-white group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:translate-y-0 group-focus-within:opacity-100 cursor-pointer"
          title="复用提示词"
        >
          <TextT size={18} weight="bold" />
        </button>
      )}

      <div className="absolute inset-x-0 bottom-0 p-4">
        <div className="rounded-2xl bg-white/92 p-3 shadow-lg shadow-slate-950/10 backdrop-blur transition group-hover:bg-white group-focus-within:bg-white dark:bg-slate-950/88 dark:shadow-slate-950/40 dark:group-hover:bg-slate-950 dark:group-focus-within:bg-slate-950">
          <div className="mb-2 flex items-center justify-between gap-3 text-[11px] font-medium text-muted dark:text-slate-400">
            <span>{statusText(job.status)}</span>
            <span>{ratio}</span>
          </div>
          <p className="line-clamp-2 text-xs leading-5 text-slate-700 dark:text-slate-300">{cleanPrompt(job.prompt) || '等待提示词内容'}</p>
        </div>
      </div>
    </article>
  );
}

function StatusBadge({ status, ratio }: { status: Job['status']; ratio: string }) {
  const className =
    status === 'succeeded'
      ? 'bg-emerald-50 text-emerald-700 ring-emerald-100'
      : status === 'failed'
        ? 'bg-red-50 text-red-700 ring-red-100'
        : status === 'canceled'
          ? 'bg-slate-100 text-slate-600 ring-slate-200'
          : 'bg-blue-50 text-blue-700 ring-blue-100';

  return (
    <div className="absolute left-3 top-3 flex items-center gap-2">
      <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold shadow-sm ring-1 ${className}`}>{statusText(status)}</span>
      <span className="rounded-full bg-white/90 px-2.5 py-1 text-[11px] font-medium text-slate-600 shadow-sm ring-1 ring-slate-200">{ratio}</span>
    </div>
  );
}

function TerminalState({ icon, title, message }: { icon: 'error' | 'canceled'; title: string; message: string }) {
  const isError = icon === 'error';
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 p-6 text-center">
      <div className={cn('flex h-14 w-14 items-center justify-center rounded-full shadow-sm ring-1', isError ? 'bg-red-50 text-danger ring-red-100' : 'bg-slate-100 text-slate-500 ring-slate-200')}>
        {isError ? <WarningCircle size={32} /> : <Stop size={32} />}
      </div>
      <div>
        <p className="text-sm font-semibold text-text dark:text-slate-100">{title}</p>
        <p className="mt-1 max-w-full truncate text-xs text-muted dark:text-slate-400">{message}</p>
      </div>
    </div>
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
  if (status === 'running') return '生成中';
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
