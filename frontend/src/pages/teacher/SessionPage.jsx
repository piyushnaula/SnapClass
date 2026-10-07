import { useEffect, useState } from 'react'
import { api } from '../../api.js'
import AudioRecorder from '../../components/AudioRecorder.jsx'
import FaceRequestDialog from '../../components/FaceRequestDialog.jsx'
import CameraCapture from '../../components/CameraCapture.jsx'
import {
  IconArrowLeft,
  IconBulb,
  IconCamera,
  IconCheck,
  IconCheckCircle,
  IconEdit,
  IconImage,
  IconMic,
  IconScanFace,
  IconSearch,
  IconUpload,
  IconUser,
  IconX,
} from '../../components/Icons.jsx'
import { useToast } from '../../components/Toast.jsx'
import {
  Alert,
  AudioPreview,
  Badge,
  ConfirmDialog,
  Dialog,
  Dropzone,
  ErrorBox,
  FilterChips,
  formatDate,
  HelpTip,
  ImagePreview,
  NextStep,
  PageHeader,
  SearchInput,
  Skeleton,
} from '../../components/ui.jsx'
import { useInterval, useLoad } from '../../hooks.js'
import { compressImage } from '../../utils/image.js'

const MAX_PHOTOS = 10

// One lecture. What we show depends on the status:
// CREATED/UPLOADED/FAILED → add or change photos, PROCESSING → wait,
// REVIEW → check + save (photos can still be added or removed), FINALIZED → view / change.
export default function SessionPage({ sessionId }) {
  const { data: session, error, loading, reload, setData } = useLoad(() => api(`/sessions/${sessionId}`), [sessionId])
  // The class name in the title tells the teacher where they are (recognition, not recall).
  const { data: classInfo } = useLoad(
    () => (session ? api(`/classes/${session.class_id}`) : null),
    [session?.class_id],
  )
  const [actionError, setActionError] = useState('')
  const [changingPhotos, setChangingPhotos] = useState(false) // review → "add or change photos"

  // While the photos are being checked, ask the server for news every 2 seconds.
  useInterval(reload, 2000, session?.status === 'PROCESSING')

  // Leave "change photos" mode as soon as the lecture moves to another step.
  useEffect(() => {
    if (session?.status !== 'REVIEW') setChangingPhotos(false)
  }, [session?.status])

  // Run an API action, then show the new state. Returns true when it worked.
  async function run(action) {
    setActionError('')
    try {
      const result = await action()
      if (result && result.status) setData(result)
      else await reload()
      return true
    } catch (err) {
      setActionError(err.message)
      return false
    }
  }

  if (loading) return <Skeleton rows={5} />
  if (error) return <ErrorBox message={error} onRetry={reload} />

  const photoStatuses = ['CREATED', 'UPLOADED', 'FAILED']
  return (
    <>
      <PageHeader
        back={{ to: `/classes/${session.class_id}`, label: classInfo ? `Back to ${classInfo.subject}` : 'Back to class' }}
        title={classInfo ? `${classInfo.subject} · Section ${classInfo.section}` : 'Attendance'}
        subtitle={`${formatDate(session.session_date, true)} · Lecture period ${session.period}`}
        actions={<Badge value={session.status} />}
      />
      <Stepper status={changingPhotos ? 'UPLOADED' : session.status} />
      <ErrorBox message={actionError} />

      {photoStatuses.includes(session.status) && <PhotoStep session={session} run={run} />}
      {session.status === 'PROCESSING' && <ProcessingStep />}
      {session.status === 'REVIEW' &&
        (changingPhotos ? (
          <PhotoStep session={session} run={run} onBack={() => setChangingPhotos(false)} />
        ) : (
          <ReviewStep session={session} run={run} onChangePhotos={() => setChangingPhotos(true)} />
        ))}
      {session.status === 'FINALIZED' && <SavedStep session={session} run={run} />}
    </>
  )
}

// ---------- Progress tracker ----------

const STEPS = ['Add photos', 'Checking', 'Your review', 'Saved']
const STEP_INDEX = { CREATED: 0, UPLOADED: 0, PROCESSING: 1, FAILED: 1, REVIEW: 2, FINALIZED: 4 }

function Stepper({ status }) {
  const current = STEP_INDEX[status]
  return (
    <ol className="stepper" aria-label="Progress">
      {STEPS.map((label, index) => {
        let state = index < current ? 'done' : index === current ? 'current' : 'todo'
        if (status === 'FAILED' && index === current) state = 'failed'
        return (
          <li key={label} className={`step ${state}`} aria-current={state === 'current' ? 'step' : undefined}>
            <span className="step-dot">
              {state === 'done' ? <IconCheck size={14} /> : state === 'failed' ? <IconX size={14} /> : index + 1}
            </span>
            <span className="step-label">{label}</span>
          </li>
        )
      })}
    </ol>
  )
}

// ---------- Step 1: add photos ----------

const PHOTO_TIPS = [
  'Stand at the front of the room, where you can see every face.',
  'Ask students to look up at the camera for two seconds.',
  'Take several photos (up to 10): left side, middle and right side, front and back rows.',
  'Make sure the room is well lit. Avoid shooting towards a bright window.',
]

// Photos already on the server: thumbnails with a Remove button.
function UploadedPhotos({ session, run }) {
  const [toRemove, setToRemove] = useState(null)
  const toast = useToast()
  const photos = session.media.filter((m) => m.kind === 'PHOTO')
  const audio = session.media.find((m) => m.kind === 'AUDIO')
  if (photos.length === 0 && !audio) return null

  async function remove() {
    const ok = await run(() => api(`/sessions/${session.id}/media/${toRemove.id}`, { method: 'DELETE' }))
    if (ok) toast(toRemove.kind === 'PHOTO' ? 'Photo removed.' : 'Recording removed.')
    setToRemove(null)
  }

  return (
    <div className="card">
      <h3 className="card-heading">
        <IconCheckCircle size={18} /> Already uploaded
      </h3>
      <p className="muted small">Remove a photo if it is blurry or shows the wrong room.</p>
      {photos.length > 0 && (
        <div className="thumb-grid">
          {photos.map((m, index) => (
            <div key={m.id} className="thumb">
              <img src={m.url} alt={`Uploaded class photo ${index + 1}`} />
              <button
                type="button"
                className="thumb-remove"
                aria-label={`Remove uploaded photo ${index + 1}`}
                title="Remove this photo"
                onClick={() => setToRemove(m)}
              >
                <IconX size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
      {audio && (
        <div className="row">
          <span className="tag">
            <IconMic size={14} /> Roll-call recording uploaded
          </span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setToRemove(audio)}>
            <IconX size={16} /> Remove
          </button>
        </div>
      )}
      <ConfirmDialog
        open={toRemove !== null}
        title={toRemove?.kind === 'AUDIO' ? 'Remove the recording?' : 'Remove this photo?'}
        message="It will be deleted. Press Check again afterwards so SnapClass uses the remaining photos."
        confirmLabel="Yes, remove"
        danger
        onConfirm={remove}
        onCancel={() => setToRemove(null)}
      />
    </div>
  )
}

// Add photos (first time), or add / remove photos and check again.
// onBack is given when we came here from the review list.
function PhotoStep({ session, run, onBack }) {
  const [photos, setPhotos] = useState([])
  const [audio, setAudio] = useState(null)
  const [busy, setBusy] = useState(false)
  const [clearChoices, setClearChoices] = useState(false)
  const toast = useToast()

  const checkedBefore = session.results.length > 0 // there was an earlier check
  const myChoices = session.results.filter((r) => r.teacher_decision).length
  const roomLeft = MAX_PHOTOS - session.photo_count - photos.length
  const hasNew = photos.length > 0 || Boolean(audio)
  // From the review list nothing has changed yet, so a new photo is needed before checking again.
  const canCheck = onBack ? hasNew : hasNew || session.photo_count > 0 || session.audio_count > 0

  function addPhotos(files) {
    const images = files.filter((file) => file.type.startsWith('image/'))
    const allowed = MAX_PHOTOS - session.photo_count
    if (photos.length + images.length > allowed) toast(`You can use up to ${MAX_PHOTOS} photos per attendance.`, 'error')
    setPhotos([...photos, ...images].slice(0, allowed))
  }

  // One button does both: upload what was chosen, then start checking (fewer steps for the teacher).
  async function checkAttendance() {
    setBusy(true)
    if (hasNew) {
      const form = new FormData()
      for (const photo of photos) form.append('photos', await compressImage(photo), 'class.jpg')
      if (audio) form.append('audio', audio, 'class-audio')
      const uploaded = await run(() => api(`/sessions/${session.id}/media`, { method: 'POST', form }))
      if (!uploaded) {
        setBusy(false)
        return
      }
      setPhotos([])
      setAudio(null)
    }
    const query = clearChoices ? '?clear_decisions=true' : ''
    await run(() => api(`/sessions/${session.id}/process${query}`, { method: 'POST' }))
    setBusy(false)
  }

  let guidance
  if (session.status === 'FAILED') {
    guidance = (
      <NextStep tone="error">
        We could not check the photos. Press <strong>Check again</strong>, or remove unclear photos and add new ones.
      </NextStep>
    )
  } else if (checkedBefore) {
    guidance = (
      <NextStep>
        Add more photos (for example of the back rows) or remove unclear ones, then press <strong>Check again</strong>.
        SnapClass looks at all photos together.
      </NextStep>
    )
  } else {
    guidance = (
      <NextStep>
        Take or choose <strong>1 to 10 photos</strong> of your class, then press <strong>Check attendance</strong>.
      </NextStep>
    )
  }

  const buttonLabel = checkedBefore || session.status === 'FAILED' ? 'Check again' : 'Check attendance'
  let hint = 'Ready when you are.'
  if (!canCheck) hint = onBack ? 'Add at least one new photo, or go back to the list.' : 'Add at least one photo first.'

  return (
    <>
      {onBack && (
        <button type="button" className="btn btn-ghost back-to-list" onClick={onBack}>
          <IconArrowLeft size={18} /> Back to the list (no changes)
        </button>
      )}
      {guidance}
      {session.status === 'FAILED' && session.error && <p className="muted small">Details: {session.error}</p>}

      <details className="tips">
        <summary>
          <IconBulb size={18} /> Tips for good class photos
        </summary>
        <ul>
          {PHOTO_TIPS.map((tip) => (
            <li key={tip}>{tip}</li>
          ))}
        </ul>
      </details>

      <UploadedPhotos session={session} run={run} />

      <div className="photo-options">
        <div className="option-card">
          <h3>
            <span className="option-number">A</span> Use the camera
          </h3>
          <p className="muted small">Best on a phone or tablet. Uses the back camera.</p>
          <CameraCapture
            facingMode="environment"
            guide="class"
            openLabel="Take photos with camera"
            disabled={roomLeft <= 0}
            onCapture={(blob) => addPhotos([new File([blob], 'camera.jpg', { type: 'image/jpeg' })])}
          />
        </div>
        <div className="option-card">
          <h3>
            <span className="option-number">B</span> Use photos you already took
          </h3>
          <p className="muted small">Choose photos, or drag them here. Up to {MAX_PHOTOS} in total.</p>
          <Dropzone
            accept="image/jpeg,image/png"
            multiple
            disabled={roomLeft <= 0}
            onFiles={addPhotos}
            icon={<IconImage size={26} />}
            title={roomLeft <= 0 ? 'Photo limit reached' : 'Choose photos from this device'}
            hint="JPG or PNG"
          />
        </div>
      </div>

      {photos.length > 0 && (
        <div className="card">
          <div className="card-title-row spread">
            <h3 className="card-heading">New photos (not uploaded yet)</h3>
            <span className="tag tag-purple">
              {session.photo_count + photos.length} of {MAX_PHOTOS}
            </span>
          </div>
          <div className="thumb-grid">
            {photos.map((photo, index) => (
              <div key={index} className="thumb">
                <ImagePreview blob={photo} alt={`New class photo ${index + 1}`} />
                <button
                  type="button"
                  className="thumb-remove"
                  aria-label={`Remove new photo ${index + 1}`}
                  title="Remove this photo"
                  onClick={() => setPhotos(photos.filter((_, i) => i !== index))}
                >
                  <IconX size={16} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {session.audio_count === 0 && (
        <details className="card optional">
          <summary>
            <IconMic size={18} /> Add a roll-call recording <span className="tag">Optional</span>
          </summary>
          <p className="muted small">
            Record up to 60 seconds while each student says &quot;present&quot; and their roll number. This helps when a face is
            hidden in the photo.
          </p>
          <AudioRecorder maxSeconds={60} label="Start recording" onRecorded={setAudio} />
          <Dropzone
            accept="audio/*"
            onFiles={(files) => setAudio(files.find((file) => file.type.startsWith('audio/')) || null)}
            icon={<IconUpload size={20} />}
            title="Or choose a recording"
          />
          {audio && (
            <div className="audio-selected">
              <AudioPreview blob={audio} />
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setAudio(null)}>
                <IconX size={16} /> Remove
              </button>
            </div>
          )}
        </details>
      )}

      {myChoices > 0 && (
        <div className="card keep-choices">
          <p>
            <IconCheckCircle size={16} className="text-green" /> Your Present/Absent choices for <strong>{myChoices}</strong>{' '}
            student(s) will be kept when SnapClass checks again.
          </p>
          <label className="checkbox">
            <input type="checkbox" checked={clearChoices} onChange={(e) => setClearChoices(e.target.checked)} />
            Start fresh: also clear my choices
          </label>
        </div>
      )}

      <div className="action-bar">
        <span className="muted">{hint}</span>
        <button type="button" className="btn btn-primary btn-lg" disabled={busy || !canCheck} onClick={checkAttendance}>
          <IconScanFace /> {busy ? 'Uploading…' : buttonLabel}
        </button>
      </div>
    </>
  )
}

// ---------- Step 2: waiting ----------

function ProcessingStep() {
  return (
    <div className="card processing-card" role="status">
      <div className="scan-animation" aria-hidden="true">
        <IconScanFace size={40} />
      </div>
      <h2>Checking the photos…</h2>
      <p className="muted">This usually takes a few seconds. Please stay on this page; it will update by itself.</p>
    </div>
  )
}

// ---------- Step 3: teacher review ----------

// What will be saved if the teacher does nothing (null = the teacher must decide).
function proposedStatus(result) {
  if (result.teacher_decision) return result.teacher_decision
  if (!result.has_biometrics || result.decision === 'UNCERTAIN') return null
  return result.decision === 'PRESENT' ? 'PRESENT' : 'ABSENT'
}

const SUGGESTION_LABELS = {
  PRESENT: 'Found in photo',
  UNCERTAIN: 'Not sure, please check',
  NOT_DETECTED: 'Not found in photo',
}

function FaceThumb({ url, name }) {
  return url ? (
    <img className="crop" src={url} alt={`Face from the class photo matched to ${name}`} />
  ) : (
    <span className="crop crop-empty" aria-hidden="true">
      <IconUser size={22} />
    </span>
  )
}

function filterStudents(results, statuses, filter, search) {
  const text = search.trim().toLowerCase()
  return results.filter((r, i) => {
    const matchesFilter =
      filter === 'all' ||
      (filter === 'check' && statuses[i] === null) ||
      (filter === 'present' && statuses[i] === 'PRESENT') ||
      (filter === 'absent' && statuses[i] === 'ABSENT')
    const matchesText = !text || `${r.name} ${r.roll_no || ''}`.toLowerCase().includes(text)
    return matchesFilter && matchesText
  })
}

// "Ask for new face photo" / "requested" controls on one review row.
function FaceRequestControl({ result, onAsk, onCancel }) {
  if (!result.has_biometrics) return null
  if (result.face_update_requested) {
    return (
      <span className="row-note">
        <span className="tag tag-purple">New face photo requested</span>
        <button type="button" className="link-button small" onClick={() => onCancel(result)}>
          Cancel request
        </button>
      </span>
    )
  }
  if (result.decision === 'PRESENT') return null // recognised fine, nothing to fix
  return (
    <button type="button" className="btn btn-ghost btn-sm ask-photo" onClick={() => onAsk(result)}>
      <IconCamera size={16} /> Ask for new face photo
    </button>
  )
}

function ReviewStep({ session, run, onChangePhotos }) {
  const { results } = session
  const statuses = results.map(proposedStatus)
  const counts = {
    check: statuses.filter((s) => s === null).length,
    present: statuses.filter((s) => s === 'PRESENT').length,
    absent: statuses.filter((s) => s === 'ABSENT').length,
  }
  const [filter, setFilter] = useState(counts.check > 0 ? 'check' : 'all')
  const [search, setSearch] = useState('')
  const [showDetails, setShowDetails] = useState(false)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [asking, setAsking] = useState(null) // student we are asking for a new face photo
  const toast = useToast()

  const statusById = Object.fromEntries(results.map((r, i) => [r.student_id, statuses[i]]))
  const visible = filterStudents(results, statuses, filter, search)

  function decide(studentId, decision) {
    return run(() => api(`/sessions/${session.id}/results/${studentId}`, { method: 'PATCH', body: { teacher_decision: decision } }))
  }

  async function cancelRequest(result) {
    const ok = await run(() =>
      api(`/classes/${session.class_id}/students/${result.student_id}/face-update-request`, { method: 'DELETE' }),
    )
    if (ok) toast(`Request for ${result.name} cancelled.`)
  }

  async function save() {
    const ok = await run(() => api(`/sessions/${session.id}/finalize`, { method: 'POST' }))
    if (ok) {
      setConfirmOpen(false)
      toast(`Attendance saved: ${counts.present} present, ${counts.absent} absent.`)
    }
  }

  return (
    <>
      {counts.check > 0 ? (
        <NextStep tone="warning">
          <strong>{counts.check} student(s)</strong> need your decision. Press <strong>Present</strong> or <strong>Absent</strong> for each,
          then press <strong>Save attendance</strong>.
        </NextStep>
      ) : (
        <NextStep>
          Everything is ready. Quickly look through the list, then press <strong>Save attendance</strong>. Nothing is saved until you do.
        </NextStep>
      )}

      {results.length > 0 && counts.present === 0 && session.summary.uncertain === 0 && (
        <Alert tone="warning">
          Nobody was recognised in the photos. Check that the photos show faces clearly, or mark students by hand below.
        </Alert>
      )}

      {/* Missing students? The teacher can add photos (e.g. of the back rows) and check again before saving. */}
      <div className={counts.absent > 0 || counts.check > 0 ? 'card change-photos highlight-card' : 'card change-photos'}>
        <div>
          <h3 className="card-heading">
            <IconImage size={18} /> Some students not found?
          </h3>
          <p className="muted small">
            Add more photos (for example of the back rows) or remove an unclear one, and SnapClass checks again. Your choices
            are kept.
          </p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={onChangePhotos}>
          <IconCamera size={18} /> Add or change photos ({session.photo_count} of {MAX_PHOTOS} used)
        </button>
      </div>

      <div className="list-toolbar">
        <FilterChips
          value={filter}
          onChange={setFilter}
          options={[
            { value: 'check', label: 'Needs check', count: counts.check, tone: 'amber' },
            { value: 'present', label: 'Present', count: counts.present, tone: 'green' },
            { value: 'absent', label: 'Absent', count: counts.absent, tone: 'red' },
            { value: 'all', label: 'Everyone', count: results.length },
          ]}
        />
        <SearchInput value={search} onChange={setSearch} />
      </div>
      <div className="review-help">
        <HelpTip label='What does "Not sure" mean?'>
          The face in the photo was unclear, or looked similar to another student. SnapClass never guesses, so you decide.
        </HelpTip>
        <HelpTip label="A student is here but was not recognised?">
          Mark them Present by hand, then press &quot;Ask for new face photo&quot;. Their old selfie may be out of date. Until they
          upload a new one, SnapClass will not mark them present automatically.
        </HelpTip>
        <label className="checkbox small">
          <input type="checkbox" checked={showDetails} onChange={(e) => setShowDetails(e.target.checked)} />
          Show match details
        </label>
      </div>

      {visible.length === 0 ? (
        <div className="empty-state compact">
          {filter === 'check' && !search ? (
            <>
              <div className="empty-icon">
                <IconCheckCircle size={26} />
              </div>
              <h3>All checked</h3>
              <p className="muted">Press &quot;Save attendance&quot; below when you are ready.</p>
            </>
          ) : (
            <>
              <div className="empty-icon">
                <IconSearch size={26} />
              </div>
              <p className="muted">No students in this list.</p>
            </>
          )}
        </div>
      ) : (
        <ul className="review-list">
          {visible.map((r) => {
            const status = statusById[r.student_id]
            return (
              <li key={r.student_id} className={status === null ? 'review-row needs-check' : 'review-row'}>
                <FaceThumb url={r.crop_url} name={r.name} />
                <div className="review-info">
                  <strong>{r.name}</strong>
                  <span className="muted small">{r.roll_no}</span>
                  {!r.has_biometrics ? (
                    <span className="tag tag-amber">No face setup: mark by hand</span>
                  ) : r.face_update_pending ? (
                    <span className="tag tag-purple">Waiting for a new face photo: not marked automatically</span>
                  ) : (
                    <Badge value={r.decision} label={SUGGESTION_LABELS[r.decision]} />
                  )}
                  <FaceRequestControl result={r} onAsk={setAsking} onCancel={cancelRequest} />
                  {showDetails && (
                    <span className="muted small mono">
                      {r.face_distance !== null ? `face distance ${r.face_distance.toFixed(2)}` : 'no face match'}
                      {r.voice_score !== null ? ` · voice ${r.voice_score.toFixed(2)}` : ''}
                    </span>
                  )}
                </div>
                <div className="toggle-group big" role="group" aria-label={`Attendance for ${r.name}`}>
                  <button
                    type="button"
                    className={status === 'PRESENT' ? 'toggle on-green' : 'toggle'}
                    aria-pressed={status === 'PRESENT'}
                    onClick={() => decide(r.student_id, 'PRESENT')}
                  >
                    <IconCheck size={16} /> Present
                  </button>
                  <button
                    type="button"
                    className={status === 'ABSENT' ? 'toggle on-red' : 'toggle'}
                    aria-pressed={status === 'ABSENT'}
                    onClick={() => decide(r.student_id, 'ABSENT')}
                  >
                    <IconX size={16} /> Absent
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {session.unmatched_faces.length > 0 && (
        <details className="card optional">
          <summary>
            <IconScanFace size={18} /> {session.unmatched_faces.length} face(s) we could not match to a student
          </summary>
          <p className="muted small">Visitors, students from another class, or faces that were too small or blurry. No action is needed.</p>
          <div className="crop-gallery">
            {session.unmatched_faces.map((face) => (
              <img key={face.id} className="crop large" src={face.crop_url} alt="Face that did not match any student" />
            ))}
          </div>
        </details>
      )}

      <div className="action-bar">
        <span className={counts.check ? 'text-amber' : 'muted'}>
          {counts.check ? `${counts.check} still need a decision` : `${counts.present} present · ${counts.absent} absent`}
        </span>
        <button type="button" className="btn btn-primary btn-lg" disabled={counts.check > 0} onClick={() => setConfirmOpen(true)}>
          <IconCheckCircle /> Save attendance
        </button>
      </div>

      <FaceRequestDialog
        student={asking && { id: asking.student_id, name: asking.name }}
        classId={session.class_id}
        sessionId={session.id}
        onClose={() => setAsking(null)}
        onDone={() => {
          setAsking(null)
          run(async () => null) // reload so the row shows "requested"
        }}
      />

      <ConfirmDialog
        open={confirmOpen}
        title="Save this attendance?"
        message={`${counts.present} present and ${counts.absent} absent will be saved. You can still change a student later, but you will need to give a reason.`}
        confirmLabel="Yes, save"
        onConfirm={save}
        onCancel={() => setConfirmOpen(false)}
      />
    </>
  )
}

// ---------- Step 4: saved, with recorded changes ----------

const SOURCE_LABELS = {
  AI_CONFIRMED: 'Suggested by SnapClass, accepted by you',
  TEACHER_OVERRIDE: 'Set by you',
  MANUAL: 'Marked by hand',
}

function SavedStep({ session, run }) {
  const [editing, setEditing] = useState(null) // the student being changed
  const [reason, setReason] = useState('')
  const [search, setSearch] = useState('')
  const toast = useToast()

  const present = session.results.filter((r) => r.final_status === 'PRESENT').length
  const newStatus = editing?.final_status === 'PRESENT' ? 'ABSENT' : 'PRESENT'
  const text = search.trim().toLowerCase()
  const visible = session.results.filter((r) => !text || `${r.name} ${r.roll_no || ''}`.toLowerCase().includes(text))

  function openChange(result) {
    setEditing(result)
    setReason('')
  }

  async function saveChange(event) {
    event.preventDefault()
    const name = editing.name
    const ok = await run(() =>
      api(`/sessions/${session.id}/attendance/${editing.student_id}`, { method: 'PATCH', body: { status: newStatus, reason } }),
    )
    if (ok) {
      setEditing(null)
      toast(`${name} is now marked ${newStatus === 'PRESENT' ? 'present' : 'absent'}.`)
    }
  }

  return (
    <>
      <Alert tone="success">
        Attendance is saved: <strong>{present}</strong> of {session.results.length} students present.
      </Alert>
      <NextStep>Nothing else to do. If a student was marked wrongly, press &quot;Change&quot; next to their name.</NextStep>

      <div className="list-toolbar">
        <h3 className="section-title">Saved list</h3>
        <SearchInput value={search} onChange={setSearch} />
      </div>
      <ul className="review-list">
        {visible.map((r) => (
          <li key={r.student_id} className="review-row">
            <div className="review-info">
              <strong>{r.name}</strong>
              <span className="muted small">{r.roll_no}</span>
              <span className="muted small">{SOURCE_LABELS[r.final_source]}</span>
            </div>
            <Badge value={r.final_status} />
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => openChange(r)}>
              <IconEdit size={16} /> Change
            </button>
          </li>
        ))}
      </ul>

      <Dialog open={editing !== null} title="Change attendance" onClose={() => setEditing(null)}>
        {editing && (
          <form onSubmit={saveChange}>
            <p>
              Change <strong>{editing.name}</strong> from <Badge value={editing.final_status} /> to <Badge value={newStatus} />
            </p>
            <label className="field">
              <span>Why are you changing this? (required)</span>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                required
                minLength={3}
                maxLength={500}
                rows={3}
                placeholder="e.g. Came late with permission"
              />
              <small className="muted">The reason is kept in the college&apos;s records.</small>
            </label>
            <div className="dialog-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setEditing(null)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={reason.trim().length < 3}>
                Save change
              </button>
            </div>
          </form>
        )}
      </Dialog>
    </>
  )
}
