// A tiny router based on the URL hash, e.g. http://localhost:3000/#/classes/123
// Using the hash means the server never needs special setup for page URLs.
import { useEffect, useState } from 'react'

export function useRoute() {
  const [hash, setHash] = useState(window.location.hash)
  useEffect(() => {
    const onChange = () => setHash(window.location.hash)
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return hash.replace(/^#/, '') || '/'
}

export function navigate(path) {
  window.location.hash = path
}

// matchRoute('/classes/:id', '/classes/42') → { id: '42' }; no match → null
export function matchRoute(pattern, path) {
  const patternParts = pattern.split('/')
  const pathParts = path.split('?')[0].split('/')
  if (patternParts.length !== pathParts.length) return null
  const params = {}
  for (let i = 0; i < patternParts.length; i++) {
    if (patternParts[i].startsWith(':')) {
      params[patternParts[i].slice(1)] = decodeURIComponent(pathParts[i])
    } else if (patternParts[i] !== pathParts[i]) {
      return null
    }
  }
  return params
}

export function Link({ to, children, ...props }) {
  return (
    <a href={`#${to}`} {...props}>
      {children}
    </a>
  )
}
