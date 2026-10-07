import { useState } from 'react'
import { api } from '../../api.js'
import {
  IconActivity,
  IconAlert,
  IconBook,
  IconCalendar,
  IconCap,
  IconClock,
  IconFile,
  IconPlus,
  IconSliders,
  IconUser,
  IconUsers,
} from '../../components/Icons.jsx'
import { useToast } from '../../components/Toast.jsx'
import { Alert, Badge, EmptyState, ErrorBox, initials, PageHeader, Skeleton, StatCard } from '../../components/ui.jsx'
import { useInterval, useLoad } from '../../hooks.js'

export default function AdminPage() {
  return (
    <>
      <PageHeader title="Dashboard" subtitle="See how SnapClass is running, manage teachers and settings." />
      <Metrics />
      <div className="two-column wide-left">
        <Teachers />
        <Settings />
      </div>
      <AuditLog />
    </>
  )
}

function Metrics() {
  const { data: m, error, loading, reload } = useLoad(() => api('/admin/metrics'), [])
  useInterval(reload, 15000, true) // refresh every 15 s

  if (loading) return <Skeleton rows={3} />
  if (error) return <ErrorBox message={error} onRetry={reload} />

  const seconds = (ms) => (ms === null ? '—' : `${(ms / 1000).toFixed(1)} s`)
  const queued = m.queue_depth ? Object.values(m.queue_depth).reduce((a, b) => a + b, 0) : null
  const failures = m.failed_sessions_last_24h + m.failed_enrollments_last_24h

  return (
    <>
      <div className="stat-grid">
        <StatCard icon={<IconUser />} label="Teachers" value={m.teachers} tone="purple" />
        <StatCard icon={<IconCap />} label="Students" value={m.students} tone="purple" />
        <StatCard icon={<IconBook />} label="Classes" value={m.classes} />
        <StatCard icon={<IconCalendar />} label="Attendance taken (last 24 h)" value={m.sessions_last_24h} />
        <StatCard icon={<IconAlert />} label="Problems (last 24 h)" value={failures} tone={failures ? 'red' : 'green'} />
        <StatCard icon={<IconActivity />} label="Photos waiting to be checked" value={queued ?? 'Offline'} tone={queued === null ? 'red' : 'default'} />
        <StatCard icon={<IconClock />} label="Checking time (typical / slowest)" value={`${seconds(m.match_job_ms.p50)} / ${seconds(m.match_job_ms.p95)}`} />
      </div>

      <div className="card">
        <h3 className="card-heading">Attendance by status</h3>
        <div className="badge-row">
          {Object.keys(m.sessions_by_status).length === 0 && <span className="muted small">No sessions yet.</span>}
          {Object.entries(m.sessions_by_status).map(([status, count]) => (
            <span key={status} className="badge-count">
              <Badge value={status} /> <strong>{count}</strong>
            </span>
          ))}
        </div>
        {m.duplicate_face_flags.length > 0 && (
          <>
            <h3 className="card-heading spaced">Possible duplicate accounts</h3>
            <ul className="flag-list">
              {m.duplicate_face_flags.map((flag, i) => (
                <li key={i}>
                  <IconAlert size={16} className="text-amber" />
                  <span className="mono small">
                    {flag.student_id.slice(0, 8)} looks like {flag.details.similar_to_student_id.slice(0, 8)} (distance {flag.details.distance})
                  </span>
                  <span className="muted small">{new Date(flag.at).toLocaleString()}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </>
  )
}

function Teachers() {
  const { data: teachers, error, loading, reload } = useLoad(() => api('/admin/teachers'), [])
  const [form, setForm] = useState({ full_name: '', email: '', password: '' })
  const [actionError, setActionError] = useState('')
  const [busy, setBusy] = useState(false)
  const toast = useToast()

  async function create(event) {
    event.preventDefault()
    setActionError('')
    setBusy(true)
    try {
      await api('/admin/teachers', { method: 'POST', body: form })
      toast(`Teacher account created for ${form.full_name}. Share the email and temporary password with them privately.`)
      setForm({ full_name: '', email: '', password: '' })
      reload()
    } catch (err) {
      setActionError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function toggleActive(teacher) {
    try {
      await api(`/admin/users/${teacher.id}`, { method: 'PATCH', body: { is_active: !teacher.is_active } })
      toast(teacher.is_active ? `${teacher.full_name} can no longer sign in.` : `${teacher.full_name} can sign in again.`)
      reload()
    } catch (err) {
      setActionError(err.message)
    }
  }

  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  return (
    <div className="card">
      <h3 className="card-heading">
        <IconUsers size={18} /> Teachers
      </h3>
      <p className="muted small">Add a teacher with a temporary password. They sign in with this email.</p>
      <form className="form-grid" onSubmit={create}>
        <label className="field">
          <span>Full name</span>
          <input value={form.full_name} onChange={update('full_name')} required minLength={2} />
        </label>
        <label className="field">
          <span>Email</span>
          <input type="email" value={form.email} onChange={update('email')} required />
        </label>
        <label className="field">
          <span>Temporary password</span>
          <input type="password" value={form.password} onChange={update('password')} required minLength={8} autoComplete="new-password" />
        </label>
        <div className="field field-button">
          <button type="submit" className="btn btn-primary" disabled={busy}>
            <IconPlus /> Add teacher
          </button>
        </div>
      </form>
      <ErrorBox message={actionError || error} onRetry={error ? reload : undefined} />
      {loading && <Skeleton rows={2} />}
      {teachers?.length === 0 && <p className="muted small">No teachers yet. Add the first one above.</p>}
      {teachers?.length > 0 && (
        <ul className="people-list">
          {teachers.map((t) => (
            <li key={t.id}>
              <span className="avatar">{initials(t.full_name)}</span>
              <div className="person">
                <strong>{t.full_name}</strong>
                <span className="muted small">{t.email}</span>
              </div>
              <span className={t.is_active ? 'tag tag-green' : 'tag tag-red'}>{t.is_active ? 'Can sign in' : 'Turned off'}</span>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => toggleActive(t)}>
                {t.is_active ? 'Turn off account' : 'Turn on account'}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

const THRESHOLD_HELP = {
  face_accept: 'Face distance at or below this is marked "Found in photo"',
  face_reject: 'Above this is "Not found"; between the two is "Not sure"',
  voice_accept: 'Voice similarity at or above this is a strong match',
  voice_reject: 'Voice similarity below this is ignored',
  fused_accept: 'Face + voice score at or above this is "Found"',
  fused_reject: 'Face + voice score below this is "Not found"',
  w_face: 'How much the face counts in the face + voice score (0 to 1)',
}

function Settings() {
  const { data, error, reload } = useLoad(() => api('/admin/settings'), [])
  const [draft, setDraft] = useState(null)
  const [saveError, setSaveError] = useState('')
  const toast = useToast()

  if (!data) return error ? <ErrorBox message={error} onRetry={reload} /> : <Skeleton rows={4} />
  const values = draft || {
    thresholds: data.thresholds,
    retention_days: data.retention.days,
    blur_threshold: data.enrollment.blur_threshold,
  }

  function setThreshold(name, value) {
    setDraft({ ...values, thresholds: { ...values.thresholds, [name]: value } })
  }

  async function save(event) {
    event.preventDefault()
    setSaveError('')
    try {
      const thresholds = Object.fromEntries(Object.entries(values.thresholds).map(([k, v]) => [k, Number(v)]))
      await api('/admin/settings', {
        method: 'PUT',
        body: { thresholds, retention_days: Number(values.retention_days), blur_threshold: Number(values.blur_threshold) },
      })
      setDraft(null)
      toast('Settings saved. New attendance will use them.')
      reload()
    } catch (err) {
      setSaveError(err.message)
    }
  }

  return (
    <form className="card" onSubmit={save}>
      <h3 className="card-heading">
        <IconSliders size={18} /> Settings
      </h3>
      <label className="field">
        <span>Delete class photos after (days)</span>
        <input type="number" min={1} max={90} value={values.retention_days} onChange={(e) => setDraft({ ...values, retention_days: e.target.value })} />
        <small className="muted">Counted from the day attendance is saved. Shorter is better for privacy.</small>
      </label>

      {/* Technical settings are hidden by default, so nobody changes them by accident. */}
      <details className="advanced">
        <summary>Advanced settings (for technical staff)</summary>
        <Alert tone="warning">
          Change these only after measuring accuracy with the evaluation script. Wrong values can mark students present by mistake.
        </Alert>
        <div className="form-grid compact">
          {Object.entries(values.thresholds).map(([name, value]) => (
            <label key={name} className="field">
              <span className="mono">{name}</span>
              <input type="number" step="0.01" value={value} onChange={(e) => setThreshold(name, e.target.value)} />
              <small className="muted">{THRESHOLD_HELP[name]}</small>
            </label>
          ))}
          <label className="field">
            <span className="mono">blur_threshold</span>
            <input type="number" step="1" value={values.blur_threshold} onChange={(e) => setDraft({ ...values, blur_threshold: e.target.value })} />
            <small className="muted">Students&apos; setup photos must be at least this sharp</small>
          </label>
        </div>
      </details>

      <ErrorBox message={saveError} />
      <div className="button-row end">
        {draft && (
          <button type="button" className="btn btn-ghost" onClick={() => setDraft(null)}>
            Undo changes
          </button>
        )}
        <button type="submit" className="btn btn-primary" disabled={!draft}>
          Save settings
        </button>
      </div>
    </form>
  )
}

// Everyday names for the recorded actions.
const ACTION_LABELS = {
  SESSION_FINALIZE: 'Attendance saved',
  ATTENDANCE_CORRECT: 'Attendance changed',
  BIOMETRIC_DELETE: 'Student removed face data',
  CONSENT_GRANTED: 'Student gave permission',
  ROLE_CHANGE: 'Teacher account created',
  USER_STATUS_CHANGE: 'Account turned on/off',
  SETTINGS_CHANGE: 'Settings changed',
  STUDENT_REMOVED: 'Student removed from class',
  DUPLICATE_FACE_SUSPECTED: 'Possible duplicate account',
}

function AuditLog() {
  const { data: entries, error, loading, reload } = useLoad(() => api('/admin/audit?limit=50'), [])
  const [showDetails, setShowDetails] = useState(false)
  return (
    <div className="card">
      <div className="card-title-row spread">
        <div>
          <h3 className="card-heading">
            <IconFile size={18} /> Activity history
          </h3>
          <p className="muted small">The latest 50 important actions. These records cannot be edited.</p>
        </div>
        <label className="checkbox small">
          <input type="checkbox" checked={showDetails} onChange={(e) => setShowDetails(e.target.checked)} />
          Show technical details
        </label>
      </div>
      <ErrorBox message={error} onRetry={reload} />
      {loading && <Skeleton rows={3} />}
      {entries?.length === 0 && <EmptyState icon={<IconFile size={28} />} title="Nothing recorded yet" />}
      {entries?.length > 0 && (
        <div className="table-card flush">
          <table className="table table-stack">
            <thead>
              <tr>
                <th>When</th>
                <th>What happened</th>
                <th>Reason</th>
                {showDetails && <th>Details</th>}
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id}>
                  <td data-label="When" className="nowrap small">
                    {new Date(e.at).toLocaleString('en-IN')}
                  </td>
                  <td data-label="What happened">
                    <span className="tag tag-purple">{ACTION_LABELS[e.action] || e.action}</span>
                  </td>
                  <td data-label="Reason" className="small">
                    {e.reason || <span className="muted">—</span>}
                  </td>
                  {showDetails && (
                    <td data-label="Details" className="muted small mono break">
                      {e.entity_type} {e.entity_id.slice(0, 8)} {e.before && JSON.stringify(e.before)}{' '}
                      {e.after && `→ ${JSON.stringify(e.after)}`}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
