import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../services/api'
import './TablePage.css'

const MikroTikPage = () => {
  const [activeTab, setActiveTab] = useState('configs')
  const [firewallBindingFilter, setFirewallBindingFilter] = useState('all') // all | bound | unbound
  const [firewallSearch, setFirewallSearch] = useState('')
  const queryClient = useQueryClient()

  // Конфигурации
  const { data: configs, isLoading: configsLoading } = useQuery({
    queryKey: ['mikrotik', 'configs'],
    queryFn: async () => {
      const response = await api.get('/mikrotik/configs')
      return response.data
    },
  })

  const testConfigMutation = useMutation({
    mutationFn: async (configId) => {
      const response = await api.post(`/mikrotik/configs/${configId}/test`)
      return response.data
    },
  })

  // Пользователи MikroTik
  const { data: mikrotikUsers, isLoading: usersLoading, refetch: refetchUsers } = useQuery({
    queryKey: ['mikrotik', 'users'],
    queryFn: async () => {
      const response = await api.get('/mikrotik/users')
      return response.data
    },
    enabled: activeTab === 'users',
  })

  const deleteUserMutation = useMutation({
    mutationFn: async (username) => {
      const response = await api.delete(`/mikrotik/users/${username}`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['mikrotik', 'users'])
    },
  })

  // Firewall правила
  const { data: firewallRules, isLoading: rulesLoading, refetch: refetchRules } = useQuery({
    queryKey: ['mikrotik', 'firewall-rules'],
    queryFn: async () => {
      // показываем только правила, содержащие "2FA" в комментарии
      const response = await api.get('/mikrotik/firewall-rules', { params: { comment: '2FA' } })
      return response.data
    },
    enabled: activeTab === 'firewall',
  })

  const { data: firewallBindings } = useQuery({
    queryKey: ['mikrotik', 'firewall-rules', 'bindings'],
    queryFn: async () => {
      const response = await api.get('/mikrotik/firewall-rules/bindings')
      return response.data
    },
    enabled: activeTab === 'firewall',
  })

  const { data: systemUsers } = useQuery({
    queryKey: ['users', 'for-firewall-binding'],
    queryFn: async () => {
      const response = await api.get('/users', { params: { skip: 0, limit: 1000 } })
      return response.data
    },
    enabled: activeTab === 'firewall',
  })

  const bindingsByComment = useMemo(() => {
    const map = new Map()
    for (const b of firewallBindings || []) {
      if (b?.firewall_rule_comment) map.set(b.firewall_rule_comment, b)
    }
    return map
  }, [firewallBindings])

  const systemUsersById = useMemo(() => {
    const map = new Map()
    for (const u of systemUsers?.items || []) {
      map.set(u.id, u)
    }
    return map
  }, [systemUsers])

  const filteredFirewallRules = useMemo(() => {
    // Доп. страховка: даже если backend вернул всё, показываем только правила с "2FA" в comment
    const rules = (firewallRules?.rules || []).filter((r) =>
      String(r.comment || '')
        .toLowerCase()
        .includes('2fa')
    )
    const q = (firewallSearch || '').trim().toLowerCase()
    return rules.filter((r) => {
      const comment = (r.comment || '').toString()
      const bound = bindingsByComment.has(comment)
      if (firewallBindingFilter === 'bound' && !bound) return false
      if (firewallBindingFilter === 'unbound' && bound) return false
      if (q) {
        if (!comment.toLowerCase().includes(q)) return false
      }
      return true
    })
  }, [firewallRules, firewallSearch, firewallBindingFilter, bindingsByComment])

  const toggleRuleMutation = useMutation({
    mutationFn: async ({ ruleId, enabled }) => {
      const endpoint = enabled
        ? `/mikrotik/firewall-rules/${ruleId}/enable`
        : `/mikrotik/firewall-rules/${ruleId}/disable`
      const response = await api.post(endpoint)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['mikrotik', 'firewall-rules'])
    },
  })

  const assignRuleMutation = useMutation({
    mutationFn: async ({ ruleId, userId }) => {
      const response = await api.post(`/mikrotik/firewall-rules/${ruleId}/assign`, { user_id: userId || null })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['mikrotik', 'firewall-rules', 'bindings'])
    },
  })

  const handleTestConfig = async (configId) => {
    try {
      const result = await testConfigMutation.mutateAsync(configId)
      alert(result.success ? 'Подключение успешно!' : `Ошибка: ${result.message}`)
    } catch (error) {
      alert(`Ошибка тестирования: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleDeleteUser = async (username) => {
    if (window.confirm(`Удалить пользователя MikroTik "${username}"?`)) {
      try {
        await deleteUserMutation.mutateAsync(username)
      } catch (error) {
        alert(`Ошибка: ${error.response?.data?.detail || error.message}`)
      }
    }
  }

  const handleToggleRule = async (rule, enabled) => {
    try {
      const ruleId = rule.id ?? (rule.number != null ? String(rule.number) : null)
      if (!ruleId) {
        alert('Не удалось определить ID/номер правила (MikroTik не вернул идентификатор).')
        return
      }
      await toggleRuleMutation.mutateAsync({ ruleId, enabled })
    } catch (error) {
      alert(`Ошибка: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleAssignRule = async (ruleId, userId) => {
    try {
      await assignRuleMutation.mutateAsync({ ruleId, userId })
    } catch (error) {
      alert(`Ошибка: ${error.response?.data?.detail || error.message}`)
    }
  }

  if (configsLoading || (activeTab === 'users' && usersLoading) || (activeTab === 'firewall' && rulesLoading)) {
    return (
      <div className="loading-container">
        <div className="loading">Загрузка данных MikroTik...</div>
      </div>
    )
  }

  return (
    <div className="table-page">
      <div className="page-header">
        <h2>Управление MikroTik</h2>
        <div className="tabs">
          <button
            className={`tab-button ${activeTab === 'configs' ? 'active' : ''}`}
            onClick={() => setActiveTab('configs')}
          >
            Конфигурации
          </button>
          <button
            className={`tab-button ${activeTab === 'users' ? 'active' : ''}`}
            onClick={() => setActiveTab('users')}
          >
            Пользователи
          </button>
          <button
            className={`tab-button ${activeTab === 'firewall' ? 'active' : ''}`}
            onClick={() => setActiveTab('firewall')}
          >
            Firewall Правила
          </button>
        </div>
      </div>

      {/* Конфигурации */}
      {activeTab === 'configs' && (
        <div className="table-container">
          {configsLoading ? (
            <div className="loading-container">
              <div className="loading">Загрузка конфигураций...</div>
            </div>
          ) : (
            <>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Название</th>
                    <th>Хост</th>
                    <th>Порт</th>
                    <th>Пользователь</th>
                    <th>Тип подключения</th>
                    <th>Активна</th>
                    <th>Действия</th>
                  </tr>
                </thead>
                <tbody>
                  {!configs?.items || configs.items.length === 0 ? (
                    <tr>
                      <td colSpan="7">
                        <div className="empty-state" style={{ margin: '2rem', padding: '2rem' }}>
                          <div className="empty-state-icon">🛡️</div>
                          <h3 className="empty-state-title">Нет конфигураций MikroTik</h3>
                          <p className="empty-state-description">Настройте подключение к MikroTik роутеру через мастер настройки</p>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    configs?.items?.map((config) => (
                      <tr key={config.id}>
                        <td>{config.name}</td>
                        <td>{config.host}</td>
                        <td>{config.port}</td>
                        <td>{config.username}</td>
                        <td>{config.connection_type}</td>
                        <td>
                          {config.is_active ? (
                            <span className="status-badge status-active">Активна</span>
                          ) : (
                            <span className="status-badge status-rejected">Неактивна</span>
                          )}
                        </td>
                        <td>
                          <button
                            className="action-btn"
                            onClick={() => handleTestConfig(config.id)}
                            disabled={testConfigMutation.isPending}
                          >
                            Тест
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {/* Пользователи MikroTik */}
      {activeTab === 'users' && (
        <div className="table-container">
          <div className="page-header">
            <button className="action-btn" onClick={() => refetchUsers()}>
              Обновить
            </button>
          </div>
          {mikrotikUsers?.warning && (
            <div
              style={{
                margin: '0 0 1rem 0',
                padding: '0.75rem 1rem',
                border: '1px solid #f0c36d',
                background: '#fff8e6',
                borderRadius: '8px',
              }}
            >
              {mikrotikUsers.warning}
            </div>
          )}
          {usersLoading ? (
            <div className="loading-container">
              <div className="loading">Загрузка пользователей MikroTik...</div>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Имя пользователя</th>
                  <th>Статус</th>
                  <th>Профиль</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {!mikrotikUsers?.users || mikrotikUsers.users.length === 0 ? (
                  <tr>
                    <td colSpan="4">
                      <div className="empty-state" style={{ margin: '2rem', padding: '2rem' }}>
                        <div className="empty-state-icon">👤</div>
                        <h3 className="empty-state-title">Нет пользователей MikroTik</h3>
                        <p className="empty-state-description">
                          {mikrotikUsers?.warning
                            ? mikrotikUsers.warning
                            : 'Проверьте, что на роутере настроены VPN пользователи (User Manager или PPP secrets).'}
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  mikrotikUsers?.users?.map((user, idx) => (
                    <tr key={`${user.name || 'user'}-${idx}`}>
                      <td>{user.name}</td>
                      <td>
                        {user.disabled ? (
                          <span className="status-badge status-rejected">Отключен</span>
                        ) : (
                          <span className="status-badge status-active">Включен</span>
                        )}
                      </td>
                      <td>{user.profile || '-'}</td>
                      <td>
                        <button
                          className="action-btn action-btn-danger"
                          onClick={() => handleDeleteUser(user.name)}
                          disabled={deleteUserMutation.isPending}
                        >
                          Удалить
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Firewall правила */}
      {activeTab === 'firewall' && (
        <div className="table-container">
          <div className="page-header">
            <div className="filters" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <button className="action-btn" onClick={() => refetchRules()}>
                Обновить
              </button>
              <select
                className="filter-select"
                value={firewallBindingFilter}
                onChange={(e) => setFirewallBindingFilter(e.target.value)}
                style={{ minWidth: 220 }}
              >
                <option value="all">Все (2FA)</option>
                <option value="bound">Только привязанные</option>
                <option value="unbound">Только не привязанные</option>
              </select>
              <input
                type="text"
                className="filter-input"
                placeholder="Поиск по комментарию…"
                value={firewallSearch}
                onChange={(e) => setFirewallSearch(e.target.value)}
                style={{ minWidth: 260 }}
              />
            </div>
          </div>
          {rulesLoading ? (
            <div className="loading-container">
              <div className="loading">Загрузка правил firewall...</div>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>№</th>
                  <th>ID (.id)</th>
                  <th>Комментарий</th>
                  <th>Действие</th>
                  <th>Цепочка</th>
                  <th>Привязано к пользователю</th>
                  <th>Статус</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {!firewallRules?.rules || firewallRules.rules.length === 0 ? (
                  <tr>
                    <td colSpan="8">
                      <div className="empty-state" style={{ margin: '2rem', padding: '2rem' }}>
                        <div className="empty-state-icon">🔐</div>
                        <h3 className="empty-state-title">Нет правил firewall с комментарием "2FA"</h3>
                        <p className="empty-state-description">
                          Создайте/пометьте правила комментарием содержащим "2FA" (например: "2FA noadmin") — тогда они появятся здесь.
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : filteredFirewallRules.length === 0 ? (
                  <tr>
                    <td colSpan="8" className="no-data">
                      Нет правил по текущему фильтру
                    </td>
                  </tr>
                ) : (
                  filteredFirewallRules.map((rule, idx) => {
                    const bound = (firewallBindings || []).find((b) => b.firewall_rule_comment === (rule.comment || ''))
                    const boundUserId = bound?.user_id || ''
                    const boundUser = boundUserId ? systemUsersById.get(boundUserId) : null
                    const ruleKey = rule.id ?? rule.number ?? idx
                    const ruleIdentifier = rule.id ?? (rule.number != null ? String(rule.number) : null)
                    return (
                    <tr key={ruleKey}>
                      <td>{rule.number ?? '-'}</td>
                      <td>{rule.id}</td>
                      <td>{rule.comment || '-'}</td>
                      <td>{rule.action || '-'}</td>
                      <td>{rule.chain || '-'}</td>
                      <td>
                        {boundUser ? (
                          <div style={{ fontSize: '0.9rem', marginBottom: '0.25rem' }}>
                            Сейчас: <b>{boundUser.full_name || boundUser.telegram_id || boundUser.id.slice(0, 8)}</b>
                          </div>
                        ) : (
                          <div style={{ fontSize: '0.9rem', marginBottom: '0.25rem', opacity: 0.8 }}>
                            Сейчас: <b>—</b>
                          </div>
                        )}
                        <select
                          className="filter-select"
                          value={boundUserId}
                          onChange={(e) =>
                            ruleIdentifier && handleAssignRule(ruleIdentifier, e.target.value || null)
                          }
                          disabled={assignRuleMutation.isPending || !rule.comment || !ruleIdentifier}
                        >
                          <option value="">— не привязано —</option>
                          {(systemUsers?.items || []).map((u) => (
                            <option key={u.id} value={u.id}>
                              {u.full_name || u.telegram_id || u.id.slice(0, 8)}
                            </option>
                          ))}
                        </select>
                        {!rule.comment && (
                          <div style={{ fontSize: '0.85rem', opacity: 0.8, marginTop: '0.25rem' }}>
                            У правила нет comment — привязка невозможна
                          </div>
                        )}
                      </td>
                      <td>
                        {rule.disabled ? (
                          <span className="status-badge status-rejected">Отключено</span>
                        ) : (
                          <span className="status-badge status-active">Включено</span>
                        )}
                      </td>
                      <td>
                        <button
                          className={`action-btn ${
                            rule.disabled
                              ? 'action-btn-success'
                              : 'action-btn-warning'
                          }`}
                          onClick={() => handleToggleRule(rule, rule.disabled)}
                          disabled={toggleRuleMutation.isPending || !ruleIdentifier}
                        >
                          {rule.disabled ? 'Включить' : 'Отключить'}
                        </button>
                      </td>
                    </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

export default MikroTikPage
