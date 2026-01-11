import { useEffect, useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../services/api'
import Modal from '../components/Modal'
import { exportTableToCSV, exportTableToExcel } from '../utils/export'
import './TablePage.css'

const getErrorMessage = (error) => {
  const data = error?.response?.data
  const detail = data?.detail

  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    // FastAPI validation error format
    return detail
      .map((d) => (typeof d?.msg === 'string' ? d.msg : JSON.stringify(d)))
      .filter(Boolean)
      .join('\n')
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail)

  if (typeof data === 'string') return data
  if (data && typeof data === 'object') return JSON.stringify(data)

  if (typeof error?.message === 'string') return error.message
  return String(error)
}

const UsersPage = () => {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [editingUser, setEditingUser] = useState(null)
  const [editForm, setEditForm] = useState({})
  const [rejectingRequest, setRejectingRequest] = useState(null)
  const [rejectReason, setRejectReason] = useState('')
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

  // Встроенные "заявки на регистрацию" (ожидающие)
  const { data: pendingRequests, isLoading: pendingRequestsLoading } = useQuery({
    queryKey: ['registration-requests', 'pending', 'embedded'],
    queryFn: async () => {
      const response = await api.get('/registration-requests', { params: { status: 'pending', skip: 0, limit: 50 } })
      return response.data
    },
  })

  const approveRequestMutation = useMutation({
    mutationFn: async (requestId) => {
      const response = await api.post(`/registration-requests/${requestId}/approve`, {})
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['registration-requests'])
      queryClient.invalidateQueries(['users'])
    },
  })

  const rejectRequestMutation = useMutation({
    mutationFn: async ({ requestId, reason }) => {
      const response = await api.post(`/registration-requests/${requestId}/reject`, {
        rejection_reason: reason,
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['registration-requests'])
      queryClient.invalidateQueries(['users'])
    },
  })

  const handleApproveRequest = async (requestId) => {
    if (window.confirm('Одобрить заявку на регистрацию?')) {
      try {
        await approveRequestMutation.mutateAsync(requestId)
      } catch (error) {
        alert(`Ошибка: ${getErrorMessage(error)}`)
      }
    }
  }

  const handleRejectRequestClick = (requestId) => {
    setRejectingRequest(requestId)
    setRejectReason('')
  }

  const handleRejectRequest = async () => {
    if (!rejectReason.trim()) {
      alert('Укажите причину отклонения')
      return
    }
    try {
      await rejectRequestMutation.mutateAsync({ requestId: rejectingRequest, reason: rejectReason.trim() })
      setRejectingRequest(null)
      setRejectReason('')
    } catch (error) {
      alert(`Ошибка: ${getErrorMessage(error)}`)
    }
  }

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

  const { data: mikrotikUsers } = useQuery({
    queryKey: ['mikrotik', 'users', 'for-user-linking'],
    queryFn: async () => {
      const response = await api.get('/mikrotik/users')
      return response.data
    },
    enabled: !!editingUser, // грузим список только когда открыт модал
  })

  const { data: mikrotik2faFirewallRules } = useQuery({
    queryKey: ['mikrotik', 'firewall-rules', '2fa', 'for-user-settings', editingUser?.id],
    queryFn: async () => {
      const response = await api.get('/mikrotik/firewall-rules', { params: { comment: '2FA' } })
      return response.data
    },
    enabled: !!editingUser,
  })

  const { data: userSettings } = useQuery({
    queryKey: ['users', editingUser?.id, 'settings'],
    queryFn: async () => {
      const response = await api.get(`/users/${editingUser.id}/settings`)
      return response.data
    },
    enabled: !!editingUser,
  })

  // синхронизируем полученные настройки в форму при открытии модалки
  useEffect(() => {
    if (!editingUser) return
    if (!userSettings) return
    setEditForm((prev) => ({
      ...prev,
      require_confirmation:
        typeof userSettings.require_confirmation === 'boolean'
          ? userSettings.require_confirmation
          : !!prev.require_confirmation,
      firewall_rule_comment: userSettings.firewall_rule_comment || prev.firewall_rule_comment || '',
      session_duration_hours:
        typeof userSettings.session_duration_hours === 'number'
          ? userSettings.session_duration_hours
          : prev.session_duration_hours ?? 24,
    }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    editingUser?.id,
    userSettings?.require_confirmation,
    userSettings?.firewall_rule_comment,
    userSettings?.session_duration_hours,
  ])

  const available2faComments = useMemo(() => {
    const rules = mikrotik2faFirewallRules?.rules || []
    const uniq = new Set()
    for (const r of rules) {
      const c = (r?.comment || '').toString().trim()
      if (c) uniq.add(c)
    }
    return Array.from(uniq).sort((a, b) => a.localeCompare(b, 'ru'))
  }, [mikrotik2faFirewallRules])

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
    const existingUsernames = (user.mikrotik_usernames || []).map((v) => (v || '').toString())
    setEditForm({
      full_name: user.full_name || '',
      phone: user.phone || '',
      email: user.email || '',
      status: user.status,
      mikrotik_usernames: existingUsernames.length > 0 ? existingUsernames : [''],
      require_confirmation: false,
      firewall_rule_comment: '',
      session_duration_hours: 24,
    })
  }

  const handleSave = async () => {
    try {
      if (editForm.require_confirmation && !(editForm.firewall_rule_comment || '').trim()) {
        alert('Для доп. защиты нужно выбрать firewall-правило (comment с "2FA")')
        return
      }

      const mikrotik_usernames = (editForm.mikrotik_usernames || [])
        .map((v) => (v || '').toString().trim())
        .filter(Boolean)
      const email = (editForm.email || '').trim()
      await updateMutation.mutateAsync({
        userId: editingUser.id,
        userData: {
          full_name: editForm.full_name,
          phone: editForm.phone,
          // Email необязателен: пустую строку превращаем в null, иначе EmailStr на backend не пройдет валидацию
          email: email ? email : null,
          status: editForm.status,
          mikrotik_usernames,
        },
      })

      // обновляем user settings (доп. защита)
      await api.put(`/users/${editingUser.id}/settings`, null, {
        params: {
          require_confirmation: !!editForm.require_confirmation,
          firewall_rule_comment: (editForm.firewall_rule_comment || '').trim() || null,
          session_duration_hours:
            editForm.session_duration_hours !== undefined && editForm.session_duration_hours !== null
              ? Number(editForm.session_duration_hours)
              : null,
        },
      })

      alert('Пользователь обновлен')
    } catch (error) {
      alert(`Ошибка: ${getErrorMessage(error)}`)
    }
  }

  const handleStatusChange = async (userId, newStatus) => {
    if (window.confirm(`Изменить статус пользователя на "${newStatus}"?`)) {
      try {
        await changeStatusMutation.mutateAsync({ userId, newStatus })
      } catch (error) {
        alert(`Ошибка: ${getErrorMessage(error)}`)
      }
    }
  }

  if (isLoading) {
    return (
      <div className="loading-container">
        <div className="loading">Загрузка пользователей...</div>
      </div>
    )
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

      {/* Заявки на регистрацию (встроено в Пользователи) */}
      <div className="table-container" style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.75rem 0.25rem' }}>
          <h3 style={{ margin: 0 }}>Заявки на регистрацию</h3>
          <button className="action-btn" onClick={() => queryClient.invalidateQueries(['registration-requests'])}>
            Обновить
          </button>
        </div>
        {pendingRequestsLoading ? (
          <div className="loading-container">
            <div className="loading">Загрузка заявок...</div>
          </div>
        ) : !pendingRequests?.items || pendingRequests.items.length === 0 ? (
          <div className="no-data" style={{ padding: '0.75rem', opacity: 0.85 }}>
            Нет ожидающих заявок
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Пользователь</th>
                <th>Telegram ID</th>
                <th>Дата</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {pendingRequests.items.map((r) => (
                <tr key={r.id}>
                  <td>{r.id.slice(0, 8)}...</td>
                  <td>{r.user?.full_name || '-'}</td>
                  <td>{r.user?.telegram_id || '-'}</td>
                  <td>{r.requested_at ? new Date(r.requested_at).toLocaleString('ru-RU') : '-'}</td>
                  <td>
                    <div className="row-actions">
                      <button
                        className="action-btn action-btn-success"
                        onClick={() => handleApproveRequest(r.id)}
                        disabled={approveRequestMutation.isPending}
                      >
                        Одобрить
                      </button>
                      <button
                        className="action-btn action-btn-danger"
                        onClick={() => handleRejectRequestClick(r.id)}
                        disabled={rejectRequestMutation.isPending}
                      >
                        Отклонить
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
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
        <div className="form-group checkbox-group">
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={!!editForm.require_confirmation}
              onChange={(e) => setEditForm({ ...editForm, require_confirmation: e.target.checked })}
            />
            Использовать доп. защиту (спрашивать «Это вы подключились?»)
          </label>
          <div className="field-hint">
            Если включено — доступ откроется (firewall) только после подтверждения в Telegram.
          </div>
        </div>
        <div className="form-group">
          <label>Firewall правило (comment с “2FA”)</label>
          <select
            value={editForm.firewall_rule_comment || ''}
            onChange={(e) => setEditForm({ ...editForm, firewall_rule_comment: e.target.value })}
            disabled={!editForm.require_confirmation}
          >
            <option value="">
              {editForm.require_confirmation ? 'Выберите правило…' : 'Включите доп. защиту, чтобы выбрать правило'}
            </option>
            {available2faComments.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          {editForm.require_confirmation && available2faComments.length === 0 && (
            <div style={{ fontSize: '0.9rem', opacity: 0.85, marginTop: '0.25rem' }}>
              На MikroTik не найдено правил firewall с comment содержащим “2FA”.
            </div>
          )}
        </div>
        <div className="form-group">
          <label>Время жизни VPN-сессии (часов)</label>
          <input
            type="number"
            min="1"
            max="168"
            value={editForm.session_duration_hours ?? 24}
            onChange={(e) =>
              setEditForm({
                ...editForm,
                session_duration_hours: e.target.value === '' ? '' : Number(e.target.value),
              })
            }
          />
          <div className="field-hint">
            Сколько времени сессия будет считаться активной до авто-истечения.
          </div>
        </div>
        <div className="form-group">
          <label>MikroTik аккаунты (usernames)</label>
          <div className="field-hint">
            Можно привязать несколько MikroTik usernames к одному пользователю Telegram. Пустые значения будут проигнорированы.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.5rem' }}>
            {(editForm.mikrotik_usernames || ['']).map((val, idx) => (
              <div key={idx} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <input
                  type="text"
                  list="mikrotik-usernames"
                  value={val || ''}
                  onChange={(e) => {
                    const next = [...(editForm.mikrotik_usernames || [])]
                    next[idx] = e.target.value
                    setEditForm({ ...editForm, mikrotik_usernames: next })
                  }}
                  placeholder={idx === 0 ? 'например: user_123456' : 'опционально'}
                  style={{ flex: 1 }}
                />
                <button
                  type="button"
                  className="action-btn action-btn-danger"
                  onClick={() => {
                    const next = [...(editForm.mikrotik_usernames || [])]
                    next.splice(idx, 1)
                    setEditForm({ ...editForm, mikrotik_usernames: next.length > 0 ? next : [''] })
                  }}
                  disabled={(editForm.mikrotik_usernames || []).length <= 1}
                  title="Удалить"
                >
                  ✕
                </button>
              </div>
            ))}
            <div>
              <button
                type="button"
                className="action-btn"
                onClick={() => {
                  const next = [...(editForm.mikrotik_usernames || [])]
                  next.push('')
                  setEditForm({ ...editForm, mikrotik_usernames: next })
                }}
              >
                + Добавить аккаунт
              </button>
            </div>
          </div>
        </div>
        <datalist id="mikrotik-usernames">
          {(mikrotikUsers?.users || []).map((u, idx) => (
            <option key={`${u.name || 'u'}-${idx}`} value={u.name} />
          ))}
        </datalist>
        {mikrotikUsers?.source && (
          <div className="field-hint" style={{ marginTop: '0.5rem' }}>
            Источник на роутере: <b>{mikrotikUsers.source}</b>
            {mikrotikUsers.warning ? ` — ${mikrotikUsers.warning}` : ''}
          </div>
        )}
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

      {/* Модальное окно отклонения заявки */}
      <Modal
        isOpen={!!rejectingRequest}
        onClose={() => {
          setRejectingRequest(null)
          setRejectReason('')
        }}
        title="Отклонить заявку"
      >
        <div className="form-group">
          <label>Причина</label>
          <textarea
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            rows={3}
            className="edit-textarea"
            placeholder="Например: нет доступа / некорректные данные…"
          />
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="action-btn action-btn-danger" onClick={handleRejectRequest} disabled={rejectRequestMutation.isPending}>
            {rejectRequestMutation.isPending ? 'Обработка…' : 'Отклонить'}
          </button>
          <button className="action-btn" onClick={() => { setRejectingRequest(null); setRejectReason('') }} disabled={rejectRequestMutation.isPending}>
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
              <th>MikroTik аккаунты</th>
              <th>Доп. защита</th>
              <th>Firewall (2FA)</th>
              <th>Статус</th>
              <th>Создан</th>
              <th>Действия</th>
            </tr>
          </thead>
          <tbody>
            {data?.items?.length === 0 ? (
              <tr>
                <td colSpan="7" className="no-data">
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
                  {user.mikrotik_usernames && user.mikrotik_usernames.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                      {user.mikrotik_usernames.map((username, idx) => (
                        <span
                          key={idx}
                          style={{
                            fontSize: '0.85rem',
                            padding: '0.15rem 0.4rem',
                            background: '#e3f2fd',
                            border: '1px solid #2196f3',
                            borderRadius: '3px',
                            display: 'inline-block',
                            fontFamily: 'monospace',
                          }}
                        >
                          {username}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span style={{ color: '#999', fontSize: '0.9rem' }}>
                      Не привязаны
                    </span>
                  )}
                </td>
                <td>
                  {user.require_confirmation ? (
                    <span className="status-badge status-active">Вкл</span>
                  ) : (
                    <span className="status-badge status-rejected">Выкл</span>
                  )}
                </td>
                <td style={{ fontFamily: 'monospace', fontSize: '0.9rem' }}>
                  {user.firewall_rule_comment ? user.firewall_rule_comment : '-'}
                </td>
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
                  <div className="row-actions">
                    <button className="action-btn" onClick={() => handleEdit(user)}>
                      Редактировать
                    </button>
                    {user.status !== 'active' && (
                      <button
                        className="action-btn action-btn-success"
                        onClick={() => handleStatusChange(user.id, 'active')}
                        disabled={changeStatusMutation.isPending}
                      >
                        Активировать
                      </button>
                    )}
                    {user.status === 'active' && (
                      <button
                        className="action-btn action-btn-warning"
                        onClick={() => handleStatusChange(user.id, 'inactive')}
                        disabled={changeStatusMutation.isPending}
                      >
                        Деактивировать
                      </button>
                    )}
                  </div>
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
