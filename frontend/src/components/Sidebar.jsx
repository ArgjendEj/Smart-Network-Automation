import { NavLink } from 'react-router-dom'

const links = [
  ['/', 'Dashboard'],
  ['/topology', 'Network Topology'],
  ['/devices', 'Devices'],
  ['/smart-config', 'Smart Auto Config'],
  ['/manual-config', 'Manual Config'],
  ['/logs', 'Logs'],
]

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <h1>⚡ Network Automation</h1>
      <nav>
        {links.map(([to, label]) => (
          <NavLink key={to} to={to} end={to === '/'}
            className={({ isActive }) => (isActive ? 'active' : '')}>
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
