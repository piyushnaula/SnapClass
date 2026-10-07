import { useId } from 'react'

// The SnapClass logo: a camera viewfinder (the class photo) with a check mark
// inside (attendance confirmed). Same drawing as public/logo.svg (the favicon).
export function LogoMark({ size = 32 }) {
  // Each logo on the page needs its own gradient id, otherwise they clash.
  const gradientId = `logo-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#a78bfa" />
          <stop offset="1" stopColor="#6d28d9" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill={`url(#${gradientId})`} />
      <path
        d="M9 13v-3a1 1 0 0 1 1-1h3M19 9h3a1 1 0 0 1 1 1v3M23 19v3a1 1 0 0 1-1 1h-3M13 23h-3a1 1 0 0 1-1-1v-3"
        fill="none"
        stroke="#fff"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M12.5 16.3l2.4 2.4 4.6-4.9" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

// Logo mark + the "SnapClass" word.
export default function Logo({ size = 32, showText = true }) {
  return (
    <span className="logo">
      <LogoMark size={size} />
      {showText && (
        <span className="logo-text">
          Snap<span>Class</span>
        </span>
      )}
    </span>
  )
}
