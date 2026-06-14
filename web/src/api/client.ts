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
  collection_id: string | null
  raw_meta: Record<string, unknown>
  ingested_at: string
  imported_at: string | null
}

export interface Collection {
  id: string
  title: string
  description: string
  cover_item_id: string | null
  created_at: string
}

export interface Portfolio {
  id: string
  slug: string
  title: string
  description: string
  item_ids: string[]
  is_public: boolean
  created_at: string
}

export interface PublicPortfolio {
  title: string
  description: string
  slug: string
  items: Item[]
}

export interface DescribeResult {
  descriptions: string[]
  summary: string
}

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
  stats: { total_items: number; total_collections: number; missing_preview: number }
}

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
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
export const login = (password: string) =>
  request<{ ok: boolean }>('/api/login', { method: 'POST', body: JSON.stringify({ password }) })

export const logout = () => request<{ ok: boolean }>('/api/logout', { method: 'POST' })

export const me = () => request<{ authenticated: boolean }>('/api/me')

// --- items ---
export const listItems = () => request<Item[]>('/api/items')

export const getItem = (id: string) => request<Item>(`/api/items/${id}`)

export const updateItem = (id: string, fields: Partial<Pick<Item, 'title' | 'note' | 'tags' | 'collection_id' | 'raw_meta'>>) =>
  request<Item>(`/api/items/${id}`, { method: 'PATCH', body: JSON.stringify(fields) })

export const deleteItem = (id: string) => request<{ ok: boolean }>(`/api/items/${id}`, { method: 'DELETE' })

export const uploadItem = async (file: File): Promise<{ item: Item | null; created: boolean; note: string | null }> => {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/api/items/upload', { method: 'POST', credentials: 'include', body: form })
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

// --- portfolios ---
export const listPortfolios = () => request<Portfolio[]>('/api/portfolios')

export const getPortfolio = (id: string) => request<Portfolio>(`/api/portfolios/${id}`)

export const createPortfolio = (data: { title: string; description?: string; slug?: string; item_ids?: string[]; is_public?: boolean }) =>
  request<Portfolio>('/api/portfolios', { method: 'POST', body: JSON.stringify(data) })

export const updatePortfolio = (id: string, fields: Partial<Pick<Portfolio, 'title' | 'description' | 'slug' | 'item_ids' | 'is_public'>>) =>
  request<Portfolio>(`/api/portfolios/${id}`, { method: 'PATCH', body: JSON.stringify(fields) })

export const deletePortfolio = (id: string) => request<{ ok: boolean }>(`/api/portfolios/${id}`, { method: 'DELETE' })

export const getPublicPortfolio = (slug: string) => request<PublicPortfolio>(`/api/p/${slug}`)

// --- settings ---
export const getSettings = () => request<AppSettings>('/api/settings')

export const updateSettings = (fields: Partial<Pick<AppSettings, 'llm_api_url' | 'llm_model' | 'llm_item_type' | 'llm_summary_focus' | 'llm_bullet_count' | 'llm_bullet_max_words' | 'llm_prompt_template' | 'theme' | 'accent' | 'nav' | 'density'>>) =>
  request<AppSettings>('/api/settings', { method: 'PUT', body: JSON.stringify(fields) })

export const itemArchiveUrl = (id: string) => `/api/items/${id}/archive`
