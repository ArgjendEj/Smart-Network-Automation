import { useState } from 'react'

export default function AutoConfigureButton({ onRun, disabled }) {
  const [busy, setBusy] = useState(false)
  return (
    <button className="primary" disabled={disabled || busy}
      onClick={async () => { setBusy(true); try { await onRun() } finally { setBusy(false) } }}>
      {busy ? 'Configuring…' : '⚙ Auto Configure'}
    </button>
  )
}
