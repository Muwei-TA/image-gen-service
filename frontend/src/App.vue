<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  PhArrowSquareOut,
  PhCheck,
  PhCircleNotch,
  PhCopy,
  PhDownloadSimple,
  PhImageSquare,
  PhMonitor,
  PhPackage,
  PhPlay,
  PhPlus,
  PhShieldCheck,
  PhSignOut,
  PhSparkle,
  PhUploadSimple,
  PhWarningCircle,
  PhX,
} from '@phosphor-icons/vue'
import { api, batchDownloadUrl, imageUrl, type Batch, type DeviceLoginState, type HealthStatus, type UploadRecord } from './lib/api'

const health = ref<HealthStatus | null>(null)
const batches = ref<Batch[]>([])
const uploads = ref<UploadRecord[]>([])
const selectedUploadIds = ref(new Set<string>())
const prompt = ref('')
const count = ref(1)
const ratio = ref('1:1')
const busy = ref(false)
const uploadBusy = ref(false)
const error = ref('')
const loginOpen = ref(false)
const loginState = ref<DeviceLoginState | null>(null)
const previewPath = ref<string | null>(null)
let workspaceTimer: number | undefined
let loginTimer: number | undefined

const jobs = computed(() => batches.value.flatMap((batch) => batch.jobs || []))
const generated = computed(() => jobs.value.flatMap((job) => (job.result_paths || []).map((path) => ({ path, job, batchId: job.batch_id }))))
const activeJobs = computed(() => jobs.value.filter((job) => ['queued', 'running'].includes(job.status)))
const authenticated = computed(() => Boolean(health.value?.codex.authenticated))
const platformLabel = computed(() => {
  const platform = health.value?.platform
  if (!platform) return '正在连接'
  if (platform.native_windows) return 'Windows 原生'
  if (platform.docker) return 'Docker'
  return platform.os === 'darwin' ? 'macOS 原生' : `${platform.os} 原生`
})

async function loadWorkspace() {
  try {
    const [nextHealth, batchList, uploadList] = await Promise.all([api.health(), api.batches(), api.uploads()])
    health.value = nextHealth
    uploads.value = uploadList.uploads
    const ordered = [...batchList.batches].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)).slice(0, 24)
    batches.value = await Promise.all(ordered.map((batch) => api.batch(batch.batch_id)))
    error.value = ''
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '工作台连接失败'
  }
}

async function refreshWorkspace() {
  await loadWorkspace()
  workspaceTimer = window.setTimeout(refreshWorkspace, activeJobs.value.length ? 2500 : 8000)
}

async function generate() {
  if (!prompt.value.trim()) return
  if (!authenticated.value) {
    loginOpen.value = true
    return
  }
  busy.value = true
  error.value = ''
  try {
    const batch = await api.createBatch({
      prompt: `${prompt.value.trim()} --ar ${ratio.value}`,
      count: count.value,
      reference_image_ids: [...selectedUploadIds.value],
    })
    batches.value = [batch, ...batches.value]
    prompt.value = ''
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '任务提交失败'
  } finally {
    busy.value = false
  }
}

async function uploadFiles(event: Event) {
  const input = event.target as HTMLInputElement
  const files = [...(input.files || [])]
  if (!files.length) return
  uploadBusy.value = true
  try {
    const created = await Promise.all(files.map((file) => api.upload(file)))
    uploads.value = [...created, ...uploads.value]
    selectedUploadIds.value = new Set([...selectedUploadIds.value, ...created.map((item) => item.image_id)])
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '上传失败'
  } finally {
    uploadBusy.value = false
    input.value = ''
  }
}

function toggleUpload(id: string) {
  const next = new Set(selectedUploadIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedUploadIds.value = next
}

async function beginLogin() {
  error.value = ''
  try {
    loginState.value = await api.startLogin()
    startLoginPolling()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '无法启动登录'
  }
}

function startLoginPolling() {
  if (loginTimer) window.clearInterval(loginTimer)
  loginTimer = window.setInterval(async () => {
    loginState.value = await api.loginState()
    if (loginState.value.completed) {
      window.clearInterval(loginTimer)
      loginTimer = undefined
      await loadWorkspace()
      if (loginState.value.success) window.setTimeout(() => (loginOpen.value = false), 900)
    }
  }, 1000)
}

async function copyCode() {
  if (loginState.value?.user_code) await navigator.clipboard.writeText(loginState.value.user_code)
}

async function logout() {
  await api.logout()
  await loadWorkspace()
}

function statusLabel(status: string) {
  return ({ queued: '等待中', running: '生成中', succeeded: '已完成', failed: '失败', canceled: '已取消' } as Record<string, string>)[status] || status
}

function shortDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}

onMounted(refreshWorkspace)

onBeforeUnmount(() => {
  if (workspaceTimer) window.clearTimeout(workspaceTimer)
  if (loginTimer) window.clearInterval(loginTimer)
})
</script>

<template>
  <div class="app-shell">
    <aside class="studio-rail">
      <div class="brand-lockup">
        <span class="brand-mark"><PhSparkle :size="20" weight="fill" /></span>
        <div><strong>Image Studio</strong><span>powered by Codex</span></div>
      </div>

      <section class="composer-block">
        <div class="section-kicker">创作指令</div>
        <textarea v-model="prompt" maxlength="8000" placeholder="描述画面、主体、光线、材质与镜头……" @keydown.meta.enter="generate" @keydown.ctrl.enter="generate" />
        <div class="composer-meta"><span>{{ prompt.length }} / 8000</span><span>⌘ Enter 提交</span></div>

        <div class="field-row">
          <label>画幅<select v-model="ratio"><option>1:1</option><option>4:3</option><option>3:4</option><option>16:9</option><option>9:16</option></select></label>
          <label>数量<select v-model="count"><option v-for="value in 4" :key="value" :value="value">{{ value }} 张</option></select></label>
        </div>

        <button class="primary-action" :disabled="busy || !prompt.trim()" @click="generate">
          <PhCircleNotch v-if="busy" class="spin" :size="19" />
          <PhPlay v-else :size="19" weight="fill" />
          {{ busy ? '正在排入队列' : '开始生成' }}
        </button>
      </section>

      <section class="reference-block">
        <div class="section-heading"><div><span>参考素材</span><small>{{ selectedUploadIds.size }} 已选择</small></div><label class="icon-button upload-button"><PhUploadSimple :size="19" /><input type="file" accept="image/*" multiple @change="uploadFiles" /></label></div>
        <div v-if="uploadBusy" class="upload-progress"><PhCircleNotch class="spin" :size="18" />正在读取素材</div>
        <div v-else-if="uploads.length" class="reference-grid">
          <button v-for="item in uploads" :key="item.image_id" class="reference-tile" :class="{ selected: selectedUploadIds.has(item.image_id) }" @click="toggleUpload(item.image_id)">
            <img :src="imageUrl(item.path)" :alt="item.filename" />
            <span v-if="selectedUploadIds.has(item.image_id)"><PhCheck :size="13" weight="bold" /></span>
          </button>
        </div>
        <label v-else class="empty-upload"><PhPlus :size="22" /><span>添加参考图</span><small>PNG · JPG · WEBP</small><input type="file" accept="image/*" multiple @change="uploadFiles" /></label>
      </section>

      <div class="rail-footer">
        <button class="account-card" @click="authenticated ? undefined : (loginOpen = true)">
          <span class="account-icon" :class="{ online: authenticated }"><PhShieldCheck :size="18" weight="fill" /></span>
          <span><strong>{{ authenticated ? 'Codex 已连接' : '连接 Codex' }}</strong><small>{{ authenticated ? (health?.codex.method === 'api_key' ? 'API Key' : 'ChatGPT 账户') : '登录后才能生成' }}</small></span>
          <PhSignOut v-if="authenticated" :size="18" @click.stop="logout" />
          <PhArrowSquareOut v-else :size="18" />
        </button>
      </div>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div><span class="eyebrow">创作空间</span><h1>让想法变成画面。</h1></div>
        <div class="runtime-chip"><component :is="health?.platform.docker ? PhPackage : PhMonitor" :size="17" /><span>{{ platformLabel }}</span><i :class="{ active: health?.ok }" /></div>
      </header>

      <div v-if="error" class="error-banner"><PhWarningCircle :size="19" weight="fill" /><span>{{ error }}</span><button @click="error = ''"><PhX :size="17" /></button></div>

      <section class="queue-strip" v-if="activeJobs.length">
        <div class="pulse-orb"><PhCircleNotch class="spin" :size="22" /></div>
        <div><strong>{{ activeJobs.length }} 个任务正在创作</strong><span>Codex 正在处理画面，完成后会自动出现。</span></div>
        <div class="queue-bars"><i v-for="value in Math.min(activeJobs.length, 5)" :key="value" :style="{ animationDelay: `${value * 120}ms` }" /></div>
      </section>

      <section class="gallery-section">
        <div class="gallery-heading"><div><h2>作品流</h2><span>{{ generated.length }} 个结果</span></div><p>最近完成的图像与正在运行的任务</p></div>

        <div v-if="!jobs.length" class="empty-stage">
          <div class="empty-visual"><span /><span /><span /><PhImageSquare :size="34" /></div>
          <h2>工作台已经就绪</h2>
          <p>写下第一条创作指令。你可以先上传参考图，也可以直接从文字开始。</p>
          <button @click="loginOpen = !authenticated"><PhShieldCheck :size="18" />{{ authenticated ? 'Codex 已连接' : '先连接 Codex' }}</button>
        </div>

        <div v-else class="masonry-grid">
          <article v-for="item in generated" :key="item.path" class="art-card">
            <button class="art-preview" @click="previewPath = item.path"><img :src="imageUrl(item.path)" :alt="item.job.prompt" loading="lazy" /></button>
            <div class="art-meta"><p>{{ item.job.prompt.replace(/\s--ar\s\S+$/, '') }}</p><div><span>{{ statusLabel(item.job.status) }}</span><a :href="batchDownloadUrl(item.batchId)" title="下载批次"><PhDownloadSimple :size="17" /></a></div></div>
          </article>
          <article v-for="job in activeJobs" :key="job.job_id" class="art-card generating-card">
            <div class="generation-canvas"><span class="scanner" /><PhSparkle :size="28" weight="fill" /></div>
            <div class="art-meta"><p>{{ job.prompt.replace(/\s--ar\s\S+$/, '') }}</p><div><span>{{ statusLabel(job.status) }}</span><button @click="api.cancelJob(job.job_id).then(loadWorkspace)"><PhX :size="16" /></button></div></div>
          </article>
        </div>
      </section>

      <section v-if="batches.length" class="history-section">
        <div class="gallery-heading"><div><h2>最近批次</h2><span>{{ batches.length }}</span></div></div>
        <div class="batch-list">
          <div v-for="batch in batches.slice(0, 8)" :key="batch.batch_id" class="batch-row">
            <span class="batch-state" :class="batch.status" /><div><strong>{{ batch.jobs?.[0]?.prompt.replace(/\s--ar\s\S+$/, '') || batch.batch_id }}</strong><small>{{ shortDate(batch.created_at) }} · {{ batch.total }} 个任务</small></div>
            <span>{{ batch.succeeded }} 完成<span v-if="batch.failed"> · {{ batch.failed }} 失败</span></span>
            <a v-if="batch.succeeded" :href="batchDownloadUrl(batch.batch_id)"><PhDownloadSimple :size="18" />下载</a>
          </div>
        </div>
      </section>
    </main>

    <div v-if="loginOpen" class="modal-layer" @mousedown.self="loginOpen = false">
      <section class="login-dialog" role="dialog" aria-modal="true" aria-labelledby="login-title">
        <button class="dialog-close" @click="loginOpen = false"><PhX :size="20" /></button>
        <div class="login-symbol"><PhShieldCheck :size="30" weight="fill" /></div>
        <span class="eyebrow">安全连接</span><h2 id="login-title">在浏览器中登录 Codex</h2>
        <p>使用一次性设备码完成 ChatGPT 登录。凭据由 Codex CLI 保存在本机，网页不会读取或保存令牌。</p>

        <template v-if="!loginState">
          <div class="login-note"><PhMonitor :size="20" /><span><strong>适用于 Windows、macOS 与 Docker</strong><small>远程环境无需回调端口</small></span></div>
          <button class="primary-action" @click="beginLogin"><PhArrowSquareOut :size="19" />获取登录码</button>
        </template>
        <template v-else>
          <div v-if="loginState.user_code" class="device-code"><small>一次性代码</small><strong>{{ loginState.user_code }}</strong><button @click="copyCode"><PhCopy :size="18" />复制</button></div>
          <a v-if="loginState.verification_url" class="verification-link" :href="loginState.verification_url" target="_blank" rel="noreferrer"><PhArrowSquareOut :size="19" />打开登录页面</a>
          <div class="login-progress" :class="{ success: loginState.success }"><PhCheck v-if="loginState.success" :size="18" weight="bold" /><PhWarningCircle v-else-if="loginState.completed" :size="18" /><PhCircleNotch v-else class="spin" :size="18" /><span>{{ loginState.success ? '登录成功，正在连接工作台' : loginState.completed ? loginState.message : '等待你在浏览器中确认' }}</span></div>
          <button v-if="loginState.completed && !loginState.success" class="primary-action" @click="beginLogin"><PhArrowSquareOut :size="19" />重新获取登录码</button>
          <pre v-if="!loginState.user_code && !loginState.completed && loginState.message">{{ loginState.message }}</pre>
        </template>
      </section>
    </div>

    <div v-if="previewPath" class="preview-layer" @click="previewPath = null"><button><PhX :size="22" /></button><img :src="imageUrl(previewPath)" alt="生成结果预览" /></div>
  </div>
</template>
