import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { ToastProvider } from './components/Toast.jsx'
import { applyDisplay, loadDisplay } from './utils/display.js'
import './styles.css'
import './usability.css'

// Apply the saved text size / contrast before the first paint (no flicker).
applyDisplay(loadDisplay())

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </StrictMode>,
)
