import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest'
import * as api from './client'
import { ApiError, csrfHeaders } from './client'

type FetchArgs = [string, RequestInit]

function mockFetch(response: Partial<Response> & { jsonBody?: unknown }): Mock<(...a: FetchArgs) => Promise<Response>> {
  const res = {
    ok: response.ok ?? true,
    status: response.status ?? 200,
    statusText: response.statusText ?? 'OK',
    headers: response.headers ?? new Headers(),
    json: async () => response.jsonBody ?? {},
    blob: async () => new Blob(['x']),
  } as unknown as Response
  const spy: Mock<(...a: FetchArgs) => Promise<Response>> = vi.fn(async () => res)
  vi.stubGlobal('fetch', spy)
  return spy
}

// The captured RequestInit types body/headers broadly; these narrow them for
// assertions in tests where we control exactly what the client sends.
function bodyJson(opts: RequestInit): unknown {
  return JSON.parse(opts.body as string)
}
function header(opts: RequestInit, name: string): string | undefined {
  return (opts.headers as Record<string, string>)?.[name]
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  document.cookie = 'cc_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT'
})

describe('csrfHeaders / readCookie', () => {
  it('returns no header for safe methods', () => {
    document.cookie = 'cc_csrf=tok123'
    expect(csrfHeaders('GET')).toEqual({})
    expect(csrfHeaders()).toEqual({})
  })

  it('attaches the CSRF header for unsafe methods when cookie present', () => {
    document.cookie = 'cc_csrf=tok123'
    expect(csrfHeaders('POST')).toEqual({ 'X-CSRF-Token': 'tok123' })
    expect(csrfHeaders('delete')).toEqual({ 'X-CSRF-Token': 'tok123' })
  })

  it('returns empty when no cookie set', () => {
    expect(csrfHeaders('POST')).toEqual({})
  })
})

describe('request', () => {
  it('GET builds the right URL and parses JSON', async () => {
    const spy = mockFetch({ jsonBody: [{ id: 'a' }] })
    const items = await api.listItems()
    expect(items).toEqual([{ id: 'a' }])
    expect(spy).toHaveBeenCalledWith('/api/items', expect.objectContaining({
      credentials: 'include',
    }))
  })

  it('encodes search queries', async () => {
    const spy = mockFetch({ jsonBody: [] })
    await api.searchItems('a b/c')
    expect(spy.mock.calls[0][0]).toBe('/api/items/search?q=a%20b%2Fc')
  })

  it('sends POST body and CSRF header for login', async () => {
    document.cookie = 'cc_csrf=csrf1'
    const spy = mockFetch({ jsonBody: { ok: true, role: 'admin', username: null } })
    await api.login('pw', 'alice')
    const [, opts] = spy.mock.calls[0]
    expect(opts.method).toBe('POST')
    expect(bodyJson(opts)).toEqual({ username: 'alice', password: 'pw' })
    expect(header(opts, 'X-CSRF-Token')).toBe('csrf1')
  })

  it('login without username omits the field', async () => {
    const spy = mockFetch({ jsonBody: { ok: true, role: 'admin', username: null } })
    await api.login('pw')
    expect(bodyJson(spy.mock.calls[0][1])).toEqual({ password: 'pw' })
  })

  it('returns undefined on 204', async () => {
    mockFetch({ status: 204 })
    const result = await api.logout()
    expect(result).toBeUndefined()
  })

  it('throws ApiError with detail from body on non-2xx', async () => {
    mockFetch({ ok: false, status: 403, jsonBody: { detail: 'nope' } })
    await expect(api.me()).rejects.toMatchObject({ status: 403, message: 'nope' })
  })

  it('falls back to statusText when body has no detail', async () => {
    mockFetch({ ok: false, status: 500, statusText: 'Server Error', jsonBody: {} })
    await expect(api.me()).rejects.toMatchObject({ status: 500, message: 'Server Error' })
  })
})

describe('resource builders', () => {
  it('updateItem issues PATCH to the item URL', async () => {
    const spy = mockFetch({ jsonBody: {} })
    await api.updateItem('apple-001', { title: 'X' })
    const [url, opts] = spy.mock.calls[0]
    expect(url).toBe('/api/items/apple-001')
    expect(opts.method).toBe('PATCH')
  })

  it('deleteCollection issues DELETE', async () => {
    const spy = mockFetch({ jsonBody: { ok: true } })
    await api.deleteCollection('col1')
    expect(spy.mock.calls[0][0]).toBe('/api/collections/col1')
    expect(spy.mock.calls[0][1].method).toBe('DELETE')
  })

  it('createPortfolio posts the payload', async () => {
    const spy = mockFetch({ jsonBody: {} })
    await api.createPortfolio({ title: 'P', is_public: true })
    expect(bodyJson(spy.mock.calls[0][1])).toMatchObject({ title: 'P', is_public: true })
  })

  it('bulkAddTags posts ids and tags', async () => {
    const spy = mockFetch({ jsonBody: { updated: [], missing: [] } })
    await api.bulkAddTags(['a'], ['red'])
    expect(bodyJson(spy.mock.calls[0][1])).toEqual({ item_ids: ['a'], tags: ['red'] })
  })

  it('exposes URL helpers without fetching', () => {
    expect(api.itemArchiveUrl('x')).toBe('/api/items/x/archive')
    expect(api.itemMetadataUrl('x')).toBe('/api/items/x/metadata')
  })
})

describe('uploadItem (FormData)', () => {
  it('posts multipart form and returns json', async () => {
    const spy = mockFetch({ jsonBody: { item: null, created: false, note: 'dup' } })
    const file = new File(['data'], 'a.png', { type: 'image/png' })
    const result = await api.uploadItem(file, 'lib1')
    expect(result.note).toBe('dup')
    const [url, opts] = spy.mock.calls[0]
    expect(url).toBe('/api/items/upload')
    expect(opts.body).toBeInstanceOf(FormData)
  })

  it('throws ApiError on failed upload', async () => {
    mockFetch({ ok: false, status: 413, jsonBody: { detail: 'too big' } })
    const file = new File(['data'], 'a.png')
    await expect(api.uploadItem(file)).rejects.toBeInstanceOf(ApiError)
  })
})

describe('downloadPost', () => {
  beforeEach(() => {
    // jsdom lacks URL.createObjectURL / anchor click side effects.
    vi.stubGlobal('URL', Object.assign(URL, {
      createObjectURL: vi.fn(() => 'blob:x'),
      revokeObjectURL: vi.fn(),
    }))
  })

  it('derives the filename from Content-Disposition and clicks a link', async () => {
    const headers = new Headers({ 'Content-Disposition': 'attachment; filename="report.csv"' })
    mockFetch({ headers, jsonBody: {} })
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    await api.exportItemsCsv('q')
    expect(clickSpy).toHaveBeenCalled()
  })

  it('throws ApiError when the export fails', async () => {
    mockFetch({ ok: false, status: 500, jsonBody: { detail: 'boom' } })
    await expect(api.exportDatabase()).rejects.toBeInstanceOf(ApiError)
  })
})
