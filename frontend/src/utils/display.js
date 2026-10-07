// Display preferences (text size, contrast) for users with different eyesight.
// Saved in this browser only, and applied as attributes on <html> that the CSS reads.

const STORAGE_KEY = 'snapclass.display'
export const DEFAULT_DISPLAY = { textSize: 'normal', contrast: 'normal' }

export function loadDisplay() {
  try {
    return { ...DEFAULT_DISPLAY, ...JSON.parse(localStorage.getItem(STORAGE_KEY)) }
  } catch {
    return DEFAULT_DISPLAY
  }
}

export function applyDisplay(settings) {
  document.documentElement.dataset.textSize = settings.textSize
  document.documentElement.dataset.contrast = settings.contrast
}

export function saveDisplay(settings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch {
    // storage blocked (private mode): the setting still applies until the page is closed
  }
  applyDisplay(settings)
}
