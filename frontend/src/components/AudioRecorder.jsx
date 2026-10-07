import { useEffect, useRef, useState } from 'react'
import { IconMic, IconStop } from './Icons.jsx'

// Record audio from the microphone. Stops by itself after maxSeconds.
// Calls onRecorded(blob) when a recording is finished.
export default function AudioRecorder({ maxSeconds, onRecorded, label = 'Record' }) {
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState('')
  const recorderRef = useRef(null)
  const timersRef = useRef([])

  function clearTimers() {
    timersRef.current.forEach((id) => {
      clearTimeout(id)
      clearInterval(id)
    })
    timersRef.current = []
  }

  // Stop everything if the component disappears while recording.
  useEffect(
    () => () => {
      clearTimers()
      if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
    },
    [],
  )

  async function start() {
    setError('')
    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setError('Microphone is not available. Please allow microphone access in your browser.')
      return
    }
    const recorder = new MediaRecorder(stream)
    const chunks = []
    recorder.ondataavailable = (event) => chunks.push(event.data)
    recorder.onstop = () => {
      stream.getTracks().forEach((track) => track.stop())
      clearTimers()
      setRecording(false)
      onRecorded(new Blob(chunks, { type: recorder.mimeType }))
    }
    recorder.start()
    recorderRef.current = recorder
    setRecording(true)
    setSeconds(0)
    timersRef.current.push(setInterval(() => setSeconds((s) => s + 1), 1000))
    timersRef.current.push(setTimeout(() => recorder.state === 'recording' && recorder.stop(), maxSeconds * 1000))
  }

  function stop() {
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
  }

  if (recording) {
    return (
      <div className="recorder-live" role="status">
        <span className="rec-dot" aria-hidden="true" />
        <span className="rec-time">
          {seconds}s <span className="muted">/ {maxSeconds}s</span>
        </span>
        <div className="progress">
          <div className="progress-bar" style={{ width: `${Math.min(100, (seconds / maxSeconds) * 100)}%` }} />
        </div>
        <button type="button" className="btn btn-danger btn-sm" onClick={stop}>
          <IconStop size={16} /> Stop
        </button>
      </div>
    )
  }

  return (
    <div>
      <button type="button" className="btn btn-secondary" onClick={start}>
        <IconMic /> {label}
      </button>
      {error && <p className="field-error">{error}</p>}
    </div>
  )
}
