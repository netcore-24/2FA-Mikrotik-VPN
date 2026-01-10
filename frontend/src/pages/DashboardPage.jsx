import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import api from '../services/api'
import './DashboardPage.css'

const DashboardPage = () => {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['stats', 'overview'],
    queryFn: async () => {
      const response = await api.get('/stats/overview')
      return response.data
    },
    refetchInterval: 30000, // Обновлять каждые 30 секунд
  })

  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="loading">Загрузка данных...</div>
      </div>
    )
  }

  // Всегда показываем карточки статистики, даже если данных нет
  const cards = [
    {
      title: 'Всего пользователей',
      value: stats?.total_users || 0,
      icon: '👥',
      color: 'blue',
      link: '/users',
    },
    {
      title: 'Активных пользователей',
      value: stats?.active_users || 0,
      icon: '✅',
      color: 'green',
      link: '/users',
    },
    {
      title: 'Активных сессий',
      value: stats?.active_sessions || 0,
      icon: '🔒',
      color: 'purple',
      link: '/vpn-sessions',
    },
    {
      title: 'Активные сессии MikroTik',
      value: stats?.mikrotik_active_sessions ?? '—',
      icon: '🛡️',
      color: 'orange',
      link: '/vpn-sessions',
    },
  ]

  return (
    <div className="dashboard">
      <div className="stats-grid">
        {cards.map((card, index) => (
          <Link 
            key={index} 
            to={card.link}
            className={`stat-card stat-card-${card.color}`}
            style={{ textDecoration: 'none', color: 'inherit' }}
          >
            <div className="stat-icon">{card.icon}</div>
            <div className="stat-content">
              <div className="stat-value">{card.value}</div>
              <div className="stat-title">{card.title}</div>
            </div>
          </Link>
        ))}
      </div>

      <div className="dashboard-content">
        <div className="dashboard-section">
          <h3>🧭 Как работает система (простыми словами)</h3>
          <div className="info-content">
            <p>
              Это связка <strong>Telegram-бота</strong>, <strong>backend</strong> и <strong>MikroTik</strong>, которая
              помогает выдавать доступ в VPN и контролировать активные подключения.
            </p>
            <ol style={{ marginLeft: '1.5rem', marginTop: '0.5rem', lineHeight: 1.8 }}>
              <li>
                <strong>Админ настраивает MikroTik</strong> (раздел <Link to="/mikrotik">MikroTik</Link> или мастер
                настройки).
              </li>
              <li>
                <strong>Пользователь пишет боту</strong> и отправляет заявку на регистрацию.
              </li>
              <li>
                <strong>Админ одобряет/отклоняет заявку</strong> (раздел <Link to="/users">Пользователи</Link>).
              </li>
              <li>
                При одобрении система <strong>создаёт/обновляет учётку на MikroTik</strong> и сохраняет настройки доступа
                (в т.ч. доп. защиту/привязки правил, если включены).
              </li>
              <li>
                Когда пользователь подключается к VPN, система <strong>видит активную сессию на MikroTik</strong> и
                отображает её в <Link to="/vpn-sessions">VPN сессиях</Link>.
              </li>
              <li>
                По тайм-ауту/по команде админа сессии <strong>завершаются</strong>, а пользователь может быть
                <strong>деактивирован</strong>.
              </li>
            </ol>
            <p style={{ marginTop: '0.75rem', color: 'var(--text-secondary)' }}>
              Для диагностики и отчётов используйте <Link to="/stats">Статистику</Link> и <Link to="/audit-logs">Аудит</Link>.
            </p>
          </div>
        </div>

        <div className="dashboard-section">
          <h3>ℹ️ Информация о системе</h3>
          <div className="info-content">
            <p>Система MikroTik 2FA VPN успешно настроена и готова к работе.</p>
            <p>Вы можете:</p>
            <ul style={{ marginLeft: '1.5rem', marginTop: '0.5rem' }}>
              <li>Управлять пользователями через раздел "Пользователи"</li>
              <li>Принимать/отклонять заявки, пришедшие из Telegram бота</li>
              <li>Мониторить активные VPN сессии</li>
              <li>Настраивать MikroTik роутер через раздел "MikroTik"</li>
              <li>Просматривать подробную статистику и графики</li>
            </ul>
            {(!stats || (stats.total_users === 0 && stats.active_sessions === 0)) && (
              <div style={{ marginTop: '1.5rem', padding: '1rem', background: 'var(--info-light)', borderRadius: 'var(--radius-md)', border: '1px solid var(--info-color)' }}>
                <strong>💡 Совет:</strong> Для начала работы создайте пользователей через Telegram бота или начните принимать заявки на регистрацию.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default DashboardPage
