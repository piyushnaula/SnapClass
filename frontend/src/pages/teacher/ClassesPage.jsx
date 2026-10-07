import { useState } from 'react'
import { api } from '../../api.js'
import { IconBook, IconCamera, IconCheck, IconChevronRight, IconPlus, IconQr, IconUsers, IconX } from '../../components/Icons.jsx'
import { useToast } from '../../components/Toast.jsx'
import { EmptyState, ErrorBox, PageHeader, Skeleton } from '../../components/ui.jsx'
import { useLoad } from '../../hooks.js'
import { Link, navigate } from '../../router.jsx'

const EMPTY_FORM = { subject: '', section: '', semester: 1, min_attendance_pct: 75 }
const GUIDE_KEY = 'snapclass.guide-hidden'

// localStorage can be blocked (private mode), so never let it crash the page.
function guideHidden() {
  try {
    return localStorage.getItem(GUIDE_KEY) === 'yes'
  } catch {
    return false
  }
}

// A short first-time guide. Each step is ticked when it is done, so new teachers
// always know what comes next (HCI: help users recognise their progress).
function GettingStarted({ classes, onCreate }) {
  const [hidden, setHidden] = useState(guideHidden)
  if (hidden || !classes) return null

  const hasClass = classes.length > 0
  const hasStudents = classes.some((c) => c.student_count > 0)
  const steps = [
    { icon: IconBook, title: 'Create a class', text: 'Add the subject and section you teach.', done: hasClass },
    { icon: IconQr, title: 'Invite your students', text: 'Open the class → Students → show the QR code in class.', done: hasStudents },
    { icon: IconCamera, title: 'Take attendance', text: 'Open the class → take a photo → check the list → save.', done: false },
  ]

  function hide() {
    try {
      localStorage.setItem(GUIDE_KEY, 'yes')
    } catch {
      // not saved, but still hidden for now
    }
    setHidden(true)
  }

  return (
    <section className="card guide" aria-labelledby="guide-title">
      <div className="card-title-row spread">
        <div>
          <h2 id="guide-title">Getting started</h2>
          <p className="muted small">Three steps to your first attendance with SnapClass.</p>
        </div>
        <button type="button" className="btn btn-ghost btn-sm" onClick={hide}>
          <IconX size={16} /> Hide guide
        </button>
      </div>
      <ol className="guide-steps">
        {steps.map((step, index) => (
          <li key={step.title} className={step.done ? 'done' : ''}>
            <span className="guide-number">{step.done ? <IconCheck size={16} /> : index + 1}</span>
            <div>
              <strong>{step.title}</strong>
              <p className="muted small">{step.text}</p>
            </div>
          </li>
        ))}
      </ol>
      {!hasClass && (
        <button type="button" className="btn btn-primary" onClick={onCreate}>
          <IconPlus /> Create my first class
        </button>
      )}
    </section>
  )
}

export default function ClassesPage() {
  const { data: classes, error, loading, reload } = useLoad(() => api('/classes'), [])
  const [form, setForm] = useState(EMPTY_FORM)
  const [formError, setFormError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [busy, setBusy] = useState(false)
  const toast = useToast()

  async function createClass(event) {
    event.preventDefault()
    setFormError('')
    setBusy(true)
    try {
      const created = await api('/classes', {
        method: 'POST',
        body: { ...form, semester: Number(form.semester), min_attendance_pct: Number(form.min_attendance_pct) },
      })
      setForm(EMPTY_FORM)
      setShowForm(false)
      toast(`Class "${created.subject}" created. Next, invite your students.`)
      navigate(`/classes/${created.id}`)
    } catch (err) {
      setFormError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const update = (field) => (event) => setForm({ ...form, [field]: event.target.value })

  return (
    <>
      <PageHeader
        title="My classes"
        subtitle="Choose a class to take attendance, invite students or see reports."
        actions={
          <button type="button" className={showForm ? 'btn btn-secondary' : 'btn btn-primary'} onClick={() => setShowForm(!showForm)}>
            {showForm ? <IconX /> : <IconPlus />}
            {showForm ? 'Cancel' : 'Add a class'}
          </button>
        }
      />

      <GettingStarted classes={classes} onCreate={() => setShowForm(true)} />

      {showForm && (
        <form className="card" onSubmit={createClass}>
          <h3 className="card-heading">Add a class</h3>
          <ErrorBox message={formError} />
          <div className="form-grid">
            <label className="field">
              <span>Subject</span>
              <input value={form.subject} onChange={update('subject')} required minLength={2} placeholder="e.g. Database Management" autoFocus />
              <small className="muted">The name students know it by</small>
            </label>
            <label className="field">
              <span>Section</span>
              <input value={form.section} onChange={update('section')} required placeholder="e.g. A" />
            </label>
            <label className="field">
              <span>Semester</span>
              <input type="number" min={1} max={12} value={form.semester} onChange={update('semester')} required />
            </label>
            <label className="field">
              <span>Minimum attendance needed (%)</span>
              <input type="number" min={0} max={100} value={form.min_attendance_pct} onChange={update('min_attendance_pct')} />
              <small className="muted">Students below this are highlighted in reports</small>
            </label>
          </div>
          <div className="button-row end">
            <button type="submit" className="btn btn-primary btn-lg" disabled={busy}>
              {busy ? 'Creating…' : 'Create class'}
            </button>
          </div>
        </form>
      )}

      {loading && <Skeleton rows={3} />}
      <ErrorBox message={error} onRetry={reload} />

      {classes?.length === 0 && !showForm && (
        <EmptyState icon={<IconBook size={28} />} title="You have no classes yet">
          Press &quot;Add a class&quot; to create your first one.
        </EmptyState>
      )}

      <div className="card-grid">
        {classes?.map((c) => (
          <Link key={c.id} to={`/classes/${c.id}`} className="card class-card">
            <div className="class-card-top">
              <span className="icon-tile">
                <IconBook size={20} />
              </span>
              <span className="class-card-open">
                Open <IconChevronRight size={16} />
              </span>
            </div>
            <h3>{c.subject}</h3>
            <p className="muted small">
              Section {c.section} · Semester {c.semester}
            </p>
            <div className="class-card-meta">
              <span>
                <IconUsers size={16} /> {c.student_count === 1 ? '1 student' : `${c.student_count} students`}
              </span>
              <span>Needs {c.min_attendance_pct}%</span>
            </div>
          </Link>
        ))}
      </div>
    </>
  )
}
