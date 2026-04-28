import { fileUrl, type UploadRecord } from './api';

export type AssetSource = 'upload' | 'generated';

export interface AssetItem {
  id: string;
  label: string;
  path: string;
  src: string;
  source: AssetSource;
  imageId?: string;
  signature?: string;
}

export function uploadToAsset(upload: UploadRecord): AssetItem {
  return {
    id: upload.image_id,
    label: upload.filename,
    path: upload.path,
    src: fileUrl(upload.path),
    source: 'upload',
    imageId: upload.image_id,
    signature: `${upload.filename}:${upload.size}`,
  };
}

export function generatedToAsset(path: string): AssetItem {
  const label = path.split('/').pop() || 'generated-image.png';
  return {
    id: `generated:${path}`,
    label,
    path,
    src: fileUrl(path),
    source: 'generated',
  };
}
