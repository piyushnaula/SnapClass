// A small set of line icons drawn as inline SVG (no icon library needed).
// Every icon uses `currentColor`, so it takes the text color of its parent.
// Usage: <IconCamera />  or  <IconCamera size={20} />

function Icon({ size = 18, children, className = '' }) {
  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  )
}

export const IconCamera = (p) => (
  <Icon {...p}>
    <path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" />
    <circle cx="12" cy="13.5" r="3.5" />
  </Icon>
)

export const IconMic = (p) => (
  <Icon {...p}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0M12 18v3M8.5 21h7" />
  </Icon>
)

export const IconUsers = (p) => (
  <Icon {...p}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M18 14a6 6 0 0 1 3.5 6" />
  </Icon>
)

export const IconUser = (p) => (
  <Icon {...p}>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21a8 8 0 0 1 16 0" />
  </Icon>
)

export const IconCalendar = (p) => (
  <Icon {...p}>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M3 10h18M8 3v4M16 3v4" />
  </Icon>
)

export const IconChart = (p) => (
  <Icon {...p}>
    <path d="M3 20h18M7 16v-5M12 16V6M17 16v-8" />
  </Icon>
)

export const IconGrid = (p) => (
  <Icon {...p}>
    <rect x="3" y="3" width="7.5" height="7.5" rx="1.5" />
    <rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5" />
    <rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5" />
    <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5" />
  </Icon>
)

export const IconBook = (p) => (
  <Icon {...p}>
    <path d="M4 19.5V5a2 2 0 0 1 2-2h14v15H6a2 2 0 0 0-2 2 2 2 0 0 0 2 2h14" />
    <path d="M8 7h8" />
  </Icon>
)

export const IconCap = (p) => (
  <Icon {...p}>
    <path d="M2 9l10-5 10 5-10 5z" />
    <path d="M6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5M22 9v6" />
  </Icon>
)

export const IconLogout = (p) => (
  <Icon {...p}>
    <path d="M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3M16 16l4-4-4-4M20 12H9" />
  </Icon>
)

export const IconPlus = (p) => (
  <Icon {...p}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
)

export const IconUpload = (p) => (
  <Icon {...p}>
    <path d="M12 15V4M7 9l5-5 5 5M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
  </Icon>
)

export const IconDownload = (p) => (
  <Icon {...p}>
    <path d="M12 4v11M7 10l5 5 5-5M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
  </Icon>
)

export const IconCheck = (p) => (
  <Icon {...p}>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </Icon>
)

export const IconCheckCircle = (p) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M8.5 12.5l2.5 2.5 4.5-5" />
  </Icon>
)

export const IconX = (p) => (
  <Icon {...p}>
    <path d="M6 6l12 12M18 6L6 18" />
  </Icon>
)

export const IconAlert = (p) => (
  <Icon {...p}>
    <path d="M12 3.5l9.5 16.5h-19z" />
    <path d="M12 10v4.5M12 17.5v.01" />
  </Icon>
)

export const IconInfo = (p) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v6M12 7.5v.01" />
  </Icon>
)

export const IconTrash = (p) => (
  <Icon {...p}>
    <path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />
  </Icon>
)

export const IconCopy = (p) => (
  <Icon {...p}>
    <rect x="8" y="8" width="12" height="12" rx="2" />
    <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" />
  </Icon>
)

export const IconLink = (p) => (
  <Icon {...p}>
    <path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" />
  </Icon>
)

export const IconShield = (p) => (
  <Icon {...p}>
    <path d="M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z" />
    <path d="M9 12l2 2 4-4" />
  </Icon>
)

export const IconSliders = (p) => (
  <Icon {...p}>
    <path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12" />
    <circle cx="16" cy="6" r="2" />
    <circle cx="10" cy="12" r="2" />
    <circle cx="18" cy="18" r="2" />
  </Icon>
)

export const IconClock = (p) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </Icon>
)

export const IconArrowLeft = (p) => (
  <Icon {...p}>
    <path d="M19 12H5M11 6l-6 6 6 6" />
  </Icon>
)

export const IconChevronRight = (p) => (
  <Icon {...p}>
    <path d="M9 6l6 6-6 6" />
  </Icon>
)

export const IconPlay = (p) => (
  <Icon {...p}>
    <path d="M7 5l12 7-12 7z" />
  </Icon>
)

export const IconStop = (p) => (
  <Icon {...p}>
    <rect x="6" y="6" width="12" height="12" rx="2" />
  </Icon>
)

export const IconRefresh = (p) => (
  <Icon {...p}>
    <path d="M20 11a8 8 0 0 0-14.5-4.5L4 8M4 4v4h4M4 13a8 8 0 0 0 14.5 4.5L20 16M20 20v-4h-4" />
  </Icon>
)

export const IconQr = (p) => (
  <Icon {...p}>
    <rect x="4" y="4" width="6" height="6" rx="1" />
    <rect x="14" y="4" width="6" height="6" rx="1" />
    <rect x="4" y="14" width="6" height="6" rx="1" />
    <path d="M14 14h2v2h-2zM18 18h2v2h-2zM14 18v2M18 14h2" />
  </Icon>
)

export const IconFile = (p) => (
  <Icon {...p}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5M9 13h6M9 17h6" />
  </Icon>
)

export const IconActivity = (p) => (
  <Icon {...p}>
    <path d="M3 12h4l3-8 4 16 3-8h4" />
  </Icon>
)

export const IconScanFace = (p) => (
  <Icon {...p}>
    <path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" />
    <path d="M9 10v.01M15 10v.01M9 15a4 4 0 0 0 6 0" />
  </Icon>
)

export const IconImage = (p) => (
  <Icon {...p}>
    <rect x="3" y="4" width="18" height="16" rx="2" />
    <circle cx="9" cy="10" r="2" />
    <path d="M21 16l-5-5-9 9" />
  </Icon>
)

export const IconMail = (p) => (
  <Icon {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="M3 7l9 6 9-6" />
  </Icon>
)

export const IconLock = (p) => (
  <Icon {...p}>
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </Icon>
)

export const IconMenu = (p) => (
  <Icon {...p}>
    <path d="M4 7h16M4 12h16M4 17h16" />
  </Icon>
)

export const IconHash = (p) => (
  <Icon {...p}>
    <path d="M5 9h14M5 15h14M10 4L8 20M16 4l-2 16" />
  </Icon>
)

export const IconHelp = (p) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.6M12 17v.01" />
  </Icon>
)

export const IconEye = (p) => (
  <Icon {...p}>
    <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
    <circle cx="12" cy="12" r="3" />
  </Icon>
)

export const IconEyeOff = (p) => (
  <Icon {...p}>
    <path d="M10.6 5.6A9.6 9.6 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a16 16 0 0 1-2.6 3.4M6.6 6.6A16 16 0 0 0 2.5 12S6 18.5 12 18.5a9 9 0 0 0 4.9-1.4" />
    <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2M3 3l18 18" />
  </Icon>
)

export const IconTextSize = (p) => (
  <Icon {...p}>
    <path d="M3 19l5-13 5 13M4.8 14.5h6.4M15 19l3-8 3 8M15.9 16.5h4.2" />
  </Icon>
)

export const IconSearch = (p) => (
  <Icon {...p}>
    <circle cx="11" cy="11" r="7" />
    <path d="M20 20l-4-4" />
  </Icon>
)

export const IconBulb = (p) => (
  <Icon {...p}>
    <path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z" />
  </Icon>
)

export const IconSwitchCamera = (p) => (
  <Icon {...p}>
    <path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" />
    <path d="M9 13.5a3 3 0 0 1 5.2-2M15 13.5a3 3 0 0 1-5.2 2M14.5 9.8v1.8h-1.8M9.5 17.2v-1.8h1.8" />
  </Icon>
)

export const IconMinus = (p) => (
  <Icon {...p}>
    <path d="M5 12h14" />
  </Icon>
)

export const IconSun = (p) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </Icon>
)

export const IconEdit = (p) => (
  <Icon {...p}>
    <path d="M4 20h4L19 9l-4-4L4 16z" />
    <path d="M13.5 6.5l4 4" />
  </Icon>
)
