import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../services/api'
import Modal from '../components/Modal'
import './TablePage.css'

const RegistrationRequestsPage = () => {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [rejectingRequest, setRejectingRequest] = useState(null)
  const [rejectReason, setRejectReason] = useState('')
  const limit = 20
  const queryClient = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['registration-requests', page, statusFilter],
    queryFn: async () => {
      const params = { skip: (page - 1) * limit, limit }
      if (statusFilter) params.status = statusFilter
      const response = await api.get('/registration-requests', { params })
      return response.data
    },
  })

  const approveMutation = useMutation({
    mutationFn: async (requestId) => {
      // backend принимает approve без body
      const response = await api.post(`/registration-requests/${requestId}/approve`, {})
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['registration-requests'])
    },
    onError: (error) => {
      alert(`Ошибка: ${error.response?.data?.detail || error.message}`)
    },
  })

  const rejectMutation = useMutation({
    mutationFn: async ({ requestId, reason }) => {
      const response = await api.post(`/registration-requests/${requestId}/reject`, {
        rejection_reason: reason,
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['registration-requests'])
    },
  })

  const handleApprove = async (requestId) => {
    if (window.confirm('Одобрить заявку на регистрацию?')) {
      try {
        await approveMutation.mutateAsync(requestId)
      } catch (error) {
        // onError уже покажет alert, но оставим на случай других обработчиков
      }
    }
  }

  const handleRejectClick = (requestId) => {
    setRejectingRequest(requestId)
    setRejectReason('')
  }

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      alert('Укажите причину отклонения')
      return
    }
    try {
      await rejectMutation.mutateAsync({ requestId: rejectingRequest, reason: rejectReason.trim() })
      setRejectingRequest(null)
      setRejectReason('')
    } catch (error) {
      alert(`Ошибка: ${error.response?.data?.detail || error.message}`)
    }
  }

  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="loading">Загрузка заявок...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="table-page">
        <div className="page-header">
          <h2>Заявки на регистрацию</h2>
        </div>
        <div className="error-message">
          ❌ Ошибка загрузки данных: {error.message || 'Неизвестная ошибка'}
        </div>
      </div>
    )
  }

  if (!data?.items || data.items.length === 0) {
    return (
      <div className="table-page">
        <div className="page-header">
          <h2>Заявки на регистрацию</h2>
        </div>
        <div className="empty-state">
          <div className="empty-state-icon">📝</div>
          <h3 className="empty-state-title">Нет заявок на регистрацию</h3>
          <p className="empty-state-description">Заявки будут отображаться здесь после того, как пользователи зарегистрируются через Telegram бота</p>
        </div>
      </div>
    )
  }

  return (
    <div className="table-page">
      <div className="page-header">
        <h2>Заявки на регистрацию</h2>
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
            <option value="pending">Ожидающие</option>
            <option value="approved">Одобренные</option>
            <option value="rejected">Отклоненные</option>
          </select>
          </div>
          <div className="export-buttons">
            <button
              className="action-btn"
              onClick={() => {
                const headers = ['ID', 'User ID', 'Пользователь', 'Telegram ID', 'Статус', 'Дата запроса', 'Дата рассмотрения']
                const rows = (data?.items || []).map((request) => [
                  request.id,
                  request.user_id,
                  request.user?.full_name || '-',
                  request.user?.telegram_id || '-',
                  request.status,
                  new Date(request.requested_at).toLocaleString('ru-RU'),
                  request.reviewed_at ? new Date(request.reviewed_at).toLocaleString('ru-RU') : '-',
                ])
                exportTableToCSV('registration-requests', headers, rows)
              }}
            >
              CSV
            </button>
            <button
              className="action-btn"
              onClick={() => {
                const headers = ['ID', 'User ID', 'Пользователь', 'Telegram ID', 'Статус', 'Дата запроса', 'Дата рассмотрения']
                const rows = (data?.items || []).map((request) => [
                  request.id,
                  request.user_id,
                  request.user?.full_name || '-',
                  request.user?.telegram_id || '-',
                  request.status,
                  new Date(request.requested_at).toLocaleString('ru-RU'),
                  request.reviewed_at ? new Date(request.reviewed_at).toLocaleString('ru-RU') : '-',
                ])
                exportTableToExcel('registration-requests', 'Заявки', headers, rows)
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
              <th>Telegram ID</th>
              <th>Статус</th>
              <th>Дата запроса</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {data?.items?.length === 0 ? (
              <tr>
                <td colSpan="6" className="no-data">
                  Нет заявок на регистрацию
                </td>
              </tr>
            ) : (
              data?.items?.map((request) => (
                <tr key={request.id}>
                  <td>{request.id.substring(0, 8)}...</td>
                  <td>{request.user?.full_name || '-'}</td>
                  <td>{request.user?.telegram_id || '-'}</td>
                  <td>
                    <span className={`status-badge status-${request.status}`}>
                      {request.status === 'pending' && 'Ожидает'}
                      {request.status === 'approved' && 'Одобрено'}
                      {request.status === 'rejected' && 'Отклонено'}
                    </span>
                  </td>
                  <td>
                    {new Date(request.requested_at).toLocaleString('ru-RU')}
                  </td>
                  <td>
                    {request.status === 'pending' && (
                      <>
                        <button
                          className="action-btn action-btn-success"
                          onClick={() => handleApprove(request.id)}
                          disabled={approveMutation.isPending}
                        >
                          {approveMutation.isPending ? 'Обработка...' : 'Одобрить'}
                        </button>
                        <button
                          className="action-btn action-btn-danger"
                          onClick={() => handleRejectClick(request.id)}
                          disabled={rejectMutation.isPending}
                        >
                          Отклонить
                        </button>
                      </>
                    )}
                    {request.status === 'rejected' && request.rejection_reason && (
                      <div className="rejection-reason">
                        Причина: {request.rejection_reason}
                      </div>
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
            Страница {page} из {Math.ceil((data?.total || 0) / limit)}
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={!data?.items || data.items.length < limit}
          >
            Вперед
          </button>
        </div>
      </div>

      {/* Модальное окно отклонения заявки */}
      <Modal
        isOpen={!!rejectingRequest}
        onClose={() => {
          setRejectingRequest(null)
          setRejectReason('')
        }}
        title="Отклонить заявку на регистрацию"
      >
        <div className="form-group">
          <label>Причина отклонения *</label>
          <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            rows={4}
            placeholder="Укажите причину отклонения заявки..."
          />
        </div>
        <div className="modal-actions">
          <button
            className="action-btn action-btn-danger"
            onClick={handleReject}
            disabled={rejectMutation.isPending || !rejectReason.trim()}
          >
            {rejectMutation.isPending ? 'Обработка...' : 'Отклонить'}
          </button>
          <button
            className="action-btn"
            onClick={() => {
              setRejectingRequest(null)
              setRejectReason('')
            }}
            disabled={rejectMutation.isPending}
          >
            Отмена
          </button>
        </div>
      </Modal>
    </div>
  )
}

export default RegistrationRequestsPage
