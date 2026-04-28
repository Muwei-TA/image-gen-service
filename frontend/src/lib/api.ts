const BASE_URL = '';

export interface BatchRequest {
  prompt?: string;
  prompts?: string[];
  count?: number;
  workdir?: string;
  reference_image_ids?: string[];
  reference_images?: string[];
}

export interface Job {
  job_id: string;
  batch_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled';
  stage?: string;
  prompt: string;
  result_paths: string[];
  error?: string;
}

export interface Batch {
  batch_id: string;
  status: string;
  jobs: Job[];
  created_at: string;
  total: number;
  running: number;
  succeeded: number;
  failed: number;
  canceled?: number;
}

export interface UploadRecord {
  image_id: string;
  filename: string;
  mime_type: string;
  size: number;
  path: string;
  created_at: string;
}

export interface HealthStatus {
  ok: boolean;
  codex?: {
    available: boolean;
    authenticated: boolean;
    auth_path: string;
    bin: string;
    max_concurrency: number;
  };
}

export async function getHealth(): Promise<HealthStatus> {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) throw new Error(await readError(res, 'Failed to fetch service health'));
  return res.json();
}

export async function submitBatch(req: BatchRequest): Promise<Batch> {
  const res = await fetch(`${BASE_URL}/batches`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(await readError(res, 'Failed to submit batch'));
  return res.json();
}

export async function getBatch(batchId: string): Promise<Batch> {
  const res = await fetch(`${BASE_URL}/batches/${batchId}`);
  if (!res.ok) throw new Error(await readError(res, 'Failed to fetch batch'));
  return res.json();
}

export async function getBatches(): Promise<{ batches: Batch[] }> {
  const res = await fetch(`${BASE_URL}/batches`);
  if (!res.ok) throw new Error(await readError(res, 'Failed to fetch batches'));
  return res.json();
}

export async function cancelJob(jobId: string): Promise<Job> {
  const res = await fetch(`${BASE_URL}/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(await readError(res, 'Failed to cancel job'));
  return res.json();
}

export async function cancelBatch(batchId: string): Promise<Batch> {
  const res = await fetch(`${BASE_URL}/batches/${encodeURIComponent(batchId)}/cancel`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(await readError(res, 'Failed to cancel batch'));
  return res.json();
}

export function batchDownloadUrl(batchId: string): string {
  return `${BASE_URL}/batches/${encodeURIComponent(batchId)}/download`;
}

export async function getUploads(): Promise<{ uploads: UploadRecord[] }> {
  const res = await fetch(`${BASE_URL}/uploads`);
  if (!res.ok) throw new Error(await readError(res, 'Failed to fetch uploads'));
  return res.json();
}

export async function uploadImage(file: File): Promise<UploadRecord> {
  const data = await fileToBase64(file);
  const res = await fetch(`${BASE_URL}/uploads`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filename: file.name,
      mime_type: file.type || 'image/png',
      data,
    }),
  });
  if (!res.ok) throw new Error(await readError(res, 'Failed to upload image'));
  return res.json();
}

export async function deleteUpload(imageId: string): Promise<void> {
  const res = await fetch(`${BASE_URL}/uploads/${encodeURIComponent(imageId)}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(await readError(res, 'Failed to delete upload'));
}

export function fileUrl(path: string): string {
  return `${BASE_URL}/files?path=${encodeURIComponent(path)}`;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result || '');
      resolve(value.includes(',') ? value.split(',')[1] : value);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

async function readError(res: Response, fallback: string): Promise<string> {
  try {
    const payload = await res.json();
    return payload?.error || fallback;
  } catch {
    return fallback;
  }
}
