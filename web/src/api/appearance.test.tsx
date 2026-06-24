import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { ACCENT_PRESETS, AppearanceProvider, useAppearance } from './appearance'
import * as api from './client'

vi.mock('./client', () => ({
  getAppearance: vi.fn(),
  updateSettings: vi.fn(),
}))

const mocked = vi.mocked(api)

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <AppearanceProvider>{children}</AppearanceProvider>
)

afterEach(() => vi.clearAllMocks())

describe('ACCENT_PRESETS', () => {
  it('defines a preset for every accent', () => {
    expect(Object.keys(ACCENT_PRESETS)).toContain('cobalt')
    expect(ACCENT_PRESETS.default).toEqual({})
  })
})

describe('useAppearance', () => {
  it('throws outside the provider', () => {
    expect(() => renderHook(() => useAppearance())).toThrow(/within AppearanceProvider/)
  })

  it('loads appearance from the API on mount', async () => {
    mocked.getAppearance.mockResolvedValue({
      theme: 'dark', accent: 'cobalt', nav: 'side', density: 'dense',
      favorites_enabled: 'false', multi_user_enabled: 'false',
    })
    const { result } = renderHook(() => useAppearance(), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.appearance.theme).toBe('dark')
    expect(result.current.appearance.favoritesEnabled).toBe(false)
  })

  it('falls back to defaults when the API fails', async () => {
    mocked.getAppearance.mockRejectedValue(new Error('offline'))
    const { result } = renderHook(() => useAppearance(), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.appearance.theme).toBe('light')
  })

  it('setAppearance updates state and persists, mapping favoritesEnabled', async () => {
    mocked.getAppearance.mockResolvedValue({
      theme: 'light', accent: 'default', nav: 'top', density: 'balanced',
      favorites_enabled: 'true', multi_user_enabled: 'false',
    })
    mocked.updateSettings.mockResolvedValue({} as never)
    const { result } = renderHook(() => useAppearance(), { wrapper })
    await waitFor(() => expect(result.current.loading).toBe(false))

    await act(async () => {
      await result.current.setAppearance({ theme: 'dark', favoritesEnabled: false })
    })
    expect(result.current.appearance.theme).toBe('dark')
    expect(mocked.updateSettings).toHaveBeenCalledWith(
      expect.objectContaining({ theme: 'dark', favorites_enabled: 'false' }),
    )
  })
})
