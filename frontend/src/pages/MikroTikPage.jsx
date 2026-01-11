import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../services/api'
import './TablePage.css'

const MikroTikPage = () => {
  const [activeTab, setActiveTab] = useState('configs')
  const [firewallBindingFilter, setFirewallBindingFilter] = useState('all') // all | bound | unbound
  const [firewallSearch, setFirewallSearch] = useState('')
  const [mikrotikUsersBindingFilter, setMikrotikUsersBindingFilter] = useState('all') // all | bound | unbound
  const [mikrotikUsersStatusFilter, setMikrotikUsersStatusFilter] = useState('all') // all | enabled | disabled
  const [mikrotikUsersProfileFilter, setMikrotikUsersProfileFilter] = useState('all') // all | <profile>
  const [mikrotikUsersSearch, setMikrotikUsersSearch] = useState('')
  const [mikrotikUsersSort, setMikrotikUsersSort] = useState({ key: 'name', dir: 'asc' }) // key: name|status|profile|bound
  const [mikrotikSessionsSearch, setMikrotikSessionsSearch] = useState('')
  const [mikrotikSessionsSourceFilter, setMikrotikSessionsSourceFilter] = useState('all') // all | user_manager_session | ppp_active
  const [mikrotikSessionsActiveFilter, setMikrotikSessionsActiveFilter] = useState('all') // all | active | inactive
  const [mikrotikSessionsSort, setMikrotikSessionsSort] = useState({ key: 'active', dir: 'desc' }) // key: active|user|source
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

  // Сессии MikroTik (User Manager sessions + PPP active)
  const { data: mikrotikSessions, isLoading: sessionsLoading, refetch: refetchSessions } = useQuery({
    queryKey: ['mikrotik', 'sessions'],
    queryFn: async () => {
      const response = await api.get('/mikrotik/sessions')
      return response.data
    },
    enabled: activeTab === 'sessions',
  })

  const filteredMikrotikSessions = useMemo(() => {
    const q = (mikrotikSessionsSearch || '').trim().toLowerCase()
    const sessions = mikrotikSessions?.sessions || []

    const filtered = sessions.filter((s) => {
      const user = String(s?.user || '').trim()
      const sid = String(s?.mikrotik_session_id || '').trim()
      const source = String(s?.source || '').trim()
      const active = !!s?.active

      if (mikrotikSessionsSourceFilter !== 'all' && source !== mikrotikSessionsSourceFilter) return false
      if (mikrotikSessionsActiveFilter === 'active' && !active) return false
      if (mikrotikSessionsActiveFilter === 'inactive' && active) return false
      if (q) {
        const hay = `${user} ${sid} ${source}`.toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })

    const dirMul = mikrotikSessionsSort.dir === 'desc' ? -1 : 1
    const getKey = (s) => {
      const user = String(s?.user || '').toLowerCase()
      const source = String(s?.source || '').toLowerCase()
      const active = !!s?.active
      if (mikrotikSessionsSort.key === 'user') return user
      if (mikrotikSessionsSort.key === 'source') return source
      // active first by default
      return active ? 0 : 1
    }

    filtered.sort((a, b) => {
      const ka = getKey(a)
      const kb = getKey(b)
      if (ka < kb) return -1 * dirMul
      if (ka > kb) return 1 * dirMul
      return 0
    })

    return filtered
  }, [
    mikrotikSessions,
    mikrotikSessionsSearch,
    mikrotikSessionsSourceFilter,
    mikrotikSessionsActiveFilter,
    mikrotikSessionsSort,
  ])

  const { data: systemUsersForMikrotik } = useQuery({
    queryKey: ['users', 'for-mikrotik-users-binding'],
    queryFn: async () => {
      const response = await api.get('/users', { params: { skip: 0, limit: 1000 } })
      return response.data
    },
    enabled: activeTab === 'users',
  })

  const systemUsersByMikrotikUsername = useMemo(() => {
    const map = new Map()
    for (const u of systemUsersForMikrotik?.items || []) {
      for (const username of u?.mikrotik_usernames || []) {
        const key = String(username || '').trim()
        if (!key) continue
        if (!map.has(key)) map.set(key, [])
        map.get(key).push(u)
      }
    }
    return map
  }, [systemUsersForMikrotik])

  const availableMikrotikProfiles = useMemo(() => {
    const set = new Set()
    for (const u of mikrotikUsers?.users || []) {
      const p = (u?.profile || '').toString().trim()
      if (p) set.add(p)
    }
    return Array.from(set).sort((a, b) => a.localeCompare(b))
  }, [mikrotikUsers])

  const filteredMikrotikUsers = useMemo(() => {
    const q = (mikrotikUsersSearch || '').trim().toLowerCase()
    const users = mikrotikUsers?.users || []

    const filtered = users.filter((u) => {
      const name = String(u?.name || '').trim()
      const profile = String(u?.profile || '').trim()
      const disabled = !!u?.disabled
      const bound = systemUsersByMikrotikUsername.has(name)

      if (mikrotikUsersStatusFilter === 'enabled' && disabled) return false
      if (mikrotikUsersStatusFilter === 'disabled' && !disabled) return false
      if (mikrotikUsersBindingFilter === 'bound' && !bound) return false
      if (mikrotikUsersBindingFilter === 'unbound' && bound) return false
      if (mikrotikUsersProfileFilter !== 'all' && profile !== mikrotikUsersProfileFilter) return false

      if (q) {
        const hay = `${name} ${profile}`.toLowerCase()
        if (!hay.includes(q)) return false
      }
      return true
    })

    const dirMul = mikrotikUsersSort.dir === 'desc' ? -1 : 1
    const getKey = (u) => {
      const name = String(u?.name || '')
      const profile = String(u?.profile || '')
      const disabled = !!u?.disabled
      const bound = systemUsersByMikrotikUsername.has(name)
      if (mikrotikUsersSort.key === 'status') return disabled ? 1 : 0
      if (mikrotikUsersSort.key === 'profile') return profile.toLowerCase()
      if (mikrotikUsersSort.key === 'bound') return bound ? 0 : 1
      return name.toLowerCase()
    }
    filtered.sort((a, b) => {
      const ka = getKey(a)
      const kb = getKey(b)
      if (ka < kb) return -1 * dirMul
      if (ka > kb) return 1 * dirMul
      return 0
    })
    return filtered
  }, [
    mikrotikUsers,
    mikrotikUsersSearch,
    mikrotikUsersStatusFilter,
    mikrotikUsersBindingFilter,
    mikrotikUsersProfileFilter,
    mikrotikUsersSort,
    systemUsersByMikrotikUsername,
  ])

  const deleteUserMutation = useMutation({
    mutationFn: async (username) => {
      const response = await api.delete(`/mikrotik/users/${username}`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['mikrotik', 'users'])
    },
  })

  const toggleMikrotikUserMutation = useMutation({
    mutationFn: async ({ username, disabled }) => {
      const endpoint = disabled ? `/mikrotik/users/${encodeURIComponent(username)}/disable` : `/mikrotik/users/${encodeURIComponent(username)}/enable`
      const response = await api.post(endpoint)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['mikrotik', 'users'])
    },
  })

  const disconnectMikrotikUserMutation = useMutation({
    mutationFn: async (username) => {
      const response = await api.post(`/mikrotik/users/${encodeURIComponent(username)}/disconnect`)
      return response.data
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

  const handleToggleMikrotikUser = async (username, disabled) => {
    try {
      await toggleMikrotikUserMutation.mutateAsync({ username, disabled })
    } catch (error) {
      alert(`Ошибка: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleDisconnectMikrotikUser = async (username) => {
    if (!window.confirm(`Отключить активные сессии пользователя "${username}" на MikroTik?`)) return
    try {
      await disconnectMikrotikUserMutation.mutateAsync(username)
      alert('Команда отправлена. Если есть активные сессии — они будут завершены.')
    } catch (error) {
      alert(`Ошибка: ${error.response?.data?.detail || error.message}`)
    }
  }

  const toggleUsersSort = (key) => {
    setMikrotikUsersSort((prev) => {
      if (prev.key !== key) return { key, dir: 'asc' }
      return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
    })
  }

  const toggleSessionsSort = (key) => {
    setMikrotikSessionsSort((prev) => {
      if (prev.key !== key) return { key, dir: key === 'active' ? 'desc' : 'asc' }
      return { key, dir: prev.dir === 'asc' ? 'desc' : 'asc' }
    })
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
            className={`tab-button ${activeTab === 'sessions' ? 'active' : ''}`}
            onClick={() => setActiveTab('sessions')}
          >
            Сессии
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
            <div className="filters" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <button className="action-btn" onClick={() => refetchUsers()}>
                Обновить
              </button>
              <select
                className="filter-select"
                value={mikrotikUsersStatusFilter}
                onChange={(e) => setMikrotikUsersStatusFilter(e.target.value)}
                style={{ minWidth: 170 }}
              >
                <option value="all">Все статусы</option>
                <option value="enabled">Только включённые</option>
                <option value="disabled">Только отключённые</option>
              </select>
              <select
                className="filter-select"
                value={mikrotikUsersBindingFilter}
                onChange={(e) => setMikrotikUsersBindingFilter(e.target.value)}
                style={{ minWidth: 210 }}
              >
                <option value="all">Все (привязка)</option>
                <option value="bound">Только привязанные</option>
                <option value="unbound">Только не привязанные</option>
              </select>
              <select
                className="filter-select"
                value={mikrotikUsersProfileFilter}
                onChange={(e) => setMikrotikUsersProfileFilter(e.target.value)}
                style={{ minWidth: 180 }}
              >
                <option value="all">Все профили</option>
                {availableMikrotikProfiles.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
              <input
                type="text"
                className="filter-input"
                placeholder="Поиск по username/профилю…"
                value={mikrotikUsersSearch}
                onChange={(e) => setMikrotikUsersSearch(e.target.value)}
                style={{ minWidth: 240 }}
              />
            </div>
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
                  <th style={{ cursor: 'pointer' }} onClick={() => toggleUsersSort('name')}>
                    Имя пользователя
                  </th>
                  <th style={{ cursor: 'pointer' }} onClick={() => toggleUsersSort('status')}>
                    Статус
                  </th>
                  <th style={{ cursor: 'pointer' }} onClick={() => toggleUsersSort('profile')}>
                    Группа / профиль
                  </th>
                  <th style={{ cursor: 'pointer' }} onClick={() => toggleUsersSort('bound')}>
                    Привязано к пользователю системы
                  </th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {!mikrotikUsers?.users || mikrotikUsers.users.length === 0 ? (
                  <tr>
                    <td colSpan="5">
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
                ) : filteredMikrotikUsers.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="no-data">
                      Нет пользователей по текущему фильтру
                    </td>
                  </tr>
                ) : (
                  filteredMikrotikUsers.map((user, idx) => {
                    const username = String(user.name || '').trim()
                    const boundUsers = systemUsersByMikrotikUsername.get(username) || []
                    return (
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
                          {boundUsers.length ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.15rem' }}>
                              {boundUsers.map((u) => (
                                <div key={u.id} style={{ fontSize: '0.9rem' }}>
                                  <b>{u.full_name || u.telegram_id || u.id.slice(0, 8)}</b>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <span style={{ opacity: 0.8 }}>—</span>
                          )}
                        </td>
                        <td>
                          <button
                            className={`action-btn ${user.disabled ? 'action-btn-success' : 'action-btn-warning'}`}
                            onClick={() => handleToggleMikrotikUser(username, !user.disabled)}
                            disabled={toggleMikrotikUserMutation.isPending || !username}
                            style={{ marginRight: '0.5rem' }}
                          >
                            {user.disabled ? 'Включить' : 'Отключить'}
                          </button>
                          <button
                            className="action-btn"
                            onClick={() => handleDisconnectMikrotikUser(username)}
                            disabled={disconnectMikrotikUserMutation.isPending || !username}
                            style={{ marginRight: '0.5rem' }}
                          >
                            Сбросить сессию
                          </button>
                          <button
                            className="action-btn action-btn-danger"
                            onClick={() => handleDeleteUser(user.name)}
                            disabled={deleteUserMutation.isPending}
                          >
                            Удалить
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

      {/* Сессии MikroTik */}
      {activeTab === 'sessions' && (
        <div className="table-container">
          <div className="page-header">
            <div className="filters" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <button className="action-btn" onClick={() => refetchSessions()}>
                Обновить
              </button>
              <select
                className="filter-select"
                value={mikrotikSessionsActiveFilter}
                onChange={(e) => setMikrotikSessionsActiveFilter(e.target.value)}
                style={{ minWidth: 170 }}
              >
                <option value="all">Все статусы</option>
                <option value="active">Только активные</option>
                <option value="inactive">Только неактивные</option>
              </select>
              <select
                className="filter-select"
                value={mikrotikSessionsSourceFilter}
                onChange={(e) => setMikrotikSessionsSourceFilter(e.target.value)}
                style={{ minWidth: 210 }}
              >
                <option value="all">Все источники</option>
                <option value="user_manager_session">User Manager</option>
                <option value="ppp_active">PPP active</option>
              </select>
              <input
                type="text"
                className="filter-input"
                placeholder="Поиск по user/session-id…"
                value={mikrotikSessionsSearch}
                onChange={(e) => setMikrotikSessionsSearch(e.target.value)}
                style={{ minWidth: 240 }}
              />
              <div style={{ opacity: 0.85, fontSize: '0.9rem' }}>
                Всего: <b>{mikrotikSessions?.total ?? 0}</b>
              </div>
            </div>
          </div>

          {sessionsLoading ? (
            <div className="loading-container">
              <div className="loading">Загрузка сессий MikroTik...</div>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ cursor: 'pointer' }} onClick={() => toggleSessionsSort('user')}>
                    Пользователь
                  </th>
                  <th>Session ID</th>
                  <th style={{ cursor: 'pointer' }} onClick={() => toggleSessionsSort('source')}>
                    Источник
                  </th>
                  <th style={{ cursor: 'pointer' }} onClick={() => toggleSessionsSort('active')}>
                    Статус
                  </th>
                </tr>
              </thead>
              <tbody>
                {!mikrotikSessions?.sessions || mikrotikSessions.sessions.length === 0 ? (
                  <tr>
                    <td colSpan="4">
                      <div className="empty-state" style={{ margin: '2rem', padding: '2rem' }}>
                        <div className="empty-state-icon">🔌</div>
                        <h3 className="empty-state-title">Нет сессий MikroTik</h3>
                        <p className="empty-state-description">
                          Активные подключения появятся здесь, когда пользователь подключится к VPN (User Manager/PPP).
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : filteredMikrotikSessions.length === 0 ? (
                  <tr>
                    <td colSpan="4" className="no-data">
                      Нет сессий по текущему фильтру
                    </td>
                  </tr>
                ) : (
                  filteredMikrotikSessions.map((s, idx) => (
                    <tr key={`${s.mikrotik_session_id || 'sid'}-${idx}`}>
                      <td>{s.user || '-'}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.9rem' }}>{s.mikrotik_session_id || '-'}</td>
                      <td>{s.source || '-'}</td>
                      <td>
                        {s.active ? (
                          <span className="status-badge status-active">Активна</span>
                        ) : (
                          <span className="status-badge status-rejected">Неактивна</span>
                        )}
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
