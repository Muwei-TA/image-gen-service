import { useMemo, useRef, useState } from 'react';
import {
  Check,
  FileImage,
  ImageSquare,
  MagicWand,
  SpinnerGap,
  Trash,
  UploadSimple,
} from '@phosphor-icons/react';
import { cn } from '../lib/utils';
import type { AssetItem } from '../lib/assets';

interface SidebarProps {
  assets: AssetItem[];
  selectedAssetIds: Set<string>;
  prompt: string;
  onPromptChange: (prompt: string) => void;
  onGenerate: (prompt: string, count: number, ratio: string) => void;
  onToggleAsset: (assetId: string) => void;
  onUploadFiles: (files: File[]) => void;
  onDeleteAsset: (assetId: string) => void;
  onClearSelection: () => void;
  isGenerating: boolean;
  isSubmitting: boolean;
  isUploading: boolean;
}

const RATIOS = [
  { label: 'Square', value: '1:1', className: 'aspect-square w-9' },
  { label: 'Classic', value: '4:3', className: 'aspect-[4/3] w-11' },
  { label: 'Wide', value: '16:9', className: 'aspect-video w-12' },
  { label: 'Banner', value: '21:9', className: 'aspect-[21/9] w-14' },
  { label: 'Story', value: '9:16', className: 'aspect-[9/16] w-7' },
];

const MIN_COUNT = 1;
const MAX_COUNT = 50;

export function Sidebar({
  assets,
  selectedAssetIds,
  prompt,
  onPromptChange,
  onGenerate,
  onToggleAsset,
  onUploadFiles,
  onDeleteAsset,
  onClearSelection,
  isGenerating,
  isSubmitting,
  isUploading,
}: SidebarProps) {
  const [count, setCount] = useState(4);
  const [ratio, setRatio] = useState('21:9');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const selectedCount = selectedAssetIds.size;
  const uploadAssets = useMemo(() => assets.filter((asset) => asset.source === 'upload'), [assets]);
  const generatedAssets = useMemo(() => assets.filter((asset) => asset.source === 'generated'), [assets]);

  function handleFiles(files: FileList | null) {
    const images = Array.from(files || []).filter((file) => file.type.startsWith('image/'));
    if (images.length) onUploadFiles(images);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function updateCount(value: number) {
    const next = Math.min(MAX_COUNT, Math.max(MIN_COUNT, Math.trunc(value) || MIN_COUNT));
    setCount(next);
  }

  return (
    <aside className="flex w-full shrink-0 flex-col border-r border-slate-200/80 bg-white/90 shadow-xl shadow-slate-200/60 backdrop-blur transition-colors dark:border-slate-800 dark:bg-slate-950/90 dark:shadow-slate-950/60 lg:h-full lg:w-[390px]">
      <div className="border-b border-slate-200 dark:border-slate-700 px-6 py-6">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-50 text-cta ring-1 ring-blue-100">
            <MagicWand weight="duotone" size={26} />
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cta">Generate images</p>
            <h1 className="mt-1 text-xl font-semibold tracking-tight text-text dark:text-slate-100">批量生图</h1>
          </div>
        </div>
        <p className="mt-4 text-sm leading-6 text-muted dark:text-slate-400">把提示词、比例、数量和参考图集中配置，一次提交多张图片生成任务。</p>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <label htmlFor="image-prompt" className="text-sm font-semibold text-text dark:text-slate-100">提示词</label>
            <span className="text-xs text-muted dark:text-slate-400">Prompt</span>
          </div>
          <textarea
            id="image-prompt"
            value={prompt}
            onChange={(event) => onPromptChange(event.target.value)}
            placeholder="描述要生成的画面：主体、场景、风格、光线、构图、颜色，以及需要参考图保留的特征。"
            className="h-40 w-full resize-none rounded-2xl border border-slate-200 bg-slate-50/70 p-4 text-sm leading-6 text-text shadow-inner shadow-slate-200/60 outline-none transition placeholder:text-slate-400 focus:border-cta focus:bg-white focus:ring-4 focus:ring-blue-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:shadow-slate-950/30 dark:focus:bg-slate-900"
          />
        </section>

        <section className="mt-7 space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-sm font-semibold text-text dark:text-slate-100">图片比例</label>
            <span className="rounded-full bg-blue-50 px-2.5 py-1 text-xs font-medium text-cta">{ratio}</span>
          </div>
          <div className="grid grid-cols-5 gap-2">
            {RATIOS.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setRatio(item.value)}
                className={cn(
                  'flex h-[78px] flex-col items-center justify-center gap-2 rounded-2xl border text-[11px] font-medium transition cursor-pointer',
                  ratio === item.value
                    ? 'border-blue-200 bg-blue-50 text-cta shadow-sm ring-2 ring-blue-100'
                    : 'border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-muted dark:text-slate-400 hover:border-blue-200 hover:text-cta hover:shadow-sm',
                )}
              >
                <span className={cn('block rounded-[4px] border-2 border-current', item.className)} />
                {item.label}
              </button>
            ))}
          </div>
        </section>

        <section className="mt-7 space-y-3">
          <div className="flex items-center justify-between">
            <label htmlFor="image-count" className="text-sm font-semibold text-text dark:text-slate-100">生成数量</label>
            <input
              id="image-count"
              type="number"
              min={MIN_COUNT}
              max={MAX_COUNT}
              value={count}
              onChange={(event) => updateCount(Number(event.target.value))}
              className="h-10 w-20 rounded-xl border border-slate-200 bg-white px-2 text-right font-mono text-sm text-text shadow-sm outline-none transition focus:border-cta focus:ring-4 focus:ring-blue-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
          </div>
          <input
            type="range"
            min={MIN_COUNT}
            max={MAX_COUNT}
            value={count}
            onChange={(event) => updateCount(Number(event.target.value))}
            className="w-full accent-cta cursor-pointer"
            aria-label="生成数量"
          />
          <p className="text-xs leading-5 text-muted dark:text-slate-400">单批最多 {MAX_COUNT} 张；服务会按当前并发配置启动队列。</p>
        </section>

        <section className="mt-8 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-semibold text-text dark:text-slate-100">参考图</label>
              <p className="mt-1 text-xs text-muted dark:text-slate-400">上传或选择生成结果作为参考</p>
            </div>
            {selectedCount > 0 && (
              <button
                type="button"
                onClick={onClearSelection}
                className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-muted shadow-sm transition hover:border-red-200 hover:bg-red-50 hover:text-danger dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400 dark:hover:bg-red-950/40 cursor-pointer"
              >
                <Trash size={14} />
                清空
              </button>
            )}
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(event) => handleFiles(event.target.files)}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="flex w-full items-center justify-center gap-3 rounded-2xl border border-dashed border-blue-200 bg-blue-50/60 px-4 py-4 text-sm font-medium text-cta transition hover:border-cta hover:bg-blue-50 cursor-pointer"
          >
            {isUploading ? <SpinnerGap size={18} className="animate-spin" /> : <UploadSimple size={18} />}
            {isUploading ? '上传中' : '上传参考图'}
          </button>

          <AssetGroup
            title="上传素材"
            emptyText="还没有上传图片"
            assets={uploadAssets}
            selectedAssetIds={selectedAssetIds}
            onToggleAsset={onToggleAsset}
            onDeleteAsset={onDeleteAsset}
          />
          <AssetGroup
            title="生成结果"
            emptyText="生成图片后可加入参考"
            assets={generatedAssets}
            selectedAssetIds={selectedAssetIds}
            onToggleAsset={onToggleAsset}
          />
        </section>
      </div>

      <div className="border-t border-slate-200 bg-slate-50/80 p-6 dark:border-slate-800 dark:bg-slate-900/80">
        <button
          type="button"
          disabled={!prompt.trim() || isSubmitting}
          onClick={() => onGenerate(prompt, count, ratio)}
          className={cn(
            'flex w-full items-center justify-center gap-2 rounded-2xl px-4 py-4 text-sm font-semibold shadow-lg transition active:scale-[0.99]',
            !prompt.trim() || isSubmitting
              ? 'cursor-not-allowed bg-slate-200 text-slate-500 shadow-none'
              : 'bg-cta text-white shadow-blue-200 hover:bg-ctaHover cursor-pointer',
          )}
        >
          {isSubmitting ? <SpinnerGap size={20} className="animate-spin" /> : <ImageSquare size={20} weight="bold" />}
          {isSubmitting ? '提交中' : `生成 ${count} 张图片`}
        </button>
        <p className="mt-3 flex items-center justify-center gap-2 text-xs text-muted dark:text-slate-400">
          <FileImage size={14} />
          {isGenerating ? '队列运行中，仍可继续提交新任务' : `当前选中 ${selectedCount} 张参考图`}
        </p>
      </div>
    </aside>
  );
}

function AssetGroup({
  title,
  emptyText,
  assets,
  selectedAssetIds,
  onToggleAsset,
  onDeleteAsset,
}: {
  title: string;
  emptyText: string;
  assets: AssetItem[];
  selectedAssetIds: Set<string>;
  onToggleAsset: (assetId: string) => void;
  onDeleteAsset?: (assetId: string) => void;
}) {
  const [visibleCount, setVisibleCount] = useState(18);
  const visibleAssets = assets.slice(0, visibleCount);
  const hiddenCount = Math.max(0, assets.length - visibleCount);

  return (
    <div className="pt-1">
      <div className="mb-2 flex items-center justify-between text-xs font-medium text-muted dark:text-slate-400">
        <span>{title}</span>
        <span>{assets.length}</span>
      </div>
      {assets.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white px-3 py-4 text-center text-xs text-muted shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400">{emptyText}</div>
      ) : (
        <div className="grid grid-cols-3 gap-2.5">
          {visibleAssets.map((asset) => {
            const selected = selectedAssetIds.has(asset.id);
            return (
              <button
                key={asset.id}
                type="button"
                onClick={() => onToggleAsset(asset.id)}
                title={asset.label}
                className={cn(
                  'group relative aspect-square overflow-hidden rounded-2xl border bg-slate-100 shadow-sm transition cursor-pointer',
                  selected ? 'border-cta ring-2 ring-blue-100' : 'border-white hover:border-blue-200 hover:shadow-md',
                )}
              >
                <img src={asset.src} alt={asset.label} className="h-full w-full object-cover transition duration-300 group-hover:scale-105" />
                <span className="absolute inset-0 bg-gradient-to-t from-black/45 via-transparent to-transparent opacity-80" />
                {selected && (
                  <span className="absolute right-1.5 top-1.5 rounded-full bg-cta p-1 text-white shadow-sm">
                    <Check size={12} weight="bold" />
                  </span>
                )}
                <span className="absolute bottom-1.5 left-1.5 rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-medium text-slate-700 shadow-sm backdrop-blur dark:bg-slate-900/90 dark:text-slate-200">
                  {asset.source === 'upload' ? '上传' : '生成'}
                </span>
                {asset.source === 'upload' && onDeleteAsset && (
                  <span
                    role="button"
                    tabIndex={0}
                    title="删除素材"
                    onClick={(event) => {
                      event.stopPropagation();
                      onDeleteAsset(asset.id);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        event.stopPropagation();
                        onDeleteAsset(asset.id);
                      }
                    }}
                    className="absolute left-1.5 top-1.5 rounded-full bg-white/90 p-1 text-slate-700 opacity-0 shadow-sm backdrop-blur transition hover:bg-red-50 hover:text-danger group-hover:opacity-100 group-focus-within:opacity-100 dark:bg-slate-900/90 dark:text-slate-200 cursor-pointer"
                  >
                    <Trash size={12} weight="bold" />
                  </span>
                )}
              </button>
            );
          })}
          {hiddenCount > 0 && (
            <button
              type="button"
              onClick={() => setVisibleCount((current) => current + 18)}
              className="aspect-square rounded-2xl border border-slate-200 bg-white text-xs font-medium text-muted shadow-sm transition hover:border-blue-200 hover:text-cta dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400 cursor-pointer"
            >
              +{hiddenCount}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
