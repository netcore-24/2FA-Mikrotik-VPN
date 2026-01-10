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
    return <div className="loading">Загрузка...</div>
  }

  const cards = [
    {
      title: 'Всего пользователей',
      value: stats?.total_users || 0,
      icon: '👥',
      color: 'blue',
    },
    {
      title: 'Активных пользователей',
      value: stats?.active_users || 0,
      icon: '✅',
      color: 'green',
    },
    {
      title: 'Активных сессий',
      value: stats?.active_sessions || 0,
      icon: '🔒',
      color: 'purple',
    },
    {
      title: 'Ожидающих одобрения',
      value: stats?.pending_registration_requests || 0,
      icon: '⏳',
      color: 'orange',
    },
  ]

  return (
    <div className="dashboard">
      <div className="stats-grid">
        {cards.map((card, index) => (
          <div key={index} className={`stat-card stat-card-${card.color}`}>
            <div className="stat-icon">{card.icon}</div>
            <div className="stat-content">
              <div className="stat-value">{card.value}</div>
              <div className="stat-title">{card.title}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="dashboard-content">
        <div className="dashboard-section">
          <h3>Быстрые действия</h3>
          <div className="quick-actions">
            <Link to="/registration-requests" className="quick-action-btn">
              Просмотреть заявки на регистрацию
            </Link>
            <Link to="/vpn-sessions" className="quick-action-btn">
              Управление VPN сессиями
            </Link>
            <Link to="/users" className="quick-action-btn">
              Управление пользователями
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

export default DashboardPage
