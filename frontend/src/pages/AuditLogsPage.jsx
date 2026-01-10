import './TablePage.css'

const AuditLogsPage = () => {
  return (
    <div className="table-page">
      <div className="page-header">
        <h2>Аудит</h2>
      </div>

      <div className="empty-state">
        <div className="empty-state-icon">🚧</div>
        <h3 className="empty-state-title">Функционал в разработке</h3>
        <p className="empty-state-description">
          Раздел аудита будет добавлен в следующих обновлениях.
        </p>
      </div>
    </div>
  )
}

export default AuditLogsPage
