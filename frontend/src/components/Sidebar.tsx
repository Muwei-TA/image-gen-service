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
  { label: '1:1', value: '1:1', className: 'aspect-square w-9' },
  { label: '4:3', value: '4:3', className: 'aspect-[4/3] w-11' },
  { label: '16:9', value: '16:9', className: 'aspect-video w-12' },
  { label: '21:9', value: '21:9', className: 'aspect-[21/9] w-14' },
  { label: '9:16', value: '9:16', className: 'aspect-[9/16] w-7' },
];

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

  return (
    <aside className="flex h-full w-[360px] shrink-0 flex-col border-r border-slate-800 bg-[#111827]">
      <div className="border-b border-slate-800 px-6 py-5">
        <div className="flex items-center gap-3 text-cyan-300">
          <MagicWand weight="duotone" size={28} />
          <div>
            <h1 className="text-lg font-semibold text-white">Image Batch Studio</h1>
            <p className="mt-1 text-xs text-slate-400">提示词、参考图和队列一处完成</p>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <section className="space-y-3">
          <label className="text-sm font-medium text-slate-200">提示词</label>
          <textarea
            value={prompt}
            onChange={(event) => onPromptChange(event.target.value)}
            placeholder="例如：21:9 动漫女孩直播间截图，霓虹灯，细腻线稿，干净画面"
            className="h-36 w-full resize-none rounded-lg border border-slate-700 bg-slate-950/60 p-3 text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400 focus:ring-2 focus:ring-cyan-400/20"
          />
        </section>

        <section className="mt-6 space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-slate-200">图片比例</label>
            <span className="text-xs text-slate-500">{ratio}</span>
          </div>
          <div className="grid grid-cols-5 gap-2">
            {RATIOS.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() => setRatio(item.value)}
                className={cn(
                  'flex h-[72px] flex-col items-center justify-center gap-2 rounded-lg border text-xs transition',
                  ratio === item.value
                    ? 'border-cyan-400 bg-cyan-400/10 text-cyan-200'
                    : 'border-slate-700 bg-slate-950/30 text-slate-400 hover:border-slate-500 hover:text-slate-200',
                )}
              >
                <span className={cn('block rounded-[3px] border-2 border-current', item.className)} />
                {item.label}
              </button>
            ))}
          </div>
        </section>

        <section className="mt-6 space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-slate-200">生成数量</label>
            <span className="font-mono text-sm text-cyan-300">{count}</span>
          </div>
          <input
            type="range"
            min="1"
            max="8"
            value={count}
            onChange={(event) => setCount(Number(event.target.value))}
            className="w-full accent-cyan-400"
          />
        </section>

        <section className="mt-7 space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-slate-200">素材库</label>
            {selectedCount > 0 && (
              <button
                type="button"
                onClick={onClearSelection}
                className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200"
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
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-slate-600 px-4 py-3 text-sm text-slate-300 transition hover:border-cyan-400 hover:bg-cyan-400/5 hover:text-cyan-100"
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

      <div className="border-t border-slate-800 p-6">
        <button
          type="button"
          disabled={!prompt.trim() || isSubmitting}
          onClick={() => onGenerate(prompt, count, ratio)}
          className={cn(
            'flex w-full items-center justify-center gap-2 rounded-lg px-4 py-4 text-sm font-semibold transition active:scale-[0.99]',
            !prompt.trim() || isSubmitting
              ? 'cursor-not-allowed bg-slate-800 text-slate-500'
              : 'bg-cyan-400 text-slate-950 shadow-[0_14px_40px_rgba(34,211,238,0.22)] hover:bg-cyan-300',
          )}
        >
          {isSubmitting ? <SpinnerGap size={20} className="animate-spin" /> : <ImageSquare size={20} weight="bold" />}
          {isSubmitting ? '提交中' : `生成 ${count} 张`}
        </button>
        <p className="mt-3 flex items-center justify-center gap-2 text-xs text-slate-500">
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
    <div className="pt-2">
      <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
        <span>{title}</span>
        <span>{assets.length}</span>
      </div>
      {assets.length === 0 ? (
        <div className="rounded-lg border border-slate-800 bg-slate-950/30 px-3 py-4 text-center text-xs text-slate-600">{emptyText}</div>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          {visibleAssets.map((asset) => {
            const selected = selectedAssetIds.has(asset.id);
            return (
              <button
                key={asset.id}
                type="button"
                onClick={() => onToggleAsset(asset.id)}
                title={asset.label}
                className={cn(
                  'group relative aspect-square overflow-hidden rounded-md border bg-slate-900 transition',
                  selected ? 'border-cyan-300 ring-2 ring-cyan-400/30' : 'border-slate-800 hover:border-slate-500',
                )}
              >
                <img src={asset.src} alt={asset.label} className="h-full w-full object-cover transition duration-300 group-hover:scale-105" />
                {selected && (
                  <span className="absolute right-1.5 top-1.5 rounded-full bg-cyan-300 p-1 text-slate-950">
                    <Check size={12} weight="bold" />
                  </span>
                )}
                <span className="absolute bottom-1.5 left-1.5 rounded bg-black/60 px-1.5 py-0.5 text-[10px] text-white">
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
                    className="absolute left-1.5 top-1.5 rounded bg-black/65 p-1 text-white opacity-0 transition hover:bg-red-500 group-hover:opacity-100"
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
              className="aspect-square rounded-md border border-slate-800 bg-slate-950/60 text-xs text-slate-400 transition hover:border-cyan-400 hover:text-cyan-200"
            >
              +{hiddenCount}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
