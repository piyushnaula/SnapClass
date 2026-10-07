import { useState } from 'react'
import { api } from '../api.js'
import { IconHash, IconUser } from '../components/Icons.jsx'
import Logo from '../components/Logo.jsx'
import { ErrorBox, PasswordInput } from '../components/ui.jsx'
import { Link } from '../router.jsx'

// Shared form: used on its own page and inside the class invite page.
export function RegisterForm({ onRegistered, submitLabel = 'Create my account' }) {
  const [form, setForm] = useState({ student_id: '', full_name: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      onRegistered(await api('/auth/register', { method: 'POST', body: form }))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <ErrorBox message={error} />
      <label className="field">
        <span>Student ID</span>
        <div className="input-icon">
          <IconHash />
          <input
            value={form.student_id}
            onChange={update('student_id')}
            required
            minLength={3}
            maxLength={20}
            pattern="[A-Za-z0-9\-]+"
            title="Letters, numbers and '-' only"
            autoCapitalize="characters"
            autoComplete="username"
            placeholder="e.g. 23CSE041"
          />
        </div>
        <small className="muted">The ID printed on your college ID card. You will sign in with it.</small>
      </label>
      <label className="field">
        <span>Full name</span>
        <div className="input-icon">
          <IconUser />
          <input value={form.full_name} onChange={update('full_name')} required minLength={2} autoComplete="name" />
        </div>
        <small className="muted">As it appears in college records, so your teacher recognises it.</small>
      </label>
      <label className="field">
        <span>Choose a password</span>
        <PasswordInput value={form.password} onChange={update('password')} minLength={8} autoComplete="new-password" />
        <small className="muted">At least 8 characters. Do not reuse your ERP or email password.</small>
      </label>
      <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={busy}>
        {busy ? 'Creating account…' : submitLabel}
      </button>
    </form>
  )
}

// Students create their own SnapClass account with their student ID.
export default function RegisterPage({ onRegistered }) {
  return (
    <div className="auth-page single">
      <main className="auth-main" id="main-content">
        <div className="auth-card">
          <div className="auth-logo">
            <Logo size={36} />
          </div>
          <h2>Create your student account</h2>
          <p className="muted">Takes one minute. Next, you will set up your face so attendance can be marked from the class photo.</p>
          <RegisterForm onRegistered={onRegistered} />
          <p className="center auth-switch">
            Already have an account? <Link to="/">Sign in</Link>
          </p>
        </div>
      </main>
    </div>
  )
}
