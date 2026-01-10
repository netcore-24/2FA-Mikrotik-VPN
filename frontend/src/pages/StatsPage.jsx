import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../services/api'
import {
  StatusPieChart,
  StatusBarChart,
  TimeSeriesLineChart,
  MultiLineChart,
} from '../components/Charts'
import { exportToCSV, exportToExcel } from '../utils/export'
import './StatsPage.css'
import '../components/Charts.css'

const StatsPage = () => {
  const [periodDays, setPeriodDays] = useState(30)

  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ['stats', 'overview'],
    queryFn: async () => {
      const response = await api.get('/stats/overview')
      return response.data
    },
    refetchInterval: 30000,
  })

  const { data: usersStats, isLoading: usersLoading } = useQuery({
    queryKey: ['stats', 'users'],
    queryFn: async () => {
      const response = await api.get('/stats/users')
      return response.data
    },
  })

  const { data: sessionsStats, isLoading: sessionsLoading } = useQuery({
    queryKey: ['stats', 'sessions'],
    queryFn: async () => {
      const response = await api.get('/stats/sessions')
      return response.data
    },
  })

  const { data: requestsStats } = useQuery({
    queryKey: ['stats', 'registration-requests'],
    queryFn: async () => {
      const response = await api.get('/stats/registration-requests')
      return response.data
    },
  })

  const { data: sessionsByPeriod, isLoading: sessionsPeriodLoading } = useQuery({
    queryKey: ['stats', 'sessions-by-period', periodDays],
    queryFn: async () => {
      const response = await api.get('/stats/sessions/by-period', {
        params: { days: periodDays },
      })
      return response.data
    },
  })

  const { data: usersByPeriod, isLoading: usersPeriodLoading } = useQuery({
    queryKey: ['stats', 'users-by-period', periodDays],
    queryFn: async () => {
      const response = await api.get('/stats/users/by-period', {
        params: { days: periodDays },
      })
      return response.data
    },
  })

  const handleExportStats = async (format) => {
    const allStats = {
      overview,
      users: usersStats,
      sessions: sessionsStats,
      requests: requestsStats,
    }

    if (format === 'csv') {
      exportToCSV('stats', allStats)
    } else {
      exportToExcel('stats', allStats)
    }
  }

  if (overviewLoading || usersLoading || sessionsLoading) {
    return <div className="loading">Загрузка статистики...</div>
  }

  // Подготовка данных для графиков
  const usersByStatusData = usersStats?.by_status || {}
  const sessionsByStatusData = sessionsStats?.by_status || {}

  // Форматирование данных временных рядов
  const sessionsTimeSeries =
    sessionsByPeriod?.data?.map((item) => ({
      date: new Date(item.date).toLocaleDateString('ru-RU', {
        month: 'short',
        day: 'numeric',
      }),
      value: item.count,
    })) || []

  const usersTimeSeries =
    usersByPeriod?.data?.map((item) => ({
      date: new Date(item.date).toLocaleDateString('ru-RU', {
        month: 'short',
        day: 'numeric',
      }),
      created: item.created_count || 0,
      approved: item.approved_count || 0,
    })) || []

  return (
    <div className="stats-page">
      <div className="stats-page-header">
        <h2>Статистика системы</h2>
        <div className="export-buttons">
          <button className="action-btn" onClick={() => handleExportStats('csv')}>
            Экспорт CSV
          </button>
          <button className="action-btn" onClick={() => handleExportStats('excel')}>
            Экспорт Excel
          </button>
        </div>
      </div>

      <div className="stats-sections">
        {/* Общая статистика */}
        <section className="stats-section">
          <h3>Общая статистика</h3>
          <div className="stats-grid-small">
            <div className="stat-card-small">
              <div className="stat-label">Всего пользователей</div>
              <div className="stat-value-large">{overview?.total_users || 0}</div>
            </div>
            <div className="stat-card-small">
              <div className="stat-label">Активных пользователей</div>
              <div className="stat-value-large">{overview?.active_users || 0}</div>
            </div>
            <div className="stat-card-small">
              <div className="stat-label">Всего сессий</div>
              <div className="stat-value-large">{overview?.total_sessions || 0}</div>
            </div>
            <div className="stat-card-small">
              <div className="stat-label">Активных сессий</div>
              <div className="stat-value-large">{overview?.active_sessions || 0}</div>
            </div>
            <div className="stat-card-small">
              <div className="stat-label">Заявок на регистрацию</div>
              <div className="stat-value-large">
                {overview?.total_registration_requests || 0}
              </div>
            </div>
            <div className="stat-card-small">
              <div className="stat-label">Ожидающих одобрения</div>
              <div className="stat-value-large">
                {overview?.pending_registration_requests || 0}
              </div>
            </div>
          </div>
        </section>

        {/* Статистика пользователей */}
        <section className="stats-section">
          <h3>Статистика пользователей</h3>
          <div className="stats-table">
            <table>
              <tbody>
                <tr>
                  <td>Всего пользователей</td>
                  <td className="stat-number">{usersStats?.total || 0}</td>
                </tr>
                <tr>
                  <td>Одобренных</td>
                  <td className="stat-number">{usersStats?.approved || 0}</td>
                </tr>
                <tr>
                  <td>Отклоненных</td>
                  <td className="stat-number">{usersStats?.rejected || 0}</td>
                </tr>
                <tr>
                  <td>Ожидающих</td>
                  <td className="stat-number">{usersStats?.pending || 0}</td>
                </tr>
                <tr>
                  <td>Активных</td>
                  <td className="stat-number">{usersStats?.active || 0}</td>
                </tr>
                <tr>
                  <td>Неактивных</td>
                  <td className="stat-number">{usersStats?.inactive || 0}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* Статистика сессий */}
        <section className="stats-section">
          <h3>Статистика VPN сессий</h3>
          <div className="stats-table">
            <table>
              <tbody>
                <tr>
                  <td>Всего сессий</td>
                  <td className="stat-number">{sessionsStats?.total || 0}</td>
                </tr>
                <tr>
                  <td>Активных</td>
                  <td className="stat-number">{sessionsStats?.active || 0}</td>
                </tr>
                <tr>
                  <td>Подключенных</td>
                  <td className="stat-number">{sessionsStats?.connected || 0}</td>
                </tr>
                <tr>
                  <td>Подтвержденных</td>
                  <td className="stat-number">{sessionsStats?.confirmed || 0}</td>
                </tr>
                <tr>
                  <td>Отключенных</td>
                  <td className="stat-number">{sessionsStats?.disconnected || 0}</td>
                </tr>
                <tr>
                  <td>Истекших</td>
                  <td className="stat-number">{sessionsStats?.expired || 0}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* Статистика заявок */}
        <section className="stats-section">
          <h3>Статистика заявок на регистрацию</h3>
          <div className="stats-table">
            <table>
              <tbody>
                <tr>
                  <td>Всего заявок</td>
                  <td className="stat-number">{requestsStats?.total || 0}</td>
                </tr>
                <tr>
                  <td>Ожидающих</td>
                  <td className="stat-number">{requestsStats?.pending || 0}</td>
                </tr>
                <tr>
                  <td>Одобренных</td>
                  <td className="stat-number">{requestsStats?.approved || 0}</td>
                </tr>
                <tr>
                  <td>Отклоненных</td>
                  <td className="stat-number">{requestsStats?.rejected || 0}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {/* Графики */}
      <div className="charts-section">
        <h3>Визуализация данных</h3>

        <div className="charts-controls">
          <label>
            Период для временных графиков:
            <select
              value={periodDays}
              onChange={(e) => setPeriodDays(parseInt(e.target.value))}
              className="period-select"
            >
              <option value="7">7 дней</option>
              <option value="30">30 дней</option>
              <option value="90">90 дней</option>
              <option value="365">1 год</option>
            </select>
          </label>
        </div>

        <div className="charts-grid">
          {/* Распределение пользователей по статусам */}
          <StatusPieChart
            data={usersByStatusData}
            title="Распределение пользователей по статусам"
          />

          {/* Распределение сессий по статусам */}
          <StatusBarChart
            data={sessionsByStatusData}
            title="Распределение VPN сессий по статусам"
          />

          {/* Временной ряд создания сессий */}
          {sessionsPeriodLoading ? (
            <div className="chart-container">
              <div className="loading">Загрузка графика...</div>
            </div>
          ) : (
            <TimeSeriesLineChart
              data={sessionsTimeSeries}
              title={`Создание VPN сессий за последние ${periodDays} дней`}
              dataKey="value"
            />
          )}

          {/* Временной ряд регистрации пользователей */}
          {usersPeriodLoading ? (
            <div className="chart-container">
              <div className="loading">Загрузка графика...</div>
            </div>
          ) : (
            <MultiLineChart
              data={usersTimeSeries}
              title={`Регистрация пользователей за последние ${periodDays} дней`}
              lines={[
                { key: 'created', name: 'Создано' },
                { key: 'approved', name: 'Одобрено' },
              ]}
            />
          )}
        </div>
      </div>
    </div>
  )
}

export default StatsPage
