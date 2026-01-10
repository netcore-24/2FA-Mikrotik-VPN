import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../services/api'
import './SettingsPage.css'

const SettingsPage = () => {
  const [selectedCategory, setSelectedCategory] = useState('')
  const [editingKey, setEditingKey] = useState(null)
  const [editValue, setEditValue] = useState('')
  const queryClient = useQueryClient()

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings', selectedCategory],
    queryFn: async () => {
      const params = selectedCategory ? { category: selectedCategory } : {}
      const response = await api.get('/settings', { params })
      return response.data
    },
  })

  const { data: categories } = useQuery({
    queryKey: ['settings', 'categories'],
    queryFn: async () => {
      const response = await api.get('/settings/categories')
      return response.data
    },
  })

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

  const deleteMutation = useMutation({
    mutationFn: async (key) => {
      const response = await api.delete(`/settings/${key}`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['settings'])
    },
  })

  const handleEdit = (setting) => {
    setEditingKey(setting.key)
    setEditValue(
      typeof setting.value === 'object'
        ? JSON.stringify(setting.value, null, 2)
        : String(setting.value || '')
    )
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

  if (isLoading) {
    return <div className="loading">Загрузка настроек...</div>
  }

  return (
    <div className="settings-page">
      <div className="page-header">
        <h2>Системные настройки</h2>
        <div className="filters">
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="filter-select"
          >
            <option value="">Все категории</option>
            {categories?.categories?.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>
      </div>

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
            {settings?.items?.length === 0 ? (
              <tr>
                <td colSpan="6" className="no-data">
                  Нет настроек
                </td>
              </tr>
            ) : (
              settings?.items?.map((setting) => (
                <tr key={setting.id || setting.key}>
                  <td>
                    <code>{setting.key}</code>
                  </td>
                  <td>
                    {editingKey === setting.key ? (
                      <textarea
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        rows={3}
                        className="edit-textarea"
                      />
                    ) : (
                      <pre className="setting-value">
                        {formatValue(setting.value, setting.is_encrypted)}
                      </pre>
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
                      <>
                        <button
                          className="action-btn"
                          onClick={() => handleEdit(setting)}
                        >
                          Редактировать
                        </button>
                        <button
                          className="action-btn action-btn-danger"
                          onClick={() => handleDelete(setting.key)}
                          disabled={deleteMutation.isPending}
                        >
                          {deleteMutation.isPending ? 'Удаление...' : 'Удалить'}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default SettingsPage
