import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './api/auth'
import { ACCENT_PRESETS, useAppearance } from './api/appearance'
import { SelectionProvider } from './api/selection'
import { ActivityProvider } from './api/activity'
import { ActivityTray } from './components/ActivityTray'
import { Nav } from './components/Nav'
import { Footer } from './components/Footer'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { ItemEdit } from './pages/ItemEdit'
import { Collections } from './pages/Collections'
import { CollectionEdit } from './pages/CollectionEdit'
import { Portfolios } from './pages/Portfolios'
import { PortfolioEdit } from './pages/PortfolioEdit'
import { Settings } from './pages/Settings'
import { Upload } from './pages/Upload'
import { NotFound } from './pages/NotFound'
import { Deck } from './portfolio/Deck'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { authenticated, loading } = useAuth()
  if (loading) return null
  if (!authenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AdminRoute({ children }: { children: React.ReactNode }) {
  const { authenticated, isAdmin, loading } = useAuth()
  if (loading) return null
  if (!authenticated) return <Navigate to="/login" replace />
  if (!isAdmin) return <Navigate to="/" replace />
  return <>{children}</>
}

function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <div className="cc-shell">
        <Nav />
        <div className="cc-content">
          <main className="cc-main">{children}</main>
          <Footer />
        </div>
      </div>
    </ProtectedRoute>
  )
}

function App() {
  const { appearance } = useAppearance()
  const preset = ACCENT_PRESETS[appearance.accent]
  const accentStyle = preset.accent
    ? { '--accent': preset.accent, '--accent-dim': preset.dim, '--accent-contrast': preset.contrast } as React.CSSProperties
    : undefined

  return (
    <div
      className="cc-app"
      data-direction="grid"
      data-theme={appearance.theme}
      data-nav={appearance.nav}
      data-density={appearance.density}
      style={accentStyle}
    >
      <SelectionProvider>
        <ActivityProvider>
        <Routes>
          <Route path="/login" element={<><Login /><Footer /></>} />
          <Route path="/p/:slug" element={<Deck />} />
          <Route path="/" element={<AdminLayout><Dashboard /></AdminLayout>} />
          <Route path="/items/:id" element={<AdminLayout><ItemEdit /></AdminLayout>} />
          <Route path="/collections" element={<AdminLayout><Collections /></AdminLayout>} />
          <Route path="/collections/:id" element={<AdminLayout><CollectionEdit /></AdminLayout>} />
          <Route path="/portfolios" element={<AdminLayout><Portfolios /></AdminLayout>} />
          <Route path="/portfolios/:id" element={<AdminLayout><AdminRoute><PortfolioEdit /></AdminRoute></AdminLayout>} />
          <Route path="/upload" element={<AdminLayout><AdminRoute><Upload /></AdminRoute></AdminLayout>} />
          <Route path="/settings" element={<AdminLayout><AdminRoute><Settings /></AdminRoute></AdminLayout>} />
          <Route path="*" element={<AdminLayout><NotFound /></AdminLayout>} />
        </Routes>
        <ActivityTray />
        </ActivityProvider>
      </SelectionProvider>
    </div>
  )
}

export default App
