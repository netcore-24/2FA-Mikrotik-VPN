import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from '../services/api'
import { exportTableToCSV, exportTableToExcel } from '../utils/export'
import './TablePage.css'

const AuditLogsPage = () => {
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({
    action: '',
    entity_type: '',
    user_id: '',
    admin_id: '',
  })
  const limit = 50

  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', page, filters],
    queryFn: async () => {
      const params = {
        skip: (page - 1) * limit,
        limit,
        ...Object.fromEntries(
          Object.entries(filters).filter(([_, value]) => value !== '')
        ),
      }
      const response = await api.get('/audit-logs', { params })
      return response.data
    },
  })

  const formatDetails = (details) => {
    if (!details) return '-'
    if (typeof details === 'string') {
      try {
        details = JSON.parse(details)
      } catch {
        return details
      }
    }
    if (typeof details === 'object') {
      return JSON.stringify(details, null, 2)
    }
    return String(details)
  }

  if (isLoading) {
    return <div className="loading">Загрузка...</div>
  }

  return (
    <div className="table-page">
      <div className="page-header">
        <h2>Журнал аудита</h2>
        <div className="header-actions">
          <div className="filters">
          <input
            type="text"
            placeholder="Действие"
            value={filters.action}
            onChange={(e) =>
              setFilters({ ...filters, action: e.target.value })
            }
            className="filter-input"
          />
          <input
            type="text"
            placeholder="Тип сущности"
            value={filters.entity_type}
            onChange={(e) =>
              setFilters({ ...filters, entity_type: e.target.value })
            }
            className="filter-input"
          />
          <button
            className="action-btn"
            onClick={() =>
              setFilters({ action: '', entity_type: '', user_id: '', admin_id: '' })
            }
          >
            Сбросить
          </button>
          </div>
          <div className="export-buttons">
            <button
              className="action-btn"
              onClick={() => {
                const headers = ['Дата', 'Действие', 'Тип', 'ID сущности', 'IP адрес', 'Детали']
                const rows = (data?.items || []).map((log) => [
                  new Date(log.created_at).toLocaleString('ru-RU'),
                  log.action,
                  log.entity_type || '-',
                  log.entity_id || '-',
                  log.ip_address || '-',
                  log.details ? JSON.stringify(log.details) : '-',
                ])
                exportTableToCSV('audit-logs', headers, rows)
              }}
            >
              CSV
            </button>
            <button
              className="action-btn"
              onClick={() => {
                const headers = ['Дата', 'Действие', 'Тип', 'ID сущности', 'IP адрес', 'Детали']
                const rows = (data?.items || []).map((log) => [
                  new Date(log.created_at).toLocaleString('ru-RU'),
                  log.action,
                  log.entity_type || '-',
                  log.entity_id || '-',
                  log.ip_address || '-',
                  log.details ? JSON.stringify(log.details) : '-',
                ])
                exportTableToExcel('audit-logs', 'Журнал аудита', headers, rows)
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
              <th>Дата</th>
              <th>Действие</th>
              <th>Тип</th>
              <th>ID сущности</th>
              <th>IP адрес</th>
              <th>Детали</th>
            </tr>
          </thead>
          <tbody>
            {data?.items?.length === 0 ? (
              <tr>
                <td colSpan="6" className="no-data">
                  Нет записей в журнале аудита
                </td>
              </tr>
            ) : (
              data?.items?.map((log) => (
                <tr key={log.id}>
                  <td>
                    {new Date(log.created_at).toLocaleString('ru-RU')}
                  </td>
                  <td>
                    <code>{log.action}</code>
                  </td>
                  <td>{log.entity_type || '-'}</td>
                  <td>
                    {log.entity_id ? `${log.entity_id.substring(0, 8)}...` : '-'}
                  </td>
                  <td>{log.ip_address || '-'}</td>
                  <td>
                    <details className="details-cell">
                      <summary>Показать</summary>
                      <pre>{formatDetails(log.details)}</pre>
                    </details>
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
            записей)
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

export default AuditLogsPage
