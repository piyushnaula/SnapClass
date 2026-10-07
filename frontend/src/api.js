// A small wrapper around fetch():
// - adds the access token to every request
// - when the token has expired (401), gets a new one with the refresh token and retries once
// - turns API errors into normal JavaScript errors with a readable message

const BASE = '/api/v1'
const STORAGE_KEY = 'snapclass.auth'

export function getAuth() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY))
  } catch {
    return null
  }
}

// data = { access_token, refresh_token, user }
export function saveAuth(data) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
}

export function clearAuth() {
  localStorage.removeItem(STORAGE_KEY)
}

// Error codes from the server whose default message is too technical for most users.
// (HCI: error messages in plain language that say how to recover.)
const FRIENDLY_ERRORS = {
  VALIDATION_ERROR: 'Some information is missing or not in the right format. Please check the form and try again.',
  INTERNAL_ERROR: 'Something went wrong on our side. Please wait a minute and try again.',
  INVALID_TRANSITION: 'This attendance has already moved to the next step. Please reload the page.',
  FILE_TOO_LARGE: 'This file is too large. Photos must be under 8 MB and audio under 10 MB.',
  INVALID_FILE_TYPE: 'This file type is not supported. Please choose a JPG or PNG photo (or an audio recording).',
}

// If several requests fail at the same moment, they share ONE refresh call.
let refreshPromise = null

async function refreshTokens() {
  const auth = getAuth()
  if (!auth?.refresh_token) return false
  const response = await fetch(`${BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: auth.refresh_token }),
  })
  if (!response.ok) {
    clearAuth()
    return false
  }
  saveAuth(await response.json())
  return true
}

/**
 * Call the API.
 *   api('/classes')                                   → GET, returns JSON
 *   api('/classes', { method: 'POST', body: {...} })  → sends JSON
 *   api('/sessions/1/media', { method: 'POST', form }) → sends FormData (files)
 *   api('/report?format=csv', { raw: true })          → returns the Response itself
 */
export async function api(path, { method = 'GET', body, form, raw = false } = {}, canRetry = true) {
  const headers = {}
  const auth = getAuth()
  if (auth?.access_token) headers.Authorization = `Bearer ${auth.access_token}`

  let payload
  if (form) {
    payload = form // the browser sets the multipart Content-Type itself
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  let response
  try {
    response = await fetch(BASE + path, { method, headers, body: payload })
  } catch {
    // fetch() itself fails only when the server cannot be reached at all.
    throw new Error('Cannot reach SnapClass. Please check your internet connection and try again.')
  }

  if (response.status === 401 && canRetry && auth?.refresh_token) {
    refreshPromise = refreshPromise || refreshTokens().finally(() => (refreshPromise = null))
    if (await refreshPromise) return api(path, { method, body, form, raw }, false)
    window.dispatchEvent(new Event('snapclass:logout')) // App.jsx listens and shows the login page
  }

  if (!response.ok) {
    let message = 'Something went wrong. Please try again.'
    try {
      const data = await response.json()
      message = FRIENDLY_ERRORS[data.error?.code] || data.error?.message || message
    } catch {
      // response was not JSON; keep the default message
    }
    if (response.status >= 500 && response.status !== 503) message = FRIENDLY_ERRORS.INTERNAL_ERROR
    throw new Error(message)
  }

  if (raw) return response
  if (response.status === 204) return null
  return response.json()
}
