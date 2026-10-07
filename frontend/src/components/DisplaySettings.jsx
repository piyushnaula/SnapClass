import { useState } from 'react'
import { loadDisplay, saveDisplay } from '../utils/display.js'
import { Dialog } from './ui.jsx'

const TEXT_SIZES = [
  { value: 'normal', label: 'Normal', sample: 'Aa' },
  { value: 'large', label: 'Large', sample: 'Aa' },
  { value: 'xlarge', label: 'Extra large', sample: 'Aa' },
]

const CONTRASTS = [
  { value: 'normal', label: 'Standard', text: 'Soft grey text' },
  { value: 'high', label: 'High contrast', text: 'Brighter text and borders' },
]

// Lets each person choose a comfortable text size and contrast.
export default function DisplaySettings({ open, onClose }) {
  const [settings, setSettings] = useState(loadDisplay)

  function change(field, value) {
    const next = { ...settings, [field]: value }
    setSettings(next)
    saveDisplay(next) // applies immediately, so the user sees the effect
  }

  return (
    <Dialog open={open} title="Text size and contrast" onClose={onClose}>
      <p className="muted small">Changes apply right away and are remembered on this device.</p>

      <fieldset className="choice-group">
        <legend>Text size</legend>
        <div className="choice-row">
          {TEXT_SIZES.map((option) => (
            <label key={option.value} className={settings.textSize === option.value ? 'choice selected' : 'choice'}>
              <input
                type="radio"
                name="textSize"
                className="visually-hidden"
                checked={settings.textSize === option.value}
                onChange={() => change('textSize', option.value)}
              />
              <span className={`choice-sample size-${option.value}`}>{option.sample}</span>
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="choice-group">
        <legend>Contrast</legend>
        <div className="choice-row two">
          {CONTRASTS.map((option) => (
            <label key={option.value} className={settings.contrast === option.value ? 'choice selected' : 'choice'}>
              <input
                type="radio"
                name="contrast"
                className="visually-hidden"
                checked={settings.contrast === option.value}
                onChange={() => change('contrast', option.value)}
              />
              <strong>{option.label}</strong>
              <span className="muted small">{option.text}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className="dialog-actions">
        <button type="button" className="btn btn-primary" onClick={onClose}>
          Done
        </button>
      </div>
    </Dialog>
  )
}
