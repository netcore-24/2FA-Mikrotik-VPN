import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../services/api'
import Modal from '../components/Modal'
import { exportTableToCSV, exportTableToExcel } from '../utils/export'
import './TablePage.css'

const UsersPage = () => {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [editingUser, setEditingUser] = useState(null)
  const [editForm, setEditForm] = useState({})
  const limit = 20
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['users', page, statusFilter, searchQuery],
    queryFn: async () => {
      const params = { skip: (page - 1) * limit, limit }
      if (statusFilter) params.status = statusFilter
      if (searchQuery) params.search = searchQuery
      const response = await api.get('/users', { params })
      return response.data
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ userId, userData }) => {
      const response = await api.put(`/users/${userId}`, userData)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['users'])
      setEditingUser(null)
      setEditForm({})
    },
  })

  const changeStatusMutation = useMutation({
    mutationFn: async ({ userId, newStatus }) => {
      // Используем специальный endpoint для изменения статуса
      const response = await api.put(`/users/${userId}/status?new_status=${newStatus}`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['users'])
    },
  })

  const handleEdit = (user) => {
    setEditingUser(user)
    setEditForm({
      full_name: user.full_name || '',
      phone: user.phone || '',
      email: user.email || '',
      status: user.status,
    })
  }

  const handleSave = async () => {
    try {
      await updateMutation.mutateAsync({
        userId: editingUser.id,
        userData: editForm,
      })
      alert('Пользователь обновлен')
    } catch (error) {
      alert(`Ошибка: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleStatusChange = async (userId, newStatus) => {
    if (window.confirm(`Изменить статус пользователя на "${newStatus}"?`)) {
      try {
        await changeStatusMutation.mutateAsync({ userId, newStatus })
      } catch (error) {
        alert(`Ошибка: ${error.response?.data?.detail || error.message}`)
      }
    }
  }

  if (isLoading) {
    return <div className="loading">Загрузка...</div>
  }

  return (
    <div className="table-page">
      <div className="page-header">
        <h2>Пользователи</h2>
        <div className="header-actions">
          <div className="filters">
          <input
            type="text"
            placeholder="Поиск по имени или Telegram ID..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value)
              setPage(1)
            }}
            className="filter-input"
          />
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
            <option value="active">Активные</option>
            <option value="inactive">Неактивные</option>
            <option value="rejected">Отклоненные</option>
          </select>
          </div>
          <div className="export-buttons">
            <button
              className="action-btn"
              onClick={() => {
                const headers = ['ID', 'Telegram ID', 'Имя', 'Телефон', 'Email', 'Статус', 'Создан']
                const rows = (data?.items || []).map((user) => [
                  user.id,
                  user.telegram_id || '',
                  user.full_name || '',
                  user.phone || '',
                  user.email || '',
                  user.status,
                  new Date(user.created_at).toLocaleString('ru-RU'),
                ])
                exportTableToCSV('users', headers, rows)
              }}
            >
              CSV
            </button>
            <button
              className="action-btn"
              onClick={() => {
                const headers = ['ID', 'Telegram ID', 'Имя', 'Телефон', 'Email', 'Статус', 'Создан']
                const rows = (data?.items || []).map((user) => [
                  user.id,
                  user.telegram_id || '',
                  user.full_name || '',
                  user.phone || '',
                  user.email || '',
                  user.status,
                  new Date(user.created_at).toLocaleString('ru-RU'),
                ])
                exportTableToExcel('users', 'Пользователи', headers, rows)
              }}
            >
              Excel
            </button>
          </div>
        </div>
      </div>

      {/* Модальное окно редактирования */}
      <Modal
        isOpen={!!editingUser}
        onClose={() => {
          setEditingUser(null)
          setEditForm({})
        }}
        title="Редактировать пользователя"
      >
        <div className="form-group">
          <label>Имя</label>
          <input
            type="text"
            value={editForm.full_name}
            onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Телефон</label>
          <input
            type="text"
            value={editForm.phone}
            onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Email</label>
          <input
            type="email"
            value={editForm.email}
            onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
          />
        </div>
        <div className="form-group">
          <label>Статус</label>
          <select
            value={editForm.status}
            onChange={(e) => setEditForm({ ...editForm, status: e.target.value })}
          >
            <option value="pending">Ожидает</option>
            <option value="approved">Одобрен</option>
            <option value="active">Активен</option>
            <option value="inactive">Неактивен</option>
            <option value="rejected">Отклонен</option>
          </select>
        </div>
        <div className="modal-actions">
          <button
            className="action-btn action-btn-success"
            onClick={handleSave}
            disabled={updateMutation.isPending}
          >
            {updateMutation.isPending ? 'Сохранение...' : 'Сохранить'}
          </button>
          <button
            className="action-btn"
            onClick={() => {
              setEditingUser(null)
              setEditForm({})
            }}
            disabled={updateMutation.isPending}
          >
            Отмена
          </button>
        </div>
      </Modal>

      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Telegram ID</th>
              <th>Имя</th>
              <th>Статус</th>
              <th>Создан</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {data?.items?.length === 0 ? (
              <tr>
                <td colSpan="6" className="no-data">
                  Нет пользователей
                </td>
              </tr>
            ) : (
              data?.items?.map((user) => (
              <tr key={user.id}>
                <td>{user.id.substring(0, 8)}...</td>
                <td>{user.telegram_id || '-'}</td>
                <td>{user.full_name || '-'}</td>
                <td>
                  <span className={`status-badge status-${user.status}`}>
                    {user.status === 'approved' && 'Одобрен'}
                    {user.status === 'pending' && 'Ожидает'}
                    {user.status === 'active' && 'Активен'}
                    {user.status === 'inactive' && 'Неактивен'}
                    {user.status === 'rejected' && 'Отклонен'}
                    {!['approved', 'pending', 'active', 'inactive', 'rejected'].includes(user.status) && user.status}
                  </span>
                </td>
                <td>{new Date(user.created_at).toLocaleDateString('ru-RU')}</td>
                <td>
                  <button
                    className="action-btn"
                    onClick={() => handleEdit(user)}
                  >
                    Редактировать
                  </button>
                  {user.status !== 'active' && (
                    <button
                      className="action-btn action-btn-success"
                      onClick={() => handleStatusChange(user.id, 'active')}
                      disabled={changeStatusMutation.isPending}
                      style={{ marginLeft: '0.5rem' }}
                    >
                      Активировать
                    </button>
                  )}
                  {user.status === 'active' && (
                    <button
                      className="action-btn action-btn-warning"
                      onClick={() => handleStatusChange(user.id, 'inactive')}
                      disabled={changeStatusMutation.isPending}
                      style={{ marginLeft: '0.5rem' }}
                    >
                      Деактивировать
                    </button>
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
            пользователей)
          </span>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={!data?.items || data.items.length < limit}
          >
            Вперед
          </button>
        </div>
      </div>
    </div>
  )
}

export default UsersPage
