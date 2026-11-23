import { useState } from 'react'

// dark is the default; the choice is remembered in this browser and applied
// before the first paint by the small script in index.html
export default function ThemeToggle({ style }) {
  const [theme, setTheme] = useState(document.documentElement.dataset.theme || 'dark')
  const next = theme === 'light' ? 'dark' : 'light'
  const toggle = () => {
    document.documentElement.dataset.theme = next
    try { localStorage.setItem('theme', next) } catch { /* storage blocked */ }
    setTheme(next)
  }
  return (
    <button type="button" onClick={toggle} title={`Switch to ${next} mode`} style={style}>
      {next === 'light' ? '☀️ Light' : '🌙 Dark'}
    </button>
  )
}
