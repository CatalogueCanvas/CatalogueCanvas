// Context provider component and its hook/constants intentionally live together.
/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import * as api from './client'
import type { Accent, Density, NavLayout, Theme } from './client'

export interface AccentPreset {
  accent?: string
  dim?: string
  contrast?: string
}

export const ACCENT_PRESETS: Record<Accent, AccentPreset> = {
  default: {},
  cobalt: { accent: 'oklch(0.55 0.21 258)', dim: 'oklch(0.48 0.2 258)', contrast: 'oklch(0.99 0 0)' },
  terracotta: { accent: 'oklch(0.58 0.13 45)', dim: 'oklch(0.5 0.12 42)', contrast: 'oklch(0.98 0.01 84)' },
  forest: { accent: 'oklch(0.52 0.11 155)', dim: 'oklch(0.45 0.1 155)', contrast: 'oklch(0.98 0 0)' },
  mint: { accent: 'oklch(0.68 0.14 168)', dim: 'oklch(0.6 0.13 168)', contrast: 'oklch(0.18 0.02 168)' },
  ink: { accent: 'oklch(0.32 0.01 260)', dim: 'oklch(0.24 0.01 260)', contrast: 'oklch(0.98 0 0)' },
}

export interface Appearance {
  theme: Theme
  accent: Accent
  nav: NavLayout
  density: Density
  favoritesEnabled: boolean
}

const DEFAULT_APPEARANCE: Appearance = { theme: 'light', accent: 'default', nav: 'top', density: 'balanced', favoritesEnabled: true }

interface AppearanceContextValue {
  appearance: Appearance
  loading: boolean
  setAppearance: (changes: Partial<Appearance>) => Promise<void>
}

const AppearanceContext = createContext<AppearanceContextValue | null>(null)

export function AppearanceProvider({ children }: { children: ReactNode }) {
  const [appearance, setAppearanceState] = useState<Appearance>(DEFAULT_APPEARANCE)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getAppearance()
      .then((s) => { setAppearanceState({
        theme: s.theme,
        accent: s.accent,
        nav: s.nav,
        density: s.density,
        favoritesEnabled: s.favorites_enabled !== 'false',
      }) })
      .catch(() => { /* use defaults */ })
      .finally(() => { setLoading(false) })
  }, [])

  const setAppearance = async (changes: Partial<Appearance>) => {
    setAppearanceState((prev) => ({ ...prev, ...changes }))
    const { favoritesEnabled, ...rest } = changes
    const payload: Record<string, string> = { ...rest } as Record<string, string>
    if (favoritesEnabled !== undefined) payload.favorites_enabled = favoritesEnabled ? 'true' : 'false'
    await api.updateSettings(payload)
  }

  return (
    <AppearanceContext.Provider value={{ appearance, loading, setAppearance }}>
      {children}
    </AppearanceContext.Provider>
  )
}

export function useAppearance() {
  const ctx = useContext(AppearanceContext)
  if (!ctx) throw new Error('useAppearance must be used within AppearanceProvider')
  return ctx
}
