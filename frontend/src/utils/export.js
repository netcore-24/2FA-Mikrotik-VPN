import * as XLSX from 'xlsx'

/**
 * Экспорт данных в CSV формат
 */
export const exportToCSV = (filename, data) => {
  // Преобразуем объект в массив строк для CSV
  const csvRows = []

  // Добавляем заголовки
  if (data.overview) {
    csvRows.push('Общая статистика')
    csvRows.push('Параметр,Значение')
    Object.entries(data.overview).forEach(([key, value]) => {
      csvRows.push(`${key},${value}`)
    })
    csvRows.push('')
  }

  // Статистика пользователей
  if (data.users) {
    csvRows.push('Статистика пользователей')
    csvRows.push('Параметр,Значение')
    Object.entries(data.users).forEach(([key, value]) => {
      if (typeof value === 'object' && value !== null) {
        Object.entries(value).forEach(([subKey, subValue]) => {
          csvRows.push(`${key}_${subKey},${subValue}`)
        })
      } else {
        csvRows.push(`${key},${value}`)
      }
    })
    csvRows.push('')
  }

  // Статистика сессий
  if (data.sessions) {
    csvRows.push('Статистика VPN сессий')
    csvRows.push('Параметр,Значение')
    Object.entries(data.sessions).forEach(([key, value]) => {
      if (typeof value === 'object' && value !== null) {
        Object.entries(value).forEach(([subKey, subValue]) => {
          csvRows.push(`${key}_${subKey},${subValue}`)
        })
      } else {
        csvRows.push(`${key},${value}`)
      }
    })
    csvRows.push('')
  }

  // Статистика заявок
  if (data.requests) {
    csvRows.push('Статистика заявок на регистрацию')
    csvRows.push('Параметр,Значение')
    Object.entries(data.requests).forEach(([key, value]) => {
      csvRows.push(`${key},${value}`)
    })
  }

  // Создаем Blob и скачиваем
  const csvContent = csvRows.join('\n')
  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)

  link.setAttribute('href', url)
  link.setAttribute('download', `${filename}_${new Date().toISOString().split('T')[0]}.csv`)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

/**
 * Экспорт данных в Excel формат
 */
export const exportToExcel = (filename, data) => {
  const workbook = XLSX.utils.book_new()

  // Лист с общей статистикой
  if (data.overview) {
    const overviewData = Object.entries(data.overview).map(([key, value]) => ({
      Параметр: key,
      Значение: value,
    }))
    const overviewSheet = XLSX.utils.json_to_sheet(overviewData)
    XLSX.utils.book_append_sheet(workbook, overviewSheet, 'Общая статистика')
  }

  // Лист со статистикой пользователей
  if (data.users) {
    const usersData = []
    Object.entries(data.users).forEach(([key, value]) => {
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        Object.entries(value).forEach(([subKey, subValue]) => {
          usersData.push({ Параметр: `${key}_${subKey}`, Значение: subValue })
        })
      } else {
        usersData.push({ Параметр: key, Значение: value })
      }
    })
    const usersSheet = XLSX.utils.json_to_sheet(usersData)
    XLSX.utils.book_append_sheet(workbook, usersSheet, 'Пользователи')
  }

  // Лист со статистикой сессий
  if (data.sessions) {
    const sessionsData = []
    Object.entries(data.sessions).forEach(([key, value]) => {
      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        Object.entries(value).forEach(([subKey, subValue]) => {
          sessionsData.push({ Параметр: `${key}_${subKey}`, Значение: subValue })
        })
      } else {
        sessionsData.push({ Параметр: key, Значение: value })
      }
    })
    const sessionsSheet = XLSX.utils.json_to_sheet(sessionsData)
    XLSX.utils.book_append_sheet(workbook, sessionsSheet, 'VPN Сессии')
  }

  // Лист со статистикой заявок
  if (data.requests) {
    const requestsData = Object.entries(data.requests).map(([key, value]) => ({
      Параметр: key,
      Значение: value,
    }))
    const requestsSheet = XLSX.utils.json_to_sheet(requestsData)
    XLSX.utils.book_append_sheet(workbook, requestsSheet, 'Заявки')
  }

  // Сохраняем файл
  XLSX.writeFile(workbook, `${filename}_${new Date().toISOString().split('T')[0]}.xlsx`)
}

/**
 * Экспорт таблицы данных в CSV
 */
export const exportTableToCSV = (filename, headers, rows) => {
  const csvRows = []
  csvRows.push(headers.join(','))
  rows.forEach((row) => {
    csvRows.push(row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
  })

  const csvContent = csvRows.join('\n')
  const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)

  link.setAttribute('href', url)
  link.setAttribute('download', `${filename}_${new Date().toISOString().split('T')[0]}.csv`)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

/**
 * Экспорт таблицы данных в Excel
 */
export const exportTableToExcel = (filename, sheetName, headers, rows) => {
  const workbook = XLSX.utils.book_new()
  const worksheet = XLSX.utils.aoa_to_sheet([headers, ...rows])
  XLSX.utils.book_append_sheet(workbook, worksheet, sheetName)
  XLSX.writeFile(workbook, `${filename}_${new Date().toISOString().split('T')[0]}.xlsx`)
}
