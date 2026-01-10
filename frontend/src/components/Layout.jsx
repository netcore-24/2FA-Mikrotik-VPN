import { Link, useLocation, Outlet } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import './Layout.css'

const Layout = () => {
  const location = useLocation()
  const { admin, logout } = useAuthStore()

  const menuItems = [
    { path: '/', label: 'Дашборд', icon: '📊' },
    { path: '/users', label: 'Пользователи', icon: '👥' },
    { path: '/vpn-sessions', label: 'VPN Сессии', icon: '🔒' },
    { path: '/mikrotik', label: 'MikroTik', icon: '🛡️' },
    { path: '/stats', label: 'Статистика', icon: '📈' },
    { path: '/audit-logs', label: 'Аудит', icon: '📋' },
    { path: '/settings', label: 'Настройки', icon: '⚙️' },
    { path: '/setup-wizard', label: 'Мастер настройки', icon: '🎯', showBadge: true },
  ]

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>MikroTik 2FA VPN</h1>
        </div>
        
        <nav className="sidebar-nav">
          {menuItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`nav-item ${location.pathname === item.path ? 'active' : ''}`}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
              {item.showBadge && <span className="nav-badge">NEW</span>}
            </Link>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-info">
            <div className="user-name">{admin?.username || 'Admin'}</div>
            <div className="user-role">{admin?.is_super_admin ? 'Супер-админ' : 'Админ'}</div>
          </div>
          <button className="logout-btn" onClick={logout}>
            Выйти
          </button>
        </div>
      </aside>

      <main className="main-content">
        <header className="main-header">
          <h2>{menuItems.find(item => item.path === location.pathname)?.label || 'Дашборд'}</h2>
        </header>
        <div className="content-wrapper">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

export default Layout
