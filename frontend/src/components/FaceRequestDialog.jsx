import { useState } from 'react'
import { api } from '../api.js'
import { useToast } from './Toast.jsx'
import { Alert, Dialog, ErrorBox } from './ui.jsx'

// Ready-made reasons, so the teacher only has to tap (recognition over recall).
const REASONS = [
  'Not recognised in the class photo',
  'The face photo looks old',
  'The face photo looks like a different person',
]

// Teacher asks a student to upload a new face photo.
// student: { id, name }   classId: the class   sessionId: the lecture (optional)
export default function FaceRequestDialog({ student, classId, sessionId, onClose, onDone }) {
  const [choice, setChoice] = useState(REASONS[0])
  const [other, setOther] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const toast = useToast()

  const reason = choice === 'other' ? other.trim() : choice

  async function send(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api(`/classes/${classId}/students/${student.id}/face-update-request`, {
        method: 'POST',
        body: { reason, session_id: sessionId || null },
      })
      toast(`Request sent. ${student.name} will be asked to upload a new face photo when they sign in.`)
      onDone()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={student !== null} title="Ask for a new face photo" onClose={onClose}>
      {student && (
        <form onSubmit={send}>
          <p>
            <strong>{student.name}</strong> will see your request every time they sign in.
          </p>
          <Alert tone="warning">
            Until they upload a new photo, SnapClass will <strong>not</strong> mark them present automatically in any lecture. You
            can still mark them present by hand.
          </Alert>
          <fieldset className="choice-group">
            <legend>Why?</legend>
            <div className="radio-list">
              {REASONS.map((text) => (
                <label key={text} className={choice === text ? 'radio-option selected' : 'radio-option'}>
                  <input type="radio" name="reason" checked={choice === text} onChange={() => setChoice(text)} />
                  {text}
                </label>
              ))}
              <label className={choice === 'other' ? 'radio-option selected' : 'radio-option'}>
                <input type="radio" name="reason" checked={choice === 'other'} onChange={() => setChoice('other')} />
                Another reason
              </label>
            </div>
          </fieldset>
          {choice === 'other' && (
            <label className="field">
              <span>Write the reason</span>
              <input value={other} onChange={(e) => setOther(e.target.value)} maxLength={300} autoFocus required minLength={3} />
            </label>
          )}
          <ErrorBox message={error} />
          <div className="dialog-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn-primary" disabled={busy || reason.length < 3}>
              {busy ? 'Sending…' : 'Send request'}
            </button>
          </div>
        </form>
      )}
    </Dialog>
  )
}
