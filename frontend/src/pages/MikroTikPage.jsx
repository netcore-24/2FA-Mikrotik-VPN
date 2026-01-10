import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../services/api'
import './TablePage.css'

const MikroTikPage = () => {
  const [activeTab, setActiveTab] = useState('configs')
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
      const response = await api.get('/mikrotik/firewall-rules')
      return response.data
    },
    enabled: activeTab === 'firewall',
  })

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
      await toggleRuleMutation.mutateAsync({ ruleId: rule.id, enabled })
    } catch (error) {
      alert(`Ошибка: ${error.response?.data?.detail || error.message}`)
    }
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
            <div className="loading">Загрузка...</div>
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
                  {configs?.items?.length === 0 ? (
                    <tr>
                      <td colSpan="7" className="no-data">
                        Нет конфигураций MikroTik
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
          {usersLoading ? (
            <div className="loading">Загрузка...</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Имя пользователя</th>
                  <th>Профиль</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {mikrotikUsers?.users?.length === 0 ? (
                  <tr>
                    <td colSpan="3" className="no-data">
                      Нет пользователей MikroTik
                    </td>
                  </tr>
                ) : (
                  mikrotikUsers?.users?.map((user) => (
                    <tr key={user.name}>
                      <td>{user.name}</td>
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
            <button className="action-btn" onClick={() => refetchRules()}>
              Обновить
            </button>
          </div>
          {rulesLoading ? (
            <div className="loading">Загрузка...</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Комментарий</th>
                  <th>Действие</th>
                  <th>Цепочка</th>
                  <th>Статус</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {firewallRules?.rules?.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="no-data">
                      Нет правил firewall
                    </td>
                  </tr>
                ) : (
                  firewallRules?.rules?.map((rule) => (
                    <tr key={rule.id}>
                      <td>{rule.id}</td>
                      <td>{rule.comment || '-'}</td>
                      <td>{rule.action || '-'}</td>
                      <td>{rule.chain || '-'}</td>
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
                          disabled={toggleRuleMutation.isPending}
                        >
                          {rule.disabled ? 'Включить' : 'Отключить'}
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
    </div>
  )
}

export default MikroTikPage
