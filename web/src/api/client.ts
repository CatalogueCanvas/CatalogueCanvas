export interface Item {
  id: string
  content_hash: string
  title: string
  note: string
  mime_type: string | null
  preview_path: string | null
  preview_url: string | null
  other_files: string[]
  download_urls: { name: string; url: string; type: 'image' | 'text' | 'other' }[]
  tags: string[]
  collection_ids: string[]
  raw_meta: Record<string, unknown>
  ingested_at: string
  imported_at: string | null
  width: number | null
  height: number | null
  library_id: string
}

export interface Library {
  id: string
  name: string
  path: string
  is_default: boolean
  created_at: string
  item_count: number
  path_ok: boolean
}

export interface Collection {
  id: string
  title: string
  description: string
  cover_item_id: string | null
  is_system: boolean
  created_at: string
}

export type PortfolioStyle = 'ledger' | 'kinetic' | 'brutalist' | 'riso'

// Layout is orthogonal to style: any style can be published as either a
// paginated slide deck or a continuous scrolling page.
export type PortfolioLayout = 'slide' | 'scroll'

export interface Portfolio {
  id: string
  slug: string
  title: string
  description: string
  item_ids: string[]
  is_public: boolean
  style: PortfolioStyle
  layout: PortfolioLayout
  watermark_enabled: boolean
  watermark_text: string
  share_token: string
  created_at: string
}

export interface PublicPortfolio {
  title: string
  description: string
  slug: string
  style: PortfolioStyle
  layout: PortfolioLayout
  items: Item[]
}

export interface DescribeResult {
  descriptions: string[]
  summary: string
}

// Single source of truth for turning a DescribeResult into a note string, so
// every code path (single-item and batch) stores the identical, full result.
export const describeResultToNote = (r: DescribeResult): string =>
  [r.summary, '', ...r.descriptions.map((d) => `- ${d}`)].join('\n')

export type Theme = 'light' | 'dark'
export type Accent = 'default' | 'cobalt' | 'terracotta' | 'forest' | 'mint' | 'ink'
export type NavLayout = 'top' | 'side'
export type Density = 'airy' | 'balanced' | 'dense'

export interface AppSettings {
  llm_api_url: string
  llm_model: string
  llm_item_type: string
  llm_summary_focus: string
  llm_bullet_count: string
  llm_bullet_max_words: string
  llm_auto_generate: string
  llm_prompt_template: string
  llm_prompt_template_default: string
  theme: Theme
  accent: Accent
  nav: NavLayout
  density: Density
  favorites_enabled: string
  multi_user_enabled: string
  update_check_enabled: string
  stats: { total_items: number; total_collections: number; missing_preview: number }
}

export interface VersionInfo {
  current: string
  latest: string | null
  update_available: boolean
  checked: boolean
  last_checked: string | null
}

export type Role = 'admin' | 'reader'

export interface MeResponse {
  authenticated: boolean
  role: Role | null
  username: string | null
  multi_user: boolean
}

export interface User {
  id: number
  username: string
  role: Role
  created_at: string
}

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

function readCookie(name: string): string | null {
  const prefix = name + '='
  for (const part of document.cookie.split('; ')) {
    if (part.startsWith(prefix)) return decodeURIComponent(part.slice(prefix.length))
  }
  return null
}

// Attach the double-submit CSRF header for state-changing requests so the
// server can match it against the cc_csrf cookie.
function csrfHeaders(method?: string): Record<string, string> {
  if (!method || !UNSAFE_METHODS.has(method.toUpperCase())) return {}
  const token = readCookie('cc_csrf')
  return token ? { 'X-CSRF-Token': token } : {}
}

export { csrfHeaders }

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...csrfHeaders(options.method),
      ...(options.headers || {}),
    },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export { ApiError }

// --- auth ---
export const login = (password: string, username?: string) =>
  request<{ ok: boolean; role: Role; username: string | null }>('/api/login', {
    method: 'POST',
    body: JSON.stringify(username ? { username, password } : { password }),
  })

export const logout = () => request<{ ok: boolean }>('/api/logout', { method: 'POST' })

export const me = () => request<MeResponse>('/api/me')

// --- users ---
export const listUsers = () => request<User[]>('/api/users')

export const createUser = (data: { username: string; password: string; role: Role }) =>
  request<User>('/api/users', { method: 'POST', body: JSON.stringify(data) })

export const updateUser = (id: number, fields: { username?: string; password?: string; role?: Role }) =>
  request<User>(`/api/users/${id}`, { method: 'PUT', body: JSON.stringify(fields) })

export const deleteUser = (id: number) =>
  request<{ ok: boolean }>(`/api/users/${id}`, { method: 'DELETE' })

// --- items ---
export const listItems = () => request<Item[]>('/api/items')

export const searchItems = (q: string) =>
  request<Item[]>(`/api/items/search?q=${encodeURIComponent(q)}`)

export const getItem = (id: string) => request<Item>(`/api/items/${id}`)

export const updateItem = (id: string, fields: Partial<Pick<Item, 'title' | 'note' | 'tags' | 'collection_ids' | 'raw_meta'>>) =>
  request<Item>(`/api/items/${id}`, { method: 'PATCH', body: JSON.stringify(fields) })

export const favoriteItem = (id: string) => request<Item>(`/api/items/${id}/favorite`, { method: 'POST' })

export const unfavoriteItem = (id: string) => request<Item>(`/api/items/${id}/favorite`, { method: 'DELETE' })

export const deleteItem = (id: string) => request<{ ok: boolean }>(`/api/items/${id}`, { method: 'DELETE' })

export const uploadItem = async (file: File, libraryId?: string): Promise<{ item: Item | null; created: boolean; note: string | null }> => {
  const form = new FormData()
  form.append('file', file)
  if (libraryId) form.append('library_id', libraryId)
  const res = await fetch('/api/items/upload', { method: 'POST', credentials: 'include', headers: csrfHeaders('POST'), body: form })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.detail || res.statusText)
  }
  return res.json()
}

export interface DescribeParams {
  api_url: string
  model: string
  item_type?: string
  summary_focus?: string
  bullet_count?: number
  bullet_max_words?: number
  prompt_template?: string
  api_key?: string
}

export const describeItem = (id: string, params: DescribeParams) =>
  request<DescribeResult>(`/api/items/${id}/describe`, { method: 'POST', body: JSON.stringify(params) })

// --- collections ---
export const listCollections = () => request<Collection[]>('/api/collections')

export const getCollection = (id: string) => request<Collection>(`/api/collections/${id}`)

export const createCollection = (data: { title: string; description?: string; cover_item_id?: string | null; id?: string }) =>
  request<Collection>('/api/collections', { method: 'POST', body: JSON.stringify(data) })

export const updateCollection = (id: string, fields: Partial<Pick<Collection, 'title' | 'description' | 'cover_item_id'>>) =>
  request<Collection>(`/api/collections/${id}`, { method: 'PATCH', body: JSON.stringify(fields) })

export const deleteCollection = (id: string) => request<{ ok: boolean }>(`/api/collections/${id}`, { method: 'DELETE' })

export const getCollectionItems = (id: string) => request<Item[]>(`/api/collections/${id}/items`)

// --- portfolios ---
export const listPortfolios = () => request<Portfolio[]>('/api/portfolios')

export const getPortfolio = (id: string) => request<Portfolio>(`/api/portfolios/${id}`)

export const createPortfolio = (data: { title: string; description?: string; slug?: string; item_ids?: string[]; is_public?: boolean; style?: PortfolioStyle; layout?: PortfolioLayout; watermark_enabled?: boolean; watermark_text?: string }) =>
  request<Portfolio>('/api/portfolios', { method: 'POST', body: JSON.stringify(data) })

export const updatePortfolio = (id: string, fields: Partial<Pick<Portfolio, 'title' | 'description' | 'slug' | 'item_ids' | 'is_public' | 'style' | 'layout' | 'watermark_enabled' | 'watermark_text'>>) =>
  request<Portfolio>(`/api/portfolios/${id}`, { method: 'PATCH', body: JSON.stringify(fields) })

export const deletePortfolio = (id: string) => request<{ ok: boolean }>(`/api/portfolios/${id}`, { method: 'DELETE' })

export const exportPortfolioStatic = (
  id: string,
  opts?: { quality?: number; max_edge?: number | null },
) => downloadPost(`/api/portfolios/${id}/export`, opts ?? undefined, 'portfolio-site.zip')

export const mintShareToken = (id: string) =>
  request<{ share_token: string }>(`/api/portfolios/${id}/share-token`, { method: 'POST' })

export const clearShareToken = (id: string) =>
  request<{ ok: boolean }>(`/api/portfolios/${id}/share-token`, { method: 'DELETE' })

export const getPublicPortfolio = (slug: string, token?: string) =>
  request<PublicPortfolio>(token ? `/api/p/${slug}/${token}` : `/api/p/${slug}`)

// --- settings ---
export const getSettings = () => request<AppSettings>('/api/settings')

export const getAppearance = () =>
  request<Pick<AppSettings, 'theme' | 'accent' | 'nav' | 'density' | 'favorites_enabled' | 'multi_user_enabled'>>('/api/settings/appearance')

export const updateSettings = (fields: Partial<Pick<AppSettings, 'llm_api_url' | 'llm_model' | 'llm_item_type' | 'llm_summary_focus' | 'llm_bullet_count' | 'llm_bullet_max_words' | 'llm_auto_generate' | 'llm_prompt_template' | 'theme' | 'accent' | 'nav' | 'density' | 'favorites_enabled' | 'multi_user_enabled' | 'update_check_enabled'>>) =>
  request<AppSettings>('/api/settings', { method: 'PUT', body: JSON.stringify(fields) })

export const getVersion = (force = false) =>
  request<VersionInfo>('/api/version' + (force ? '?force=true' : ''))

export const exportDatabase = () =>
  downloadPost('/api/settings/export/db', undefined, 'catalogue.db')

export const exportFullBackup = () =>
  downloadPost('/api/settings/export/all', undefined, 'cataloguecanvas-backup.zip')

export const downloadDiagnostics = () =>
  downloadPost('/api/settings/diagnostics', undefined, 'cataloguecanvas-diagnostics.md')

// --- CSV batch metadata round-trip ---
export interface CsvFieldChange<T> {
  old: T
  new: T
}

export interface CsvRowChange {
  id: string
  title?: CsvFieldChange<string>
  note?: CsvFieldChange<string>
  tags?: CsvFieldChange<string[]>
}

export interface CsvPreview {
  to_update: CsvRowChange[]
  skipped: string[]
  unchanged: string[]
  total_rows: number
}

export interface CsvApplyResult {
  updated: string[]
  skipped: string[]
  unchanged: string[]
  backup: string | null
}

// Trigger a browser download from a POST endpoint. Sensitive exports are POST
// (CSRF-protected) so they can't be fetched with a bare cross-site GET/anchor.
async function downloadPost(path: string, body?: unknown, fallbackName = 'download'): Promise<void> {
  const res = await fetch(path, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...csrfHeaders('POST') },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}))
    throw new ApiError(res.status, errBody.detail || res.statusText)
  }
  const disposition = res.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  const name = match ? match[1] : fallbackName
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export const exportItemsCsv = (q?: string) =>
  downloadPost('/api/items/export/csv', { q: q ?? '' }, 'catalogue-metadata.csv')

const postCsv = async <T>(path: string, file: File): Promise<T> => {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(path, { method: 'POST', credentials: 'include', headers: csrfHeaders('POST'), body: form })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.detail || res.statusText)
  }
  return res.json()
}

export const previewCsvImport = (file: File) =>
  postCsv<CsvPreview>('/api/items/import/csv/preview', file)

export const applyCsvImport = (file: File) =>
  postCsv<CsvApplyResult>('/api/items/import/csv', file)

export interface CsvBackup {
  filename: string
  size: number
  created_at: string
}

export const DELETE_BACKUP_CONFIRM = 'delete metadata backup'

export const listCsvBackups = () =>
  request<{ backups: CsvBackup[] }>('/api/items/import/csv/backups')

export const deleteCsvBackup = (filename: string, confirm: string) =>
  request<{ ok: boolean }>(`/api/items/import/csv/backups/${encodeURIComponent(filename)}`, {
    method: 'DELETE',
    body: JSON.stringify({ confirm }),
  })

export const itemArchiveUrl = (id: string) => `/api/items/${id}/archive`

export const itemMetadataUrl = (id: string) => `/api/items/${id}/metadata`

// --- libraries ---
export const listLibraries = () => request<Library[]>('/api/libraries')

export const createLibrary = (data: { name: string; path: string; is_default?: boolean }) =>
  request<Library>('/api/libraries', { method: 'POST', body: JSON.stringify(data) })

export const updateLibrary = (id: string, fields: Partial<Pick<Library, 'name' | 'path'>>) =>
  request<Library>(`/api/libraries/${id}`, { method: 'PUT', body: JSON.stringify(fields) })

export const setDefaultLibrary = (id: string) =>
  request<Library>(`/api/libraries/${id}/default`, { method: 'POST' })

export const deleteLibrary = (id: string) =>
  request<{ ok: boolean }>(`/api/libraries/${id}`, { method: 'DELETE' })

// --- bulk item actions ---
export const bulkClearNotes = (item_ids: string[]) =>
  request<{ updated: string[]; missing: string[] }>('/api/items/bulk/clear-notes', { method: 'POST', body: JSON.stringify({ item_ids }) })

export const bulkAddTags = (item_ids: string[], tags: string[]) =>
  request<{ updated: string[]; missing: string[] }>('/api/items/bulk/tags', { method: 'POST', body: JSON.stringify({ item_ids, tags }) })

export const bulkFavorite = (item_ids: string[]) =>
  request<{ updated: string[]; missing: string[] }>('/api/items/bulk/favorite', { method: 'POST', body: JSON.stringify({ item_ids }) })

export const bulkUnfavorite = (item_ids: string[]) =>
  request<{ updated: string[]; missing: string[] }>('/api/items/bulk/unfavorite', { method: 'POST', body: JSON.stringify({ item_ids }) })

export const updatePortfolioItems = (p_id: string, item_ids: string[], action: 'add' | 'remove') =>
  request<Portfolio>(`/api/portfolios/${p_id}/items`, { method: 'POST', body: JSON.stringify({ item_ids, action }) })

export const downloadBulkArchive = async (item_ids: string[]) => {
  const res = await fetch('/api/items/archive', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...csrfHeaders('POST') },
    body: JSON.stringify({ item_ids }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new ApiError(res.status, body.detail || res.statusText)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `items_bulk_${Date.now()}.zip`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
