// terminal window (black, white ">_"); the thin outline keeps its edge visible
// on the dark theme
export default function TerminalIcon({ size = 28 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 392 392" aria-hidden="true" style={{ flex: 'none' }}>
      <rect x="4" y="4" width="384" height="384" rx="54" fill="#000" stroke="var(--border)" strokeWidth="8" />
      <rect x="4" y="74" width="384" height="23" fill="#fff" />
      <g fill="none" stroke="#fff" strokeWidth="26" strokeLinecap="round" strokeLinejoin="round">
        <path d="M100 154 L160 220 L100 286" />
        <path d="M182 271 H290" />
      </g>
    </svg>
  )
}
