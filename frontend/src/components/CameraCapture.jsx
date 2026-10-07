import { useEffect, useRef, useState } from 'react'
import { IconCamera, IconSwitchCamera, IconX } from './Icons.jsx'

// Take photos with the device camera. Calls onCapture(blob) for every photo taken.
//
//   facingMode: 'user' (front camera, for a selfie) or 'environment' (back camera, for the class)
//   guide:      'face' shows an oval to place your face in, 'class' shows a frame for the whole room
//
// A live camera preview only works on secure pages (https or localhost). When a phone
// opens SnapClass over plain http, we fall back to the phone's own camera app instead.
export default function CameraCapture({
  onCapture,
  facingMode = 'user',
  guide = 'face',
  disabled = false,
  openLabel = 'Open camera',
}) {
  const liveCameraAvailable = window.isSecureContext && Boolean(navigator.mediaDevices?.getUserMedia)
  const videoRef = useRef(null)
  const [stream, setStream] = useState(null)
  const [facing, setFacing] = useState(facingMode)
  const [error, setError] = useState('')
  const [flash, setFlash] = useState(false)
  const [taken, setTaken] = useState(0)

  // Turn the camera off when the component disappears or the stream changes.
  useEffect(() => {
    return () => stream?.getTracks().forEach((track) => track.stop())
  }, [stream])

  async function start(mode = facing) {
    setError('')
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: mode, width: { ideal: 1920 }, height: { ideal: 1080 } },
      })
      videoRef.current.srcObject = media
      setStream(media)
      setFacing(mode)
    } catch {
      setError('We could not open the camera. Please allow camera access in your browser, or choose photos from your device instead.')
    }
  }

  function stop() {
    setStream(null)
    setTaken(0)
  }

  function capture() {
    const video = videoRef.current
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0)
    canvas.toBlob(
      (blob) => {
        if (!blob) return
        onCapture(blob)
        setTaken((n) => n + 1)
      },
      'image/jpeg',
      0.92,
    )
    // A short white flash tells the user the photo was taken (feedback).
    setFlash(true)
    setTimeout(() => setFlash(false), 180)
  }

  // Fallback: the phone's own camera app (works without https).
  if (!liveCameraAvailable) {
    return (
      <label className={disabled ? 'btn btn-secondary btn-lg disabled' : 'btn btn-secondary btn-lg'}>
        <IconCamera /> {openLabel}
        <input
          type="file"
          accept="image/*"
          capture={facingMode}
          className="visually-hidden"
          disabled={disabled}
          onChange={(event) => {
            Array.from(event.target.files).forEach(onCapture)
            event.target.value = ''
          }}
        />
      </label>
    )
  }

  return (
    <div className="camera">
      {/* The video element always exists so the ref is ready when the camera starts. */}
      <div className={stream ? `camera-frame guide-${guide}` : 'hidden'}>
        <video ref={videoRef} autoPlay playsInline muted />
        <span className="camera-guide" aria-hidden="true" />
        <span className="camera-hint">
          {guide === 'face' ? 'Place your face inside the oval' : 'Fit as many students as possible in the frame'}
        </span>
        {flash && <span className="camera-flash" aria-hidden="true" />}
        {taken > 0 && (
          <span className="camera-count" role="status">
            {taken} photo{taken > 1 ? 's' : ''} taken
          </span>
        )}
      </div>

      {stream ? (
        <div className="camera-controls">
          <button type="button" className="icon-button large" onClick={() => start(facing === 'user' ? 'environment' : 'user')} aria-label="Switch between front and back camera" title="Switch camera">
            <IconSwitchCamera size={22} />
          </button>
          <button type="button" className="shutter" onClick={capture} disabled={disabled} aria-label="Take photo">
            <span />
          </button>
          <button type="button" className="icon-button large" onClick={stop} aria-label="Close camera" title="Close camera">
            <IconX size={22} />
          </button>
        </div>
      ) : (
        <button type="button" className="btn btn-secondary btn-lg" onClick={() => start(facingMode)} disabled={disabled}>
          <IconCamera /> {openLabel}
        </button>
      )}
      {disabled && stream && <p className="muted small center">Photo limit reached. Remove a photo to take another.</p>}
      {error && <p className="field-error">{error}</p>}
    </div>
  )
}
