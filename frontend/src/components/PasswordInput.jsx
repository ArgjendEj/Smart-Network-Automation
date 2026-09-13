import { useState } from 'react'

// password field with a show/hide eye toggle
export default function PasswordInput({ value, onChange, autoFocus, autoComplete, placeholder }) {
  const [show, setShow] = useState(false)
  return (
    <div style={{ position: 'relative', display: 'flex' }}>
      <input
        type={show ? 'text' : 'password'}
        value={value}
        onChange={onChange}
        autoFocus={autoFocus}
        autoComplete={autoComplete}
        placeholder={placeholder}
        style={{ flex: 1, paddingRight: 38, width: '100%' }}
      />
      <button
        type="button"
        onClick={() => setShow((s) => !s)}
        title={show ? 'Hide password' : 'Show password'}
        aria-label={show ? 'Hide password' : 'Show password'}
        style={{
          position: 'absolute', right: 4, top: 4, bottom: 4,
          padding: '0 8px', border: 'none', background: 'transparent',
          fontSize: 15, lineHeight: 1,
        }}
      >
        {show ? '🙈' : '👁️'}
      </button>
    </div>
  )
}
