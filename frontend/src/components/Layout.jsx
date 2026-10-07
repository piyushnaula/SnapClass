import { useEffect, useState } from 'react'
import { Link } from '../router.jsx'
import DisplaySettings from './DisplaySettings.jsx'
import HelpDialog from './HelpDialog.jsx'
import { IconBook, IconChart, IconGrid, IconHelp, IconLogout, IconMenu, IconScanFace, IconTextSize, IconX } from './Icons.jsx'
import Logo from './Logo.jsx'
import { initials } from './ui.jsx'

// Menu items per role. `match` lists the URL prefixes that highlight the item.
const NAV_ITEMS = {
  TEACHER: [{ to: '/', label: 'My classes', icon: IconBook, match: ['/classes', '/sessions'] }],
  STUDENT: [
    { to: '/', label: 'My attendance', icon: IconChart, match: [] },
    { to: '/biometrics', label: 'Face setup', icon: IconScanFace, match: ['/biometrics'] },
  ],
  ADMIN: [{ to: '/', label: 'Dashboard', icon: IconGrid, match: [] }],
}

const ROLE_LABELS = { TEACHER: 'Teacher', STUDENT: 'Student', ADMIN: 'Administrator' }

function isActive(item, path) {
  if (item.to === '/' && path === '/') return true
  return item.match.some((prefix) => path.startsWith(prefix))
}

// Header + page container used by every page.
export default function Layout({ user, path, onLogout, children }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [displayOpen, setDisplayOpen] = useState(false)

  // Close the phone menu after moving to another page.
  useEffect(() => setMenuOpen(false), [path])

  const items = user ? NAV_ITEMS[user.role] : []

  // Help, text size and log out: shown as labelled buttons on big screens,
  // and inside the menu on phones.
  const actions = (
    <>
      <button type="button" className="header-action" onClick={() => setHelpOpen(true)}>
        <IconHelp /> <span className="header-action-label">Help</span>
      </button>
      <button type="button" className="header-action" onClick={() => setDisplayOpen(true)}>
        <IconTextSize /> <span className="header-action-label">Text size</span>
      </button>
      {user && (
        <button type="button" className="header-action" onClick={onLogout}>
          <IconLogout /> <span className="header-action-label">Log out</span>
        </button>
      )}
    </>
  )

  return (
    <div className="app">
      {/* Lets keyboard and screen-reader users jump straight to the page content. */}
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>

      <header className="header">
        <div className="header-inner">
          <Link to="/" className="brand" aria-label="SnapClass home">
            <Logo size={30} />
          </Link>

          <nav className={menuOpen ? 'nav open' : 'nav'} aria-label="Main navigation">
            {items.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className={isActive(item, path) ? 'nav-link active' : 'nav-link'}
                aria-current={isActive(item, path) ? 'page' : undefined}
              >
                <item.icon />
                {item.label}
              </Link>
            ))}
            <div className="nav-actions">{actions}</div>
          </nav>

          <div className="header-right">
            <div className="header-actions">{actions}</div>
            {user && (
              <div className="user-chip" title={user.email}>
                <span className="avatar" aria-hidden="true">
                  {initials(user.full_name)}
                </span>
                <span className="user-meta">
                  <strong>{user.full_name}</strong>
                  <span>{ROLE_LABELS[user.role]}</span>
                </span>
              </div>
            )}
            <button
              type="button"
              className="menu-toggle"
              aria-label={menuOpen ? 'Close menu' : 'Open menu'}
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(!menuOpen)}
            >
              {menuOpen ? <IconX /> : <IconMenu />}
              <span>Menu</span>
            </button>
          </div>
        </div>
      </header>

      <main className="container" id="main-content" tabIndex={-1}>
        {children}
      </main>

      <footer className="footer">
        <span>SnapClass</span>
        <span>
          Need help?{' '}
          <button type="button" className="link-button" onClick={() => setHelpOpen(true)}>
            Read the quick guide
          </button>
        </span>
      </footer>

      <HelpDialog open={helpOpen} onClose={() => setHelpOpen(false)} role={user?.role || 'STUDENT'} />
      <DisplaySettings open={displayOpen} onClose={() => setDisplayOpen(false)} />
    </div>
  )
}
