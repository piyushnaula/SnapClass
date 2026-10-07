import { useState } from 'react'
import { api } from '../../api.js'
import { IconAlert, IconBook, IconCamera, IconChevronRight, IconScanFace } from '../../components/Icons.jsx'
import { Badge, Dialog, EmptyState, ErrorBox, formatDate, formatPct, NextStep, PageHeader, Skeleton } from '../../components/ui.jsx'
import { useLoad } from '../../hooks.js'
import { Link, navigate } from '../../router.jsx'

// A circular progress ring drawn with SVG.
function Ring({ value, danger }) {
  const radius = 34
  const circumference = 2 * Math.PI * radius
  const filled = Math.max(0, Math.min(100, value ?? 0))
  return (
    <svg className="ring" viewBox="0 0 80 80" role="img" aria-label={`Attendance ${formatPct(value)}`}>
      <circle className="ring-track" cx="40" cy="40" r={radius} />
      <circle
        className={danger ? 'ring-value danger' : 'ring-value'}
        cx="40"
        cy="40"
        r={radius}
        strokeDasharray={circumference}
        strokeDashoffset={circumference * (1 - filled / 100)}
        transform="rotate(-90 40 40)"
      />
      <text x="40" y="45" textAnchor="middle" className="ring-text">
        {value === null ? '—' : `${Math.round(value)}%`}
      </text>
    </svg>
  )
}

// How many classes in a row the student must attend to reach the minimum.
// Solve (present + n) / (total + n) >= min  →  n >= (min × total − present) / (1 − min)
function classesNeeded(present, total, minPct) {
  const min = minPct / 100
  if (min >= 1) return present === total ? 0 : null // 100% minimum cannot be recovered
  return Math.max(0, Math.ceil((min * total - present) / (1 - min)))
}

function AttendanceAdvice({ c }) {
  if (c.total === 0) return <p className="muted small">No attendance has been taken in this class yet.</p>
  const needed = classesNeeded(c.present, c.total, c.min_attendance_pct)
  if (needed === 0) {
    return <p className="advice ok">You are above the {c.min_attendance_pct}% minimum. Keep it up.</p>
  }
  return (
    <p className="advice warn">
      {needed === null
        ? `You are below the ${c.min_attendance_pct}% minimum. Please talk to your teacher.`
        : `You are below the ${c.min_attendance_pct}% minimum. Attend the next ${needed} class${needed > 1 ? 'es' : ''} without missing any to reach it.`}
    </p>
  )
}

const POPUP_KEY = 'snapclass.face-request-seen'

function popupAlreadyShown() {
  try {
    return sessionStorage.getItem(POPUP_KEY) === 'yes'
  } catch {
    return false
  }
}

// Shown when a teacher asked for a new face photo: a pop-up once per visit,
// plus a banner that stays until the new photo is uploaded.
function FaceRequestNotice({ request }) {
  const [popupOpen, setPopupOpen] = useState(() => !popupAlreadyShown())

  function closePopup() {
    try {
      sessionStorage.setItem(POPUP_KEY, 'yes')
    } catch {
      // ignore: the pop-up may show again, which is fine
    }
    setPopupOpen(false)
  }

  const message = (
    <>
      <strong>{request.requested_by}</strong> ({request.subject}) asked you to upload a new face photo:{' '}
      <em>&quot;{request.reason}&quot;</em>
    </>
  )
  return (
    <>
      <div className="banner urgent" role="alert">
        <span className="icon-tile danger">
          <IconAlert size={22} />
        </span>
        <div>
          <strong>Please upload a new face photo</strong>
          <p className="small">{message}. Until you do, you will not be marked present automatically.</p>
        </div>
        <Link to="/biometrics" className="btn btn-primary btn-sm banner-button">
          Upload now <IconChevronRight size={16} />
        </Link>
      </div>

      <Dialog open={popupOpen} title="Your teacher needs a new face photo" onClose={closePopup}>
        <p>{message}</p>
        <div className="alert alert-warning">
          <span className="alert-text">
            Until you upload a new photo, SnapClass <strong>cannot mark you present automatically</strong> in any lecture.
          </span>
        </div>
        <div className="dialog-actions">
          <button type="button" className="btn btn-secondary" onClick={closePopup}>
            Later
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              closePopup()
              navigate('/biometrics')
            }}
          >
            <IconCamera /> Upload new photo now
          </button>
        </div>
      </Dialog>
    </>
  )
}

// The full lecture list for one subject: the latest 5, then "Show all".
function History({ history }) {
  const [showAll, setShowAll] = useState(false)
  if (history.length === 0) return null
  const visible = showAll ? history : history.slice(0, 5)
  return (
    <>
      <h3 className="mini-title">Lecture history</h3>
      <ul className="recent-list">
        {visible.map((r) => (
          <li key={`${r.date}-${r.period}`}>
            <span>
              {formatDate(r.date, true)} <span className="muted">· period {r.period}</span>
            </span>
            <Badge value={r.status} />
          </li>
        ))}
      </ul>
      {history.length > 5 && (
        <button type="button" className="link-button small" onClick={() => setShowAll(!showAll)}>
          {showAll ? 'Show fewer' : `Show all ${history.length} lectures`}
        </button>
      )}
    </>
  )
}

export default function StudentHome() {
  const { data: classes, error, loading, reload } = useLoad(() => api('/me/attendance'), [])
  const { data: bio } = useLoad(() => api('/me/biometrics'), [])

  return (
    <>
      <PageHeader title="My attendance" subtitle="Your attendance in every class you have joined." />

      {bio?.face_update_request && <FaceRequestNotice request={bio.face_update_request} />}

      {bio && bio.face_samples === 0 && !bio.face_update_request && (
        <Link to="/biometrics" className="banner">
          <span className="icon-tile">
            <IconScanFace size={22} />
          </span>
          <div>
            <strong>Set up your face (2 minutes)</strong>
            <p className="muted small">Until you do, your teacher has to mark your attendance by hand.</p>
          </div>
          <span className="btn btn-primary btn-sm banner-button">
            Start <IconChevronRight size={16} />
          </span>
        </Link>
      )}

      {loading && <Skeleton rows={3} />}
      <ErrorBox message={error} onRetry={reload} />
      {classes?.length === 0 && (
        <>
          <NextStep>Ask your teacher for the class invite link or QR code, and open it on this device.</NextStep>
          <EmptyState icon={<IconBook size={28} />} title="You have not joined any class yet" />
        </>
      )}

      <div className="card-grid">
        {classes?.map((c) => {
          const below = c.pct !== null && c.pct < c.min_attendance_pct
          return (
            <article key={c.class_id} className="card attendance-card">
              <div className="attendance-head">
                <div>
                  <h2 className="card-title">{c.subject}</h2>
                  <p className="muted small">
                    Section {c.section} · Semester {c.semester}
                  </p>
                  <p className="attended">
                    You attended <strong>{c.present}</strong> of <strong>{c.total}</strong> {c.total === 1 ? 'class' : 'classes'}
                  </p>
                </div>
                <Ring value={c.pct} danger={below} />
              </div>
              <AttendanceAdvice c={c} />
              <History history={c.history} />
            </article>
          )
        })}
      </div>
    </>
  )
}
