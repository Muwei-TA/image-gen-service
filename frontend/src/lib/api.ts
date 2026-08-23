const API = '/api'

export interface CodexStatus {
  available: boolean
  authenticated: boolean
  method?: 'chatgpt' | 'api_key' | null
  detail: string
  max_concurrency: number
  egress_proxy: {
    enabled: boolean
    scheme?: string
    host?: string
    port?: number | null
  }
}

export interface HealthStatus {
  ok: boolean
  platform: { os: string; native_windows: boolean; docker: boolean }
  codex: CodexStatus
}

export interface DeviceLoginState {
  running: boolean
  completed: boolean
  success: boolean
  verification_url?: string | null
  user_code?: string | null
  message: string
}

export interface Job {
  job_id: string
  batch_id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled'
  stage?: string
  prompt: string
  result_paths: string[]
  error?: string
}

export interface Batch {
  batch_id: string
  status: string
  jobs: Job[]
  created_at: string
  total: number
  running: number
  succeeded: number
  failed: number
  canceled?: number
}

export interface UploadRecord {
  image_id: string
  filename: string
  mime_type: string
  size: number
  path: string
  created_at: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, init)
  if (!response.ok) {
    let message = `请求失败 (${response.status})`
    try {
      const payload = await response.json()
      message = payload.error || payload.detail || message
    } catch {
      // Response is not JSON.
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export const api = {
  health: () => request<HealthStatus>('/health'),
  authStatus: () => request<CodexStatus>('/auth/status'),
  startLogin: () => request<DeviceLoginState>('/auth/login/device', { method: 'POST' }),
  loginState: () => request<DeviceLoginState>('/auth/login/device'),
  cancelLogin: () => request<DeviceLoginState>('/auth/login/device', { method: 'DELETE' }),
  logout: () => request<CodexStatus>('/auth/logout', { method: 'POST' }),
  batches: () => request<{ batches: Batch[] }>('/batches'),
  batch: (id: string) => request<Batch>(`/batches/${encodeURIComponent(id)}`),
  createBatch: (payload: Record<string, unknown>) => request<Batch>('/batches', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),
  cancelJob: (id: string) => request<Job>(`/jobs/${encodeURIComponent(id)}/cancel`, { method: 'POST' }),
  uploads: () => request<{ uploads: UploadRecord[] }>('/uploads'),
  deleteUpload: (id: string) => request(`/uploads/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  upload: async (file: File) => {
    const data = await fileToBase64(file)
    return request<UploadRecord>('/uploads', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: file.name, mime_type: file.type || 'image/png', data }),
    })
  },
}

export function imageUrl(path: string): string {
  return `${API}/files?path=${encodeURIComponent(path)}`
}

export function batchDownloadUrl(batchId: string): string {
  return `${API}/batches/${encodeURIComponent(batchId)}/download`
}

export function allImagesDownloadUrl(): string {
  return `${API}/downloads/images`
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || '').split(',').pop() || '')
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}
