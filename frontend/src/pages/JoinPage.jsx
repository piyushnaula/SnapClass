import { useState } from 'react'
import { api } from '../api.js'
import { IconBook, IconCheckCircle, IconLink, IconUser } from '../components/Icons.jsx'
import { useToast } from '../components/Toast.jsx'
import { EmptyState, ErrorBox, PasswordInput, Skeleton } from '../components/ui.jsx'
import { useLoad } from '../hooks.js'
import { navigate } from '../router.jsx'
import { RegisterForm } from './RegisterPage.jsx'

// Students open this page from the teacher's invite link or QR code.
// Not signed in → create an account or sign in → joined automatically.
// Signed in as a student → one "Join" button.
export default function JoinPage({ code, user, onSignedIn }) {
  const { data: classInfo, error: loadError, loading } = useLoad(() => api(`/join/${code}`), [code])
  const [hasAccount, setHasAccount] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const toast = useToast()

  // Join the class with the (now) signed-in student, then go to the right next page.
  async function join() {
    setBusy(true)
    setError('')
    try {
      const result = await api(`/join/${code}`, { method: 'POST' })
      const status = await api('/me/biometrics')
      toast(result.already_joined ? `You are already in ${result.subject}.` : `You joined ${result.subject}.`)
      // New students go straight to face setup; others to their attendance.
      navigate(status.face_samples === 0 ? '/biometrics' : '/')
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  async function afterSignIn(data) {
    onSignedIn(data)
    if (data.user.role !== 'STUDENT') {
      setError('Only students can join a class. You are signed in as a teacher or administrator.')
      return
    }
    await join()
  }

  if (loading) return <Skeleton rows={4} />
  if (loadError) {
    return (
      <EmptyState icon={<IconLink size={28} />} title="This invite link does not work any more">
        It may have expired or been used too many times. Please ask your teacher for a new link.
      </EmptyState>
    )
  }

  const classHeader = (
    <div className="card-title-row">
      <span className="icon-tile">
        <IconBook size={22} />
      </span>
      <div>
        <p className="eyebrow">You are joining</p>
        <h2>{classInfo.subject}</h2>
        <p className="muted small">
          Section {classInfo.section} · Semester {classInfo.semester}
        </p>
      </div>
    </div>
  )

  // Already signed in.
  if (user) {
    return (
      <div className="narrow-page">
        <div className="card">
          {classHeader}
          <ErrorBox message={error} />
          {user.role === 'STUDENT' ? (
            <>
              <p className="muted">
                Signed in as <strong className="text-strong">{user.full_name}</strong> ({user.roll_no}).
              </p>
              <button type="button" className="btn btn-primary btn-block btn-lg" onClick={join} disabled={busy}>
                <IconCheckCircle /> {busy ? 'Joining…' : 'Join this class'}
              </button>
            </>
          ) : (
            <p className="muted">Only students can join a class. Please sign out and open this link on the student&apos;s device.</p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="narrow-page">
      <ol className="mini-steps" aria-label="Joining steps">
        <li className="current">
          <span>1</span> {hasAccount ? 'Sign in' : 'Create your account'}
        </li>
        <li>
          <span>2</span> Set up your face
        </li>
      </ol>

      <div className="card">
        {classHeader}
        <p className="field-question">Have you used SnapClass before?</p>
        <div className="segmented" role="radiogroup" aria-label="Have you used SnapClass before?">
          <button type="button" role="radio" aria-checked={!hasAccount} className={!hasAccount ? 'active' : ''} onClick={() => setHasAccount(false)}>
            No, I am new
          </button>
          <button type="button" role="radio" aria-checked={hasAccount} className={hasAccount ? 'active' : ''} onClick={() => setHasAccount(true)}>
            Yes, I have an account
          </button>
        </div>
        <ErrorBox message={error} />
        {hasAccount ? (
          <SignInForm onSignedIn={afterSignIn} />
        ) : (
          <RegisterForm onRegistered={afterSignIn} submitLabel="Create account and join" />
        )}
      </div>
    </div>
  )
}

function SignInForm({ onSignedIn }) {
  const [studentId, setStudentId] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await onSignedIn(await api('/auth/login', { method: 'POST', body: { login_id: studentId, password } }))
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
          <IconUser />
          <input value={studentId} onChange={(e) => setStudentId(e.target.value)} required autoComplete="username" placeholder="e.g. 23CSE041" />
        </div>
      </label>
      <label className="field">
        <span>Password</span>
        <PasswordInput value={password} onChange={(e) => setPassword(e.target.value)} />
      </label>
      <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={busy}>
        {busy ? 'Signing in…' : 'Sign in and join'}
      </button>
    </form>
  )
}
