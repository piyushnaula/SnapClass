import { useState } from 'react'
import { api } from '../api.js'
import DisplaySettings from '../components/DisplaySettings.jsx'
import { IconCheckCircle, IconScanFace, IconShield, IconTextSize, IconUser } from '../components/Icons.jsx'
import Logo from '../components/Logo.jsx'
import { ErrorBox, PasswordInput } from '../components/ui.jsx'
import { Link } from '../router.jsx'

const FEATURES = [
  { icon: IconScanFace, title: 'Take one photo of the class', text: 'SnapClass finds the students of your class in the photo.' },
  { icon: IconCheckCircle, title: 'You always decide', text: 'You check the list and save it. Nothing is saved without you.' },
  { icon: IconShield, title: 'Private by design', text: 'Students give permission first and can remove their data at any time.' },
]

export default function LoginPage({ onLogin }) {
  const [loginId, setLoginId] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [displayOpen, setDisplayOpen] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const data = await api('/auth/login', { method: 'POST', body: { login_id: loginId, password } })
      onLogin(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      {/* Left side: what SnapClass does, in plain words (hidden on small screens). */}
      <aside className="auth-brand">
        <Logo size={40} />
        <h1>Take attendance with one class photo.</h1>
        <p className="muted">Take a photo, check the list, save. It is that simple.</p>
        <ul className="feature-list">
          {FEATURES.map((feature) => (
            <li key={feature.title}>
              <span className="feature-icon">
                <feature.icon size={20} />
              </span>
              <div>
                <strong>{feature.title}</strong>
                <span className="muted">{feature.text}</span>
              </div>
            </li>
          ))}
        </ul>
      </aside>

      {/* Right side: the sign-in form. */}
      <main className="auth-main" id="main-content">
        <form className="auth-card" onSubmit={handleSubmit}>
          <div className="auth-mobile-logo">
            <Logo size={36} />
          </div>
          <h2>Sign in</h2>
          <p className="muted">Students: use your student ID. Teachers: use your email.</p>
          <ErrorBox message={error} />

          <label className="field">
            <span>Student ID or email</span>
            <div className="input-icon">
              <IconUser />
              <input
                value={loginId}
                onChange={(e) => setLoginId(e.target.value)}
                required
                autoFocus
                autoComplete="username"
                autoCapitalize="none"
                placeholder="e.g. 23CSE041 or name@college.edu"
              />
            </div>
          </label>
          <label className="field">
            <span>Password</span>
            <PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>

          <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>

          <Link to="/register" className="btn btn-secondary btn-block btn-lg">
            New student? Create your account
          </Link>

          <div className="auth-help">
            <p>
              <strong>Forgot your password?</strong> Password reset is not available yet. Please contact your college&apos;s
              SnapClass administrator.
            </p>
          </div>

          <button type="button" className="link-button text-size-link" onClick={() => setDisplayOpen(true)}>
            <IconTextSize size={16} /> Text too small? Change text size
          </button>
        </form>
      </main>
      <DisplaySettings open={displayOpen} onClose={() => setDisplayOpen(false)} />
    </div>
  )
}
