import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../services/api'
import Modal from '../components/Modal'
import { exportTableToCSV, exportTableToExcel } from '../utils/export'
import './TablePage.css'

const VPNSessionsPage = () => {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [extendingSession, setExtendingSession] = useState(null)
  const [extendHours, setExtendHours] = useState('24')
  const limit = 20
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['vpn-sessions', page, statusFilter],
    queryFn: async () => {
      const params = { skip: (page - 1) * limit, limit }
      if (statusFilter) params.status = statusFilter
      const response = await api.get('/vpn-sessions', { params })
      return response.data
    },
  })

  const disconnectMutation = useMutation({
    mutationFn: async (sessionId) => {
      const response = await api.post(`/vpn-sessions/${sessionId}/disconnect`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['vpn-sessions'])
    },
  })

  const extendMutation = useMutation({
    mutationFn: async ({ sessionId, hours }) => {
      const response = await api.post(`/vpn-sessions/${sessionId}/extend`, { hours })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['vpn-sessions'])
    },
  })

  const handleDisconnect = async (sessionId) => {
    if (window.confirm('Отключить VPN сессию?')) {
      await disconnectMutation.mutateAsync(sessionId)
    }
  }

  const handleExtendClick = (sessionId) => {
    setExtendingSession(sessionId)
    setExtendHours('24')
  }

  const handleExtend = async () => {
    const hours = parseInt(extendHours)
    if (isNaN(hours) || hours <= 0) {
      alert('Укажите корректное количество часов')
      return
    }
    try {
      await extendMutation.mutateAsync({ sessionId: extendingSession, hours })
      setExtendingSession(null)
      setExtendHours('24')
    } catch (error) {
      alert(`Ошибка: ${error.response?.data?.detail || error.message}`)
    }
  }

  const getStatusLabel = (status) => {
    const labels = {
      requested: 'Запрошено',
      connected: 'Подключено',
      confirmed: 'Подтверждено',
      active: 'Активно',
      reminder_sent: 'Напоминание отправлено',
      expired: 'Истекла',
      disconnected: 'Отключено',
    }
    return labels[status] || status
  }

  if (isLoading) {
    return <div className="loading">Загрузка...</div>
  }

  return (
    <div className="table-page">
      <div className="page-header">
        <h2>VPN Сессии</h2>
        <div className="header-actions">
          <div className="filters">
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value)
              setPage(1)
            }}
            className="filter-select"
          >
            <option value="">Все статусы</option>
            <option value="active">Активные</option>
            <option value="connected">Подключенные</option>
            <option value="confirmed">Подтвержденные</option>
            <option value="disconnected">Отключенные</option>
            <option value="expired">Истекшие</option>
          </select>
          <button
            className="action-btn"
            onClick={() => queryClient.invalidateQueries(['vpn-sessions'])}
          >
            Обновить
          </button>
          </div>
          <div className="export-buttons">
            <button
              className="action-btn"
              onClick={() => {
                const headers = ['ID', 'User ID', 'Пользователь', 'MikroTik Username', 'Статус', 'Создана', 'Истекает']
                const rows = (data?.items || []).map((session) => [
                  session.id,
                  session.user_id,
                  session.user?.full_name || session.user?.telegram_id || '-',
                  session.mikrotik_username || '-',
                  session.status,
                  new Date(session.created_at).toLocaleString('ru-RU'),
                  session.expires_at ? new Date(session.expires_at).toLocaleString('ru-RU') : '-',
                ])
                exportTableToCSV('vpn-sessions', headers, rows)
              }}
            >
              CSV
            </button>
            <button
              className="action-btn"
              onClick={() => {
                const headers = ['ID', 'User ID', 'Пользователь', 'MikroTik Username', 'Статус', 'Создана', 'Истекает']
                const rows = (data?.items || []).map((session) => [
                  session.id,
                  session.user_id,
                  session.user?.full_name || session.user?.telegram_id || '-',
                  session.mikrotik_username || '-',
                  session.status,
                  new Date(session.created_at).toLocaleString('ru-RU'),
                  session.expires_at ? new Date(session.expires_at).toLocaleString('ru-RU') : '-',
                ])
                exportTableToExcel('vpn-sessions', 'VPN Сессии', headers, rows)
              }}
            >
              Excel
            </button>
          </div>
        </div>
      </div>

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Пользователь</th>
              <th>MikroTik Username</th>
              <th>Статус</th>
              <th>Создана</th>
              <th>Истекает</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {data?.items?.length === 0 ? (
              <tr>
                <td colSpan="7" className="no-data">
                  Нет VPN сессий
                </td>
              </tr>
            ) : (
              data?.items?.map((session) => (
                <tr key={session.id}>
                  <td>{session.id.substring(0, 8)}...</td>
                  <td>
                    {session.user?.full_name || session.user?.telegram_id || '-'}
                  </td>
                  <td>{session.mikrotik_username || '-'}</td>
                  <td>
                    <span className={`status-badge status-${session.status}`}>
                      {getStatusLabel(session.status)}
                    </span>
                  </td>
                  <td>
                    {new Date(session.created_at).toLocaleString('ru-RU')}
                  </td>
                  <td>
                    {session.expires_at
                      ? new Date(session.expires_at).toLocaleString('ru-RU')
                      : '-'}
                  </td>
                  <td>
                    {['active', 'connected', 'confirmed'].includes(session.status) && (
                      <>
                        <button
                          className="action-btn action-btn-warning"
                          onClick={() => handleExtendClick(session.id)}
                          disabled={extendMutation.isPending}
                        >
                          Продлить
                        </button>
                        <button
                          className="action-btn action-btn-danger"
                          onClick={() => handleDisconnect(session.id)}
                          disabled={disconnectMutation.isPending}
                        >
                          {disconnectMutation.isPending ? 'Отключение...' : 'Отключить'}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        <div className="pagination">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Назад
          </button>
          <span>
            Страница {page} из {Math.ceil((data?.total || 0) / limit)} ({data?.total || 0}{' '}
            сессий)
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={!data?.items || data.items.length < limit}
          >
            Вперед
          </button>
        </div>
      </div>

      {/* Модальное окно продления сессии */}
      <Modal
        isOpen={!!extendingSession}
        onClose={() => {
          setExtendingSession(null)
          setExtendHours('24')
        }}
        title="Продлить VPN сессию"
      >
        <div className="form-group">
          <label>Количество часов</label>
          <input
            type="number"
            min="1"
            value={extendHours}
            onChange={(e) => setExtendHours(e.target.value)}
            placeholder="24"
          />
        </div>
        <div className="modal-actions">
          <button
            className="action-btn action-btn-warning"
            onClick={handleExtend}
            disabled={extendMutation.isPending || !extendHours || parseInt(extendHours) <= 0}
          >
            {extendMutation.isPending ? 'Продление...' : 'Продлить'}
          </button>
          <button
            className="action-btn"
            onClick={() => {
              setExtendingSession(null)
              setExtendHours('24')
            }}
            disabled={extendMutation.isPending}
          >
            Отмена
          </button>
        </div>
      </Modal>
    </div>
  )
}

export default VPNSessionsPage
