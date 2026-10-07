// Small pop-up messages ("Attendance saved") that disappear by themselves.
// HCI: visibility of system status — every important action gets clear feedback.
// Usage:  const toast = useToast();  toast('Link copied')  or  toast('Could not save', 'error')
import { createContext, useCallback, useContext, useState } from 'react'
import { IconAlert, IconCheckCircle, IconX } from './Icons.jsx'

const ToastContext = createContext(() => {})

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => setToasts((list) => list.filter((t) => t.id !== id)), [])

  const show = useCallback(
    (message, tone = 'success') => {
      const id = `${Date.now()}-${Math.random()}`
      setToasts((list) => [...list.slice(-2), { id, message, tone }]) // at most 3 on screen
      setTimeout(() => dismiss(id), 4500)
    },
    [dismiss],
  )

  return (
    <ToastContext.Provider value={show}>
      {children}
      {/* aria-live: screen readers read new messages aloud. */}
      <div className="toast-area" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.tone}`}>
            {t.tone === 'error' ? <IconAlert /> : <IconCheckCircle />}
            <span>{t.message}</span>
            <button type="button" className="toast-close" aria-label="Close message" onClick={() => dismiss(t.id)}>
              <IconX size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}
