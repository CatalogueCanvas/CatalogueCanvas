import { useEffect } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { useAuth } from '../api/auth'
import { useAppearance } from '../api/appearance'
import { useSelection } from '../api/selection'
import { Icon, type IconName } from './Icon'

function NavItem({ to, end, label, icon }: { to: string; end?: boolean; label: string; icon: IconName }) {
  return (
    <NavLink to={to} end={end} className="cc-nav-link">
      {({ isActive }) => (
        <span aria-current={isActive ? 'true' : undefined}>
          <Icon name={icon} size={17} />
          {label}
          {isActive && <span className="cc-nav-dot" />}
        </span>
      )}
    </NavLink>
  )
}

export function Nav() {
  const { authenticated, isAdmin, username, logout } = useAuth()
  const { appearance, setAppearance } = useAppearance()
  const { batchMode, toggleBatchMode } = useSelection()
  const location = useLocation()
  const onItemsPage = location.pathname === '/'
  const isDark = appearance.theme === 'dark'

  // Batch mode only applies on the Items page; leaving it resets any active
  // selection so no invisible stale state lingers.
  useEffect(() => {
    if (!onItemsPage && batchMode) toggleBatchMode()
  }, [onItemsPage, batchMode, toggleBatchMode])

  return (
    <nav className="cc-nav">
      <Link to="/" className="cc-logo">
        <svg className="cc-mark" viewBox="0 0 48 48" aria-hidden="true">
          <path d="M40 13 A16 16 0 1 0 40 35" fill="none" stroke="var(--text)" strokeWidth="3.4" strokeLinecap="round" />
          <path d="M34 19 A9 9 0 1 0 34 29" fill="none" stroke="var(--accent)" strokeWidth="3.4" strokeLinecap="round" />
        </svg>
        CatalogueCanvas
      </Link>
      <div className="cc-nav-links">
        <NavItem to="/" end label="Items" icon="items" />
        <NavItem to="/collections" label="Collections" icon="collections" />
        <NavItem to="/portfolios" label="Portfolios" icon="portfolios" />
        {isAdmin && <NavItem to="/upload" label="Upload" icon="upload" />}
        {isAdmin && <NavItem to="/settings" label="Settings/Admin" icon="settings" />}
      </div>
      <div className="cc-nav-spacer" />
      {authenticated && (
        <div className="cc-nav__foot">
          {onItemsPage && (
            <button
              className="cc-mode-btn"
              type="button"
              data-active={batchMode || undefined}
              onClick={toggleBatchMode}
            >
              {isAdmin ? 'Batch edit' : 'Select'}
            </button>
          )}
          <button
            className="cc-mode-btn"
            type="button"
            onClick={() => void setAppearance({ theme: isDark ? 'light' : 'dark' })}
          >
            <span className="cc-mode-ind" />
            {isDark ? 'Dark' : 'Light'}
          </button>
          {username && <span className="cc-nav__user" title={username}><Icon name="user" size={14} />{username}</span>}
          <button className="cc-btn cc-btn--ghost cc-btn--sm" onClick={() => void logout()}><Icon name="logout" size={15} />Log out</button>
        </div>
      )}
    </nav>
  )
}
