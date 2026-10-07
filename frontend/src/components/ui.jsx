// Small reusable pieces of UI used by every page.
import { useEffect, useRef, useState } from 'react'
import { Link } from '../router.jsx'
import {
  IconAlert,
  IconArrowLeft,
  IconCheck,
  IconCheckCircle,
  IconClock,
  IconEye,
  IconEyeOff,
  IconHelp,
  IconImage,
  IconInfo,
  IconLock,
  IconMinus,
  IconRefresh,
  IconSearch,
  IconX,
} from './Icons.jsx'

// ---------- Loading ----------

export function Spinner({ text = 'Loading…' }) {
  return (
    <div className="spinner-row" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{text}</span>
    </div>
  )
}

// Grey placeholder blocks shown while a page loads (feels faster than a spinner).
export function Skeleton({ rows = 3 }) {
  return (
    <div className="card" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton" style={{ width: `${90 - i * 15}%` }} />
      ))}
    </div>
  )
}

// ---------- Messages ----------

export function ErrorBox({ message, onRetry }) {
  if (!message) return null
  return (
    <div className="alert alert-error" role="alert">
      <IconAlert />
      <span className="alert-text">{message}</span>
      {onRetry && (
        <button type="button" className="btn btn-ghost btn-sm" onClick={onRetry}>
          <IconRefresh size={16} /> Retry
        </button>
      )}
    </div>
  )
}

// tone: "info" | "success" | "warning"
export function Alert({ tone = 'info', children }) {
  const icon = tone === 'success' ? <IconCheckCircle /> : tone === 'warning' ? <IconAlert /> : <IconInfo />
  return (
    <div className={`alert alert-${tone}`}>
      {icon}
      <span className="alert-text">{children}</span>
    </div>
  )
}

export function EmptyState({ icon, title, children, action }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon}</div>
      <h3>{title}</h3>
      {children && <p className="muted">{children}</p>}
      {action}
    </div>
  )
}

// ---------- Layout pieces ----------

export function PageHeader({ title, subtitle, back, actions }) {
  return (
    <div className="page-header">
      <div className="page-header-text">
        {back && (
          <Link to={back.to} className="back-link">
            <IconArrowLeft size={16} /> {back.label}
          </Link>
        )}
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  )
}

// tone: "default" | "green" | "amber" | "red" | "purple"
export function StatCard({ icon, label, value, tone = 'default' }) {
  return (
    <div className={`stat-card tone-${tone}`}>
      <div className="stat-icon">{icon}</div>
      <div>
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  )
}

// ---------- Status badge ----------
// Every status has everyday words, a color AND an icon, so it is understandable
// without technical knowledge and without seeing colors (color-blind users).

const STATUS = {
  PRESENT: { label: 'Present', tone: 'green', icon: IconCheck },
  ABSENT: { label: 'Absent', tone: 'red', icon: IconX },
  UNCERTAIN: { label: 'Not sure', tone: 'amber', icon: IconHelp },
  NOT_DETECTED: { label: 'Not found in photo', tone: 'gray', icon: IconMinus },
  CREATED: { label: 'Not started', tone: 'gray', icon: IconMinus },
  UPLOADED: { label: 'Photos added', tone: 'blue', icon: IconImage },
  PROCESSING: { label: 'Checking photos', tone: 'purple', icon: IconClock },
  REVIEW: { label: 'Needs your review', tone: 'amber', icon: IconAlert },
  FINALIZED: { label: 'Saved', tone: 'green', icon: IconCheck },
  FAILED: { label: 'Problem', tone: 'red', icon: IconAlert },
  QUEUED: { label: 'Processing', tone: 'purple', icon: IconClock },
  DONE: { label: 'Done', tone: 'green', icon: IconCheck },
}

export function statusLabel(value) {
  return STATUS[value]?.label || value
}

export function Badge({ value, label }) {
  if (!value) return null
  const info = STATUS[value] || { label: value, tone: 'gray', icon: IconMinus }
  const StatusIcon = info.icon
  return (
    <span className={`badge badge-${info.tone}`}>
      <StatusIcon size={13} />
      {label || info.label}
    </span>
  )
}

// ---------- Guidance ----------

// "What to do now" box at the top of a step (HCI: visibility of system status + next action).
export function NextStep({ children, tone = 'info' }) {
  return (
    <div className={`next-step next-step-${tone}`}>
      <span className="next-step-label">What to do now</span>
      <p>{children}</p>
    </div>
  )
}

// A small "?" button that shows a plain explanation when pressed (works on touch screens too).
export function HelpTip({ label = 'What does this mean?', children }) {
  const [open, setOpen] = useState(false)
  return (
    <span className="help-tip">
      <button type="button" className="help-tip-button" aria-expanded={open} onClick={() => setOpen(!open)}>
        <IconHelp size={15} /> {label}
      </button>
      {open && <span className="help-tip-text">{children}</span>}
    </span>
  )
}

// ---------- Inputs ----------

// Password field with "show password" and a Caps Lock warning (prevents common typing errors).
export function PasswordInput({ value, onChange, autoComplete = 'current-password', minLength, withIcon = true }) {
  const [visible, setVisible] = useState(false)
  const [capsLock, setCapsLock] = useState(false)
  return (
    <>
      <div className={withIcon ? 'input-icon with-action' : 'with-action'}>
        {withIcon && <IconLock />}
        <input
          type={visible ? 'text' : 'password'}
          value={value}
          onChange={onChange}
          onKeyUp={(event) => setCapsLock(event.getModifierState?.('CapsLock') || false)}
          required
          minLength={minLength}
          autoComplete={autoComplete}
        />
        <button
          type="button"
          className="input-action"
          onClick={() => setVisible(!visible)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          title={visible ? 'Hide password' : 'Show password'}
        >
          {visible ? <IconEyeOff /> : <IconEye />}
        </button>
      </div>
      {capsLock && <small className="text-amber">Caps Lock is on</small>}
    </>
  )
}

export function SearchInput({ value, onChange, placeholder = 'Search by name or roll number' }) {
  return (
    <div className="input-icon search-input">
      <IconSearch />
      <input type="search" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} aria-label={placeholder} />
    </div>
  )
}

// Row of filter buttons with counts, e.g. "Needs check (3) | Present (50) | Absent (7)".
export function FilterChips({ options, value, onChange }) {
  return (
    <div className="chips" role="group" aria-label="Filter the list">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={value === option.value ? `chip active ${option.tone || ''}` : `chip ${option.tone || ''}`}
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
        >
          {option.label} <span className="chip-count">{option.count}</span>
        </button>
      ))}
    </div>
  )
}

// ---------- Dialogs (native <dialog>: keyboard and focus handling built in) ----------

export function Dialog({ open, title, onClose, children }) {
  const ref = useRef(null)
  useEffect(() => {
    const dialog = ref.current
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  return (
    <dialog ref={ref} className="dialog" onClose={onClose}>
      <div className="dialog-header">
        <h3>{title}</h3>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
          <IconX />
        </button>
      </div>
      {open && children}
    </dialog>
  )
}

// A yes/no question in a dialog. Replaces window.confirm().
export function ConfirmDialog({ open, title, message, confirmLabel = 'Confirm', danger = false, onConfirm, onCancel }) {
  const [busy, setBusy] = useState(false)
  async function confirm() {
    setBusy(true)
    try {
      await onConfirm()
    } finally {
      setBusy(false)
    }
  }
  return (
    <Dialog open={open} title={title} onClose={onCancel}>
      <p className="muted">{message}</p>
      <div className="dialog-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className={danger ? 'btn btn-danger' : 'btn btn-primary'} onClick={confirm} disabled={busy}>
          {busy ? 'Please wait…' : confirmLabel}
        </button>
      </div>
    </Dialog>
  )
}

// ---------- File picker with drag and drop ----------

export function Dropzone({ accept, multiple = false, onFiles, icon, title, hint, disabled = false }) {
  const [dragging, setDragging] = useState(false)

  function handleDrop(event) {
    event.preventDefault()
    setDragging(false)
    if (!disabled) onFiles(Array.from(event.dataTransfer.files))
  }

  return (
    <label
      className={`dropzone${dragging ? ' dragging' : ''}${disabled ? ' disabled' : ''}`}
      onDragOver={(event) => {
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <input
        type="file"
        className="visually-hidden"
        accept={accept}
        multiple={multiple}
        disabled={disabled}
        onChange={(event) => {
          onFiles(Array.from(event.target.files))
          event.target.value = '' // allow picking the same file again
        }}
      />
      <span className="dropzone-icon">{icon}</span>
      <strong>{title}</strong>
      {hint && <span className="muted small">{hint}</span>}
    </label>
  )
}

// ---------- Local file previews ----------

// The temporary URL is created once per file and freed when the preview disappears.
function useObjectUrl(blob) {
  const [url, setUrl] = useState(null)
  useEffect(() => {
    if (!blob) return undefined
    const objectUrl = URL.createObjectURL(blob)
    setUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [blob])
  return url
}

export function ImagePreview({ blob, alt }) {
  const url = useObjectUrl(blob)
  return url ? <img src={url} alt={alt} /> : null
}

export function AudioPreview({ blob }) {
  const url = useObjectUrl(blob)
  return url ? <audio controls src={url} /> : null
}

// ---------- Helpers ----------

export function formatPct(value) {
  return value === null || value === undefined ? '—' : `${value.toFixed(1)}%`
}

export function todayISO() {
  // Local date (IST for Indian users), not UTC.
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

// "Wed, 8 Oct 2026" — the weekday helps teachers recognise the lecture without counting dates.
export function formatDate(iso, withWeekday = false) {
  const options = { day: 'numeric', month: 'short', year: 'numeric' }
  if (withWeekday) options.weekday = 'short'
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', options)
}

export function initials(name = '') {
  const parts = name.trim().split(/\s+/)
  return ((parts[0]?.[0] || '') + (parts.length > 1 ? parts[parts.length - 1][0] : '')).toUpperCase()
}
