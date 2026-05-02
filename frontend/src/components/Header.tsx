import { Moon, Sun } from '@phosphor-icons/react';

export function Header({
  runningCount,
  assetCount,
  selectedAssetCount,
  isDarkMode,
  onToggleTheme,
}: {
  runningCount: number;
  assetCount: number;
  selectedAssetCount: number;
  isDarkMode: boolean;
  onToggleTheme: () => void;
}) {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/85 px-4 py-3 backdrop-blur-xl transition-colors dark:border-slate-800 dark:bg-slate-950/80 sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-[1540px] items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-slate-950 to-blue-700 text-sm font-bold text-white shadow-lg shadow-blue-200 dark:shadow-blue-950/40">
            AI
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-text dark:text-slate-100">Image Batch Studio</h1>
            <p className="text-xs font-medium text-muted dark:text-slate-400">Prompt · Reference images · Batch queue</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="hidden items-center gap-2 sm:flex">
            <Metric label="队列" value={runningCount} tone="blue" />
            <Metric label="素材" value={assetCount} tone="slate" />
            <Metric label="参考" value={selectedAssetCount} tone="green" />
          </div>
          <button
            type="button"
            onClick={onToggleTheme}
            className="inline-flex h-10 items-center gap-2 rounded-full border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800 cursor-pointer"
            aria-label={isDarkMode ? '切换到浅色模式' : '切换到暗黑模式'}
          >
            {isDarkMode ? <Sun size={16} /> : <Moon size={16} />}
            <span className="hidden md:inline">{isDarkMode ? '浅色' : '暗黑'}</span>
          </button>
        </div>
      </div>
    </header>
  );
}

function Metric({ label, value, tone }: { label: string; value: number; tone: 'blue' | 'slate' | 'green' }) {
  const toneClass = {
    blue: 'bg-blue-50 text-blue-700 border-blue-100 dark:bg-blue-950/50 dark:text-blue-200 dark:border-blue-900',
    slate: 'bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-900 dark:text-slate-200 dark:border-slate-700',
    green: 'bg-emerald-50 text-emerald-700 border-emerald-100 dark:bg-emerald-950/50 dark:text-emerald-200 dark:border-emerald-900',
  }[tone];

  return (
    <div className={`rounded-full border px-3 py-1.5 ${toneClass}`}>
      <span className="text-xs text-current/70">{label}</span>
      <span className="ml-2 text-sm font-semibold tabular-nums">{value}</span>
    </div>
  );
}
