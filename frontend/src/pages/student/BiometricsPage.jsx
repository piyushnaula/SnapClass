import { useState } from 'react'
import { api } from '../../api.js'
import AudioRecorder from '../../components/AudioRecorder.jsx'
import CameraCapture from '../../components/CameraCapture.jsx'
import { IconCheck, IconCheckCircle, IconImage, IconMic, IconShield, IconTrash, IconUpload, IconX } from '../../components/Icons.jsx'
import { useToast } from '../../components/Toast.jsx'
import {
  Alert,
  AudioPreview,
  ConfirmDialog,
  Dropzone,
  ErrorBox,
  ImagePreview,
  NextStep,
  PageHeader,
  Skeleton,
} from '../../components/ui.jsx'
import { useInterval, useLoad } from '../../hooks.js'
import { compressImage } from '../../utils/image.js'

// Guided setup: 1 permission → 2 face photos → 3 voice (optional). One clear step at a time.
export default function BiometricsPage() {
  const { data: status, error, loading, reload } = useLoad(() => api('/me/biometrics'), [])
  const waiting = status?.jobs.some((job) => job.status === 'QUEUED')

  // Poll while the uploaded photos/clips are still being checked.
  useInterval(reload, 2000, waiting)

  if (loading) return <Skeleton rows={4} />
  if (error) return <ErrorBox message={error} onRetry={reload} />

  const faceDone = status.face_samples > 0
  const voiceDone = status.voice_samples > 0
  const request = status.face_update_request // teacher asked for a new face photo
  const steps = [
    { label: 'Give permission', done: status.consent_current },
    { label: 'Add face photos', done: faceDone && !request },
    { label: 'Add voice (optional)', done: voiceDone },
  ]

  return (
    <>
      <PageHeader title="Face setup" subtitle="Lets your teacher's class photo mark your attendance automatically." />

      <ol className="setup-progress" aria-label="Setup progress">
        {steps.map((step, index) => (
          <li key={step.label} className={step.done ? 'done' : ''}>
            <span className="setup-dot">{step.done ? <IconCheck size={14} /> : index + 1}</span>
            {step.label}
          </li>
        ))}
      </ol>

      {waiting && <NextStep>We are checking what you uploaded. This takes a few seconds…</NextStep>}

      {request && !waiting && (
        <NextStep tone="warning">
          <strong>{request.requested_by}</strong> ({request.subject}) asked for a new face photo: &quot;{request.reason}&quot;. Please
          take 3–5 new photos below. Until you do, you will not be marked present automatically.
        </NextStep>
      )}

      {!status.consent_current ? (
        <ConsentStep onAccepted={reload} />
      ) : (
        <>
          {faceDone && !request && !waiting && (
            <Alert tone="success">
              <strong>You are all set.</strong> Your face is set up, so your attendance can be suggested from the class photo.
              {!voiceDone && ' Adding your voice is optional.'}
            </Alert>
          )}
          <LastResult jobs={status.jobs} />
          {faceDone && !request ? (
            <details className="card optional">
              <summary>
                <IconImage size={18} /> Retake my face photos
              </summary>
              <FaceStep onSubmitted={reload} />
            </details>
          ) : (
            <div className="card">
              <FaceStep onSubmitted={reload} />
            </div>
          )}
          <details className="card optional" open={faceDone && !voiceDone}>
            <summary>
              <IconMic size={18} /> {voiceDone ? 'Record my voice again' : 'Add my voice'} <span className="tag">Optional</span>
            </summary>
            <VoiceStep sentence={status.voice_sentence} onSubmitted={reload} />
          </details>
        </>
      )}
      <DeleteStep onDeleted={reload} hasData={faceDone || voiceDone || status.consent_current} />
    </>
  )
}

function ConsentStep({ onAccepted }) {
  const { data: consent, error, reload } = useLoad(() => api('/consent/current'), [])
  const [actionError, setActionError] = useState('')
  const toast = useToast()

  async function accept() {
    try {
      await api('/consent', { method: 'POST', body: { version: consent.version } })
      toast('Thank you. Next, add a few photos of your face.')
      onAccepted()
    } catch (err) {
      setActionError(err.message)
    }
  }

  if (!consent) return <ErrorBox message={error} onRetry={reload} />
  return (
    <div className="card">
      <h2 className="card-heading">
        <IconShield size={20} /> Your permission
      </h2>
      <p className="muted">Before we use your face, please read what happens with your data. In short:</p>
      <ul className="check-list">
        <li>Your photos are used only to mark your attendance in your own classes.</li>
        <li>Your setup photos are deleted right after processing. Only a numeric face code is kept.</li>
        <li>A teacher always checks the result before anything is saved.</li>
        <li>You can remove your data at any time on this page.</li>
      </ul>
      <details className="read-more">
        <summary>Read the full permission text (version {consent.version})</summary>
        <pre className="consent">{consent.body}</pre>
      </details>
      <ErrorBox message={actionError} />
      <div className="button-row">
        <button type="button" className="btn btn-primary btn-lg" onClick={accept}>
          <IconCheck /> I agree, continue
        </button>
      </div>
      <p className="muted small">Saying no is fine: your teacher will mark your attendance by hand.</p>
    </div>
  )
}

// Shows only the latest result, in plain words.
function LastResult({ jobs }) {
  const last = jobs.find((job) => job.status !== 'QUEUED')
  if (!last || last.status !== 'FAILED') return null
  return (
    <div className="alert alert-error" role="alert">
      <span className="alert-text">
        <strong>Your last {last.kind === 'FACE' ? 'photos' : 'voice clips'} could not be used.</strong> {last.message} Please try again.
      </span>
    </div>
  )
}

const FACE_TIPS = ['Only your face in the photo', 'Good light on your face', 'Look straight at the camera', 'No mask or sunglasses']

function FaceStep({ onSubmitted }) {
  const [photos, setPhotos] = useState([]) // array of Blobs
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const toast = useToast()

  function addPhotos(newPhotos) {
    const images = newPhotos.filter((photo) => photo.type.startsWith('image/'))
    setPhotos((current) => [...current, ...images].slice(0, 5))
  }

  async function submit() {
    setBusy(true)
    setError('')
    try {
      const form = new FormData()
      for (const photo of photos) form.append('photos', await compressImage(photo, 1280), 'face.jpg')
      await api('/me/biometrics/face', { method: 'POST', form })
      setPhotos([])
      toast('Photos sent. We are checking them now.')
      onSubmitted()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <h2 className="card-heading">Add 3 to 5 photos of your face</h2>
      <ul className="tip-chips">
        {FACE_TIPS.map((tip) => (
          <li key={tip}>
            <IconCheck size={14} /> {tip}
          </li>
        ))}
      </ul>
      <div className="photo-options">
        <div className="option-card">
          <CameraCapture facingMode="user" guide="face" openLabel="Take photos with camera" onCapture={(blob) => addPhotos([blob])} disabled={photos.length >= 5} />
        </div>
        <div className="option-card">
          <Dropzone
            accept="image/jpeg,image/png"
            multiple
            disabled={photos.length >= 5}
            onFiles={addPhotos}
            icon={<IconImage size={22} />}
            title="Choose photos from this device"
            hint="JPG or PNG"
          />
        </div>
      </div>

      <div className="photo-counter" role="status">
        <span className={photos.length >= 3 ? 'text-green' : ''}>
          {photos.length} of 5 photos {photos.length >= 3 && <IconCheckCircle size={16} />}
        </span>
        <span className="muted small">{photos.length < 3 ? `${3 - photos.length} more needed` : 'Enough photos'}</span>
      </div>
      {photos.length > 0 && (
        <div className="thumb-grid">
          {photos.map((photo, index) => (
            <div key={index} className="thumb">
              <ImagePreview blob={photo} alt={`Your photo ${index + 1}`} />
              <button
                type="button"
                className="thumb-remove"
                aria-label={`Remove photo ${index + 1}`}
                title="Remove this photo"
                onClick={() => setPhotos(photos.filter((_, i) => i !== index))}
              >
                <IconX size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
      <ErrorBox message={error} />
      <button type="button" className="btn btn-primary btn-block btn-lg" onClick={submit} disabled={busy || photos.length < 3}>
        <IconUpload /> {busy ? 'Sending…' : photos.length < 3 ? 'Add at least 3 photos' : `Save my ${photos.length} photos`}
      </button>
    </>
  )
}

function VoiceStep({ sentence, onSubmitted }) {
  const [clips, setClips] = useState([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const toast = useToast()

  async function submit() {
    setBusy(true)
    setError('')
    try {
      const form = new FormData()
      clips.forEach((clip, i) => form.append('clips', clip, `clip-${i + 1}`))
      await api('/me/biometrics/voice', { method: 'POST', form })
      setClips([])
      toast('Voice clips sent. We are checking them now.')
      onSubmitted()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <p className="muted">
        Record yourself reading this sentence <strong>3 times</strong> in a quiet place (about 5–8 seconds each). Recording stops by
        itself.
      </p>
      <blockquote className="quote">{sentence}</blockquote>
      <ul className="clip-list">
        {[0, 1, 2].map((index) => (
          <li key={index} className={clips[index] ? 'clip done' : 'clip'}>
            <span className="clip-number">{clips[index] ? <IconCheck size={14} /> : index + 1}</span>
            {clips[index] ? (
              <>
                <AudioPreview blob={clips[index]} />
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setClips(clips.filter((_, i) => i !== index))}>
                  <IconX size={16} /> Redo
                </button>
              </>
            ) : (
              <span className="muted small">Recording {index + 1}</span>
            )}
          </li>
        ))}
      </ul>
      {clips.length < 3 && (
        <AudioRecorder maxSeconds={8} label={`Record ${clips.length + 1} of 3`} onRecorded={(blob) => setClips((c) => [...c, blob])} />
      )}
      <ErrorBox message={error} />
      <button type="button" className="btn btn-primary btn-block btn-lg" onClick={submit} disabled={busy || clips.length !== 3}>
        <IconUpload /> {busy ? 'Sending…' : clips.length < 3 ? `${3 - clips.length} recording(s) left` : 'Save my voice'}
      </button>
    </>
  )
}

function DeleteStep({ onDeleted, hasData }) {
  const [open, setOpen] = useState(false)
  const [error, setError] = useState('')
  const toast = useToast()

  async function erase() {
    try {
      await api('/me/biometrics', { method: 'DELETE' })
      setOpen(false)
      toast('Your face and voice data has been removed.')
      onDeleted()
    } catch (err) {
      setOpen(false)
      setError(err.message)
    }
  }

  if (!hasData) return null
  return (
    <details className="card danger-zone optional">
      <summary>
        <IconTrash size={18} /> Remove my face and voice data
      </summary>
      <p className="muted small">
        This deletes your face and voice data right away and withdraws your permission. Your attendance history stays. Your teacher will
        then mark you by hand.
      </p>
      <ErrorBox message={error} />
      <button type="button" className="btn btn-danger" onClick={() => setOpen(true)}>
        <IconTrash /> Remove my data
      </button>
      <ConfirmDialog
        open={open}
        title="Remove your face and voice data?"
        message="This cannot be undone. You can set up your face again later if you change your mind."
        confirmLabel="Yes, remove it"
        danger
        onConfirm={erase}
        onCancel={() => setOpen(false)}
      />
    </details>
  )
}

