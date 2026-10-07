import { useState } from 'react'
import { api } from '../../api.js'
import {
  IconCalendar,
  IconCamera,
  IconChart,
  IconChevronRight,
  IconCopy,
  IconDownload,
  IconQr,
  IconTrash,
  IconUsers,
} from '../../components/Icons.jsx'
import FaceRequestDialog from '../../components/FaceRequestDialog.jsx'
import { useToast } from '../../components/Toast.jsx'
import {
  Badge,
  ConfirmDialog,
  EmptyState,
  ErrorBox,
  formatDate,
  formatPct,
  HelpTip,
  PageHeader,
  SearchInput,
  Skeleton,
  todayISO,
} from '../../components/ui.jsx'
import { useLoad } from '../../hooks.js'
import { Link, navigate } from '../../router.jsx'
import { downloadBlob } from '../../utils/image.js'

const TABS = [
  { id: 'attendance', label: 'Take attendance', icon: IconCamera },
  { id: 'students', label: 'Students', icon: IconUsers },
  { id: 'report', label: 'Reports', icon: IconChart },
]

// Show only the students whose name or roll number contains the search text.
function matchesSearch(student, search) {
  const text = `${student.full_name} ${student.roll_no || ''}`.toLowerCase()
  return text.includes(search.trim().toLowerCase())
}

// One class: take attendance, manage students, see reports.
export default function ClassPage({ classId }) {
  const { data: classInfo, error, loading, reload } = useLoad(() => api(`/classes/${classId}`), [classId])
  const [tab, setTab] = useState('attendance')

  if (loading) return <Skeleton rows={4} />
  if (error) return <ErrorBox message={error} onRetry={reload} />

  const students = classInfo.student_count === 1 ? '1 student' : `${classInfo.student_count} students`
  return (
    <>
      <PageHeader
        back={{ to: '/', label: 'My classes' }}
        title={classInfo.subject}
        subtitle={`Section ${classInfo.section} · Semester ${classInfo.semester} · ${students} · needs ${classInfo.min_attendance_pct}% attendance`}
      />
      <div className="tabs" role="tablist" aria-label="Class sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={tab === t.id ? 'tab active' : 'tab'}
            onClick={() => setTab(t.id)}
          >
            <t.icon size={18} /> {t.label}
          </button>
        ))}
      </div>
      {tab === 'attendance' && <AttendanceTab classId={classId} studentCount={classInfo.student_count} onInvite={() => setTab('students')} />}
      {tab === 'students' && <StudentsTab classId={classId} onChange={reload} />}
      {tab === 'report' && <ReportTab classInfo={classInfo} />}
    </>
  )
}

function AttendanceTab({ classId, studentCount, onInvite }) {
  const { data: sessions, error, loading, reload } = useLoad(() => api(`/classes/${classId}/sessions`), [classId])
  const [form, setForm] = useState({ session_date: todayISO(), period: 1 })
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)

  async function startSession(event) {
    event.preventDefault()
    setFormError('')
    setBusy(true)
    try {
      const session = await api(`/classes/${classId}/sessions`, {
        method: 'POST',
        body: { session_date: form.session_date, period: Number(form.period) },
      })
      navigate(`/sessions/${session.id}`)
    } catch (err) {
      setFormError(err.message)
      setBusy(false)
    }
  }

  return (
    <>
      {studentCount === 0 && (
        <div className="alert alert-warning">
          <span className="alert-text">
            No students have joined this class yet, so nobody can be recognised.{' '}
            <button type="button" className="link-button" onClick={onInvite}>
              Invite students first
            </button>
          </span>
        </div>
      )}

      <form className="card highlight-card" onSubmit={startSession}>
        <h2 className="card-heading">Start a new attendance</h2>
        <p className="muted small">Choose the date and lecture period, then press Start. You will take or choose the class photos next.</p>
        <div className="inline-form">
          <label className="field">
            <span>Date</span>
            <input type="date" value={form.session_date} onChange={(e) => setForm({ ...form, session_date: e.target.value })} required />
          </label>
          <label className="field">
            <span>Lecture period</span>
            <input type="number" min={1} max={12} value={form.period} onChange={(e) => setForm({ ...form, period: e.target.value })} required />
          </label>
          <button type="submit" className="btn btn-primary btn-lg" disabled={busy}>
            <IconCamera /> {busy ? 'Starting…' : 'Start'}
          </button>
        </div>
        <ErrorBox message={formError} />
      </form>

      <h3 className="section-title">Past attendance</h3>
      {loading && <Skeleton rows={3} />}
      <ErrorBox message={error} onRetry={reload} />
      {sessions?.length === 0 && (
        <EmptyState icon={<IconCalendar size={28} />} title="No attendance taken yet">
          Your saved attendance will be listed here.
        </EmptyState>
      )}
      {sessions?.length > 0 && (
        <div className="table-card">
          <table className="table table-stack">
            <thead>
              <tr>
                <th>Date</th>
                <th>Period</th>
                <th>Status</th>
                <th aria-label="Open" />
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id} className="clickable" onClick={() => navigate(`/sessions/${s.id}`)}>
                  <td data-label="Date">{formatDate(s.session_date, true)}</td>
                  <td data-label="Period">{s.period}</td>
                  <td data-label="Status">
                    <Badge value={s.status} />
                  </td>
                  <td className="cell-action">
                    <Link to={`/sessions/${s.id}`} className="btn btn-secondary btn-sm" onClick={(e) => e.stopPropagation()}>
                      {s.status === 'FINALIZED' ? 'View' : 'Continue'} <IconChevronRight size={16} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

function StudentsTab({ classId, onChange }) {
  const { data: students, error, loading, reload } = useLoad(() => api(`/classes/${classId}/students`), [classId])
  const [joinCode, setJoinCode] = useState(null)
  const [toRemove, setToRemove] = useState(null)
  const [asking, setAsking] = useState(null) // student we ask for a new face photo
  const [actionError, setActionError] = useState('')
  const [search, setSearch] = useState('')
  const toast = useToast()

  async function createJoinCode() {
    setActionError('')
    try {
      setJoinCode(await api(`/classes/${classId}/join-codes`, { method: 'POST', body: {} }))
    } catch (err) {
      setActionError(err.message)
    }
  }

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(joinCode.join_url)
      toast('Invite link copied. You can paste it in a message to your students.')
    } catch {
      toast('Could not copy automatically. Please select the link and copy it.', 'error')
    }
  }

  async function cancelRequest(student) {
    try {
      await api(`/classes/${classId}/students/${student.id}/face-update-request`, { method: 'DELETE' })
      toast(`Request for ${student.full_name} cancelled.`)
      reload()
    } catch (err) {
      setActionError(err.message)
    }
  }

  async function removeStudent() {
    try {
      await api(`/classes/${classId}/students/${toRemove.id}`, { method: 'DELETE' })
      toast(`${toRemove.full_name} was removed from the class.`)
      setToRemove(null)
      reload()
      onChange()
    } catch (err) {
      setToRemove(null)
      setActionError(err.message)
    }
  }

  const notSetUp = students?.filter((s) => !s.face_samples).length || 0
  const visible = students?.filter((s) => matchesSearch(s, search)) || []

  return (
    <>
      <div className="card">
        <h2 className="card-heading">Invite students</h2>
        <ol className="numbered-list">
          <li>Press &quot;Create invite link&quot;.</li>
          <li>Show the QR code on the projector, or send the link in your class group.</li>
          <li>Students open it on their phone, create an account and set up their face.</li>
        </ol>
        <button type="button" className="btn btn-primary" onClick={createJoinCode}>
          <IconQr /> {joinCode ? 'Create a new invite link' : 'Create invite link'}
        </button>
        {joinCode && (
          <div className="join-code">
            <img src={`data:image/png;base64,${joinCode.qr_png_base64}`} alt="QR code students can scan to join this class" />
            <div className="join-code-info">
              <span className="eyebrow">Invite code</span>
              <strong className="code">{joinCode.code}</strong>
              <span className="link-box">{joinCode.join_url}</span>
              <div className="button-row">
                <button type="button" className="btn btn-secondary" onClick={copyLink}>
                  <IconCopy size={16} /> Copy link
                </button>
              </div>
              <span className="muted small">Works until {new Date(joinCode.expires_at).toLocaleString('en-IN')}</span>
            </div>
          </div>
        )}
      </div>

      <ErrorBox message={actionError || error} onRetry={error ? reload : undefined} />
      {loading && <Skeleton rows={3} />}
      {students?.length === 0 && (
        <EmptyState icon={<IconUsers size={28} />} title="No students yet">
          Create an invite link above and share it with your class.
        </EmptyState>
      )}
      {students?.length > 0 && (
        <>
          <div className="list-toolbar">
            <h3 className="section-title">
              {students.length} {students.length === 1 ? 'student' : 'students'}
              {notSetUp > 0 && <span className="tag tag-amber">{notSetUp} without face setup</span>}
            </h3>
            <SearchInput value={search} onChange={setSearch} />
          </div>
          {notSetUp > 0 && (
            <HelpTip label="Why does face setup matter?">
              Students without face setup cannot be recognised in photos. You will mark them by hand on the attendance screen.
            </HelpTip>
          )}
          <div className="table-card">
            <table className="table table-stack">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Face setup</th>
                  <th>Voice</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {visible.map((s) => (
                  <tr key={s.id}>
                    <td data-label="Student">
                      <div className="person">
                        <strong>{s.full_name}</strong>
                        <span className="muted small">
                          {s.roll_no}
                          {s.email ? ` · ${s.email}` : ''}
                        </span>
                      </div>
                    </td>
                    <td data-label="Face setup">
                      {s.face_update_requested ? (
                        <span className="tag tag-purple">New photo requested</span>
                      ) : s.face_samples ? (
                        <Badge value="DONE" />
                      ) : (
                        <span className="tag tag-amber">Not yet</span>
                      )}
                    </td>
                    <td data-label="Voice">{s.voice_samples ? <Badge value="DONE" /> : <span className="tag">Optional</span>}</td>
                    <td className="cell-action">
                      {s.face_update_requested ? (
                        <button type="button" className="btn btn-ghost btn-sm" onClick={() => cancelRequest(s)}>
                          Cancel request
                        </button>
                      ) : (
                        s.face_samples > 0 && (
                          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAsking(s)}>
                            <IconCamera size={16} /> New face photo
                          </button>
                        )
                      )}
                      <button type="button" className="btn btn-ghost btn-sm danger-text" onClick={() => setToRemove(s)}>
                        <IconTrash size={16} /> Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {visible.length === 0 && <p className="muted center pad">No student matches &quot;{search}&quot;.</p>}
          </div>
        </>
      )}

      <FaceRequestDialog
        student={asking && { id: asking.id, name: asking.full_name }}
        classId={classId}
        onClose={() => setAsking(null)}
        onDone={() => {
          setAsking(null)
          reload()
        }}
      />

      <ConfirmDialog
        open={toRemove !== null}
        title="Remove this student from the class?"
        message={toRemove && `${toRemove.full_name} will no longer appear in this class. Their past attendance is kept.`}
        confirmLabel="Yes, remove"
        danger
        onConfirm={removeStudent}
        onCancel={() => setToRemove(null)}
      />
    </>
  )
}

function ReportTab({ classInfo }) {
  const [filters, setFilters] = useState({ from: '', to: '', below: false })
  const [search, setSearch] = useState('')
  const query = new URLSearchParams()
  if (filters.from) query.set('from', filters.from)
  if (filters.to) query.set('to', filters.to)
  if (filters.below) query.set('below', 'true')
  const queryString = query.toString()

  const { data: report, error, loading, reload } = useLoad(
    () => api(`/classes/${classInfo.id}/report?${queryString}`),
    [classInfo.id, queryString],
  )
  const [downloadError, setDownloadError] = useState('')
  const toast = useToast()

  async function downloadCsv() {
    try {
      const response = await api(`/classes/${classInfo.id}/report?${queryString}&format=csv`, { raw: true })
      downloadBlob(await response.blob(), `attendance-${classInfo.subject}-${classInfo.section}.csv`)
      toast('Report downloaded. You can open it in Excel or Google Sheets.')
    } catch (err) {
      setDownloadError(err.message)
    }
  }

  const belowCount = report?.rows.filter((row) => row.below_threshold).length || 0
  const rows = report?.rows.filter((row) => matchesSearch(row, search)) || []

  return (
    <>
      <div className="card">
        <h2 className="card-heading">Attendance report</h2>
        <p className="muted small">Leave the dates empty to see the whole semester.</p>
        <div className="inline-form">
          <label className="field">
            <span>From date</span>
            <input type="date" value={filters.from} onChange={(e) => setFilters({ ...filters, from: e.target.value })} />
          </label>
          <label className="field">
            <span>To date</span>
            <input type="date" value={filters.to} onChange={(e) => setFilters({ ...filters, to: e.target.value })} />
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={filters.below} onChange={(e) => setFilters({ ...filters, below: e.target.checked })} />
            Show only students below {classInfo.min_attendance_pct}%
          </label>
          <button type="button" className="btn btn-secondary" onClick={downloadCsv}>
            <IconDownload /> Download for Excel
          </button>
        </div>
      </div>

      <ErrorBox message={error || downloadError} onRetry={error ? reload : undefined} />
      {loading && <Skeleton rows={4} />}
      {report && report.rows.length > 0 && (
        <>
          <div className="list-toolbar">
            <h3 className="section-title">
              {belowCount > 0 ? (
                <span className="tag tag-red">{belowCount} below {classInfo.min_attendance_pct}%</span>
              ) : (
                <span className="tag tag-green">Everyone is at or above {classInfo.min_attendance_pct}%</span>
              )}
            </h3>
            <SearchInput value={search} onChange={setSearch} />
          </div>
          <div className="table-card">
            <table className="table table-stack">
              <thead>
                <tr>
                  <th>Student</th>
                  <th>Classes attended</th>
                  <th>Attendance</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.student_id} className={row.below_threshold ? 'row-warn' : ''}>
                    <td data-label="Student">
                      <div className="person">
                        <strong>{row.full_name}</strong>
                        <span className="muted small">{row.roll_no}</span>
                      </div>
                    </td>
                    <td data-label="Attended">
                      {row.present} of {row.total}
                    </td>
                    <td data-label="Attendance">
                      <div className="pct-cell">
                        <div className="progress small-bar">
                          <div className={row.below_threshold ? 'progress-bar red' : 'progress-bar'} style={{ width: `${row.pct || 0}%` }} />
                        </div>
                        <strong className={row.below_threshold ? 'text-red' : ''}>{formatPct(row.pct)}</strong>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <p className="muted center pad">No student matches &quot;{search}&quot;.</p>}
          </div>
        </>
      )}
      {report?.rows.length === 0 && (
        <EmptyState icon={<IconChart size={28} />} title="Nothing to show">
          {filters.below ? 'No student is below the minimum. Well done!' : 'No students in this class yet.'}
        </EmptyState>
      )}
    </>
  )
}
