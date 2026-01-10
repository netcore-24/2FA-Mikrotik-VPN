import { useEffect, useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../services/api'
import './SettingsPage.css'

const SettingsPage = () => {
  const [activeTab, setActiveTab] = useState('system') // system | telegram
  const [selectedCategory, setSelectedCategory] = useState('')
  const [editingKey, setEditingKey] = useState(null)
  const [editValue, setEditValue] = useState('')
  const queryClient = useQueryClient()

  const { data: telegramSettings, isLoading: telegramLoading } = useQuery({
    queryKey: ['settings', 'telegram_templates'],
    queryFn: async () => {
      const response = await api.get('/settings', { params: { category: 'telegram_templates' } })
      return response.data
    },
    enabled: activeTab === 'telegram',
  })

  const [telegramDrafts, setTelegramDrafts] = useState({})

  useEffect(() => {
    if (activeTab !== 'telegram') return
    const items = telegramSettings?.items || []
    const next = {}
    for (const s of items) {
      // value может быть null для encrypted, но наши шаблоны не encrypted
      next[s.key] = typeof s.value === 'string' ? s.value : s.value == null ? '' : String(s.value)
    }
    setTelegramDrafts(next)
  }, [activeTab, telegramSettings])

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings', selectedCategory],
    queryFn: async () => {
      const params = selectedCategory ? { category: selectedCategory } : {}
      const response = await api.get('/settings', { params })
      return response.data
    },
    enabled: activeTab === 'system',
  })

  const { data: categories } = useQuery({
    queryKey: ['settings', 'categories'],
    queryFn: async () => {
      const response = await api.get('/settings/categories')
      return response.data
    },
    enabled: activeTab === 'system',
  })

  // Не показываем telegram_templates в "Системных", чтобы не было дублей с вкладкой Telegram сообщения
  useEffect(() => {
    if (activeTab !== 'system') return
    if (selectedCategory === 'telegram_templates') setSelectedCategory('')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab])

  const systemCategories = useMemo(() => {
    const cats = categories?.categories || []
    return cats.filter((c) => c !== 'telegram_templates')
  }, [categories])

  const systemSettingsItems = useMemo(() => {
    const items = settings?.items || []
    return items.filter((s) => s.category !== 'telegram_templates')
  }, [settings])

  const updateMutation = useMutation({
    mutationFn: async ({ key, value, category, description, isEncrypted }) => {
      const response = await api.put(`/settings/${key}`, {
        value,
        category,
        description,
        is_encrypted: isEncrypted,
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['settings'])
      setEditingKey(null)
    },
  })

  const updateTelegramMutation = useMutation({
    mutationFn: async ({ key, value, description }) => {
      const response = await api.put(`/settings/${key}`, {
        value,
        category: 'telegram_templates',
        description: description || null,
        is_encrypted: false,
      })
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['settings', 'telegram_templates'])
      queryClient.invalidateQueries(['settings'])
    },
  })

  const deleteMutation = useMutation({
    mutationFn: async (key) => {
      const response = await api.delete(`/settings/${key}`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['settings'])
    },
  })

  const handleEdit = async (setting) => {
    setEditingKey(setting.key)
    if (setting.is_encrypted) {
      // Для секретов в списке значение скрыто, поэтому подгружаем текущее значение отдельным запросом.
      try {
        const response = await api.get(`/settings/${setting.key}`)
        const v = response?.data?.value
        setEditValue(typeof v === 'object' ? JSON.stringify(v, null, 2) : String(v ?? ''))
      } catch (error) {
        alert(`Ошибка загрузки значения: ${error.response?.data?.detail || error.message}`)
        setEditValue('')
      }
      return
    }
    setEditValue(typeof setting.value === 'object' ? JSON.stringify(setting.value, null, 2) : String(setting.value || ''))
  }

  const handleSave = async (setting) => {
    try {
      let value = editValue
      // Пытаемся парсить как JSON, если это строка
      if (typeof editValue === 'string' && editValue.trim()) {
        if (editValue.trim().startsWith('{') || editValue.trim().startsWith('[')) {
          try {
            value = JSON.parse(editValue)
          } catch {
            // Если не JSON, оставляем как строку
          }
        }
      }

      await updateMutation.mutateAsync({
        key: setting.key,
        value,
        category: setting.category,
        description: setting.description,
        isEncrypted: setting.is_encrypted,
      })
    } catch (error) {
      alert(`Ошибка сохранения: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleDelete = async (key) => {
    if (window.confirm(`Удалить настройку "${key}"? Это действие необратимо.`)) {
      try {
        await deleteMutation.mutateAsync(key)
        alert('Настройка удалена')
      } catch (error) {
        alert(`Ошибка: ${error.response?.data?.detail || error.message}`)
      }
    }
  }

  const formatValue = (value, isEncrypted) => {
    if (isEncrypted) {
      return '••••••••'
    }
    if (typeof value === 'object') {
      return JSON.stringify(value, null, 2)
    }
    return String(value)
  }

  if (activeTab === 'system' && isLoading) {
    return (
      <div className="loading-container">
        <div className="loading">Загрузка настроек...</div>
      </div>
    )
  }

  if (activeTab === 'system' && (!settings || !settings.items || settings.items.length === 0)) {
    return (
      <div className="table-page">
        <div className="page-header">
          <h2>Системные настройки</h2>
        </div>
        <div className="empty-state">
          <div className="empty-state-icon">⚙️</div>
          <h3 className="empty-state-title">Настройки не найдены</h3>
          <p className="empty-state-description">Настройки системы появятся после инициализации базы данных</p>
        </div>
      </div>
    )
  }

  return (
    <div className="settings-page">
      <div className="page-header">
        <h2>Системные настройки</h2>
        <div className="filters">
          <button
            className={`tab-button ${activeTab === 'system' ? 'active' : ''}`}
            onClick={() => setActiveTab('system')}
            type="button"
          >
            Системные
          </button>
          <button
            className={`tab-button ${activeTab === 'telegram' ? 'active' : ''}`}
            onClick={() => setActiveTab('telegram')}
            type="button"
          >
            Telegram сообщения
          </button>
          {activeTab === 'system' && (
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="filter-select"
            >
              <option value="">Все категории</option>
              {systemCategories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {activeTab === 'telegram' ? (
        <div>
          <div style={{ margin: '0 0 1rem 0', padding: '0.75rem 1rem', border: '1px solid #e5e7eb', borderRadius: 8, background: '#fafafa' }}>
            <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Шаблоны сообщений Telegram</div>
            <div style={{ fontSize: '0.9rem', opacity: 0.85 }}>
              Плейсхолдеры: <code>{'{full_name}'}</code>, <code>{'{telegram_id}'}</code>, <code>{'{mikrotik_username}'}</code>,{' '}
              <code>{'{mikrotik_session_id}'}</code>, <code>{'{expires_at}'}</code>, <code>{'{hours_remaining}'}</code>, <code>{'{now}'}</code>.
            </div>
          </div>

          {telegramLoading ? (
            <div className="loading-container">
              <div className="loading">Загрузка Telegram-шаблонов...</div>
            </div>
          ) : (
            <div style={{ display: 'grid', gap: '1rem' }}>
              {(telegramSettings?.items || []).map((s) => (
                <div key={s.key} style={{ border: '1px solid #e5e7eb', borderRadius: 10, padding: '1rem', background: '#fff' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
                    <div>
                      <div style={{ fontWeight: 700 }}>
                        <code>{s.key}</code>
                      </div>
                      <div style={{ fontSize: '0.9rem', opacity: 0.85, marginTop: '0.25rem' }}>{s.description || ''}</div>
                    </div>
                    <button
                      className="action-btn action-btn-success"
                      onClick={() =>
                        updateTelegramMutation.mutateAsync({
                          key: s.key,
                          value: telegramDrafts[s.key] ?? '',
                          description: s.description,
                        })
                      }
                      disabled={updateTelegramMutation.isPending}
                    >
                      {updateTelegramMutation.isPending ? 'Сохранение…' : 'Сохранить'}
                    </button>
                  </div>
                  <textarea
                    value={telegramDrafts[s.key] ?? ''}
                    onChange={(e) => setTelegramDrafts((prev) => ({ ...prev, [s.key]: e.target.value }))}
                    rows={10}
                    className="edit-textarea"
                    style={{ marginTop: '0.75rem', width: '100%' }}
                    placeholder="Введите текст сообщения…"
                  />
                </div>
              ))}
              {(telegramSettings?.items || []).length === 0 && (
                <div className="no-data" style={{ padding: '0.75rem', opacity: 0.85 }}>
                  В категории <code>telegram</code> нет настроек.
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        <div className="settings-container">
          <table className="settings-table">
            <thead>
              <tr>
                <th>Ключ</th>
                <th>Значение</th>
                <th>Категория</th>
                <th>Описание</th>
                <th>Тип</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {systemSettingsItems.length === 0 ? (
                <tr>
                  <td colSpan="6" className="no-data">
                    Нет настроек
                  </td>
                </tr>
              ) : (
                systemSettingsItems.map((setting) => (
                  <tr key={setting.id || setting.key}>
                    <td>
                      <code>{setting.key}</code>
                    </td>
                    <td>
                      {editingKey === setting.key ? (
                        <>
                          {setting.is_encrypted && (
                            <div style={{ marginBottom: '0.5rem', fontSize: '0.9rem', opacity: 0.85 }}>
                              Значение зашифровано и не показывается. Введите новое значение, чтобы заменить его.
                            </div>
                          )}
                          <textarea
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            rows={3}
                            className="edit-textarea"
                            placeholder={setting.is_encrypted ? 'Введите новое значение…' : ''}
                          />
                        </>
                      ) : (
                        <pre className="setting-value">{formatValue(setting.value, setting.is_encrypted)}</pre>
                      )}
                    </td>
                    <td>{setting.category}</td>
                    <td>{setting.description || '-'}</td>
                    <td>
                      {setting.is_encrypted ? (
                        <span className="badge badge-encrypted">Зашифровано</span>
                      ) : (
                        <span className="badge badge-plain">Обычное</span>
                      )}
                    </td>
                    <td>
                      {editingKey === setting.key ? (
                        <>
                          <button
                            className="action-btn action-btn-success"
                            onClick={() => handleSave(setting)}
                            disabled={updateMutation.isPending}
                          >
                            {updateMutation.isPending ? 'Сохранение...' : 'Сохранить'}
                          </button>
                          <button
                            className="action-btn"
                            onClick={() => {
                              setEditingKey(null)
                              setEditValue('')
                            }}
                            disabled={updateMutation.isPending}
                          >
                            Отмена
                          </button>
                        </>
                      ) : (
                        <div className="row-actions">
                          <button className="action-btn" onClick={() => handleEdit(setting)}>
                            Редактировать
                          </button>
                          <button
                            className="action-btn action-btn-danger"
                            onClick={() => handleDelete(setting.key)}
                            disabled={deleteMutation.isPending}
                          >
                            {deleteMutation.isPending ? 'Удаление...' : 'Удалить'}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default SettingsPage
