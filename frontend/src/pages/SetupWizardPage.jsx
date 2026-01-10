import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import api from '../services/api'
import Modal from '../components/Modal'
import './SetupWizardPage.css'

// Список популярных часовых поясов
const TIMEZONES = [
  { value: 'UTC', label: 'UTC (Всемирное координированное время)' },
  { value: 'Europe/Moscow', label: 'Москва (MSK, UTC+3)' },
  { value: 'Europe/Kiev', label: 'Киев (EET, UTC+2)' },
  { value: 'Europe/Minsk', label: 'Минск (MSK, UTC+3)' },
  { value: 'Asia/Almaty', label: 'Алматы (ALMT, UTC+6)' },
  { value: 'Asia/Tashkent', label: 'Ташкент (UZT, UTC+5)' },
  { value: 'Asia/Yekaterinburg', label: 'Екатеринбург (YEKT, UTC+5)' },
  { value: 'Asia/Novosibirsk', label: 'Новосибирск (NOVT, UTC+7)' },
  { value: 'Europe/London', label: 'Лондон (GMT, UTC+0)' },
  { value: 'Europe/Berlin', label: 'Берлин (CET, UTC+1)' },
  { value: 'Europe/Paris', label: 'Париж (CET, UTC+1)' },
  { value: 'America/New_York', label: 'Нью-Йорк (EST, UTC-5)' },
  { value: 'America/Los_Angeles', label: 'Лос-Анджелес (PST, UTC-8)' },
  { value: 'Asia/Tokyo', label: 'Токио (JST, UTC+9)' },
  { value: 'Asia/Shanghai', label: 'Шанхай (CST, UTC+8)' },
]

const SetupWizardPage = () => {
  const [currentStep, setCurrentStep] = useState(null)
  const [stepData, setStepData] = useState({})
  const [testingConnection, setTestingConnection] = useState(null)
  const [adminEmail, setAdminEmail] = useState('') // Сохраняем email из шага security
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Получаем статус мастера настройки
  const { data: status, isLoading: statusLoading } = useQuery({
    queryKey: ['setup-wizard', 'status'],
    queryFn: async () => {
      const response = await api.get('/setup-wizard/status')
      return response.data
    },
  })

  // Получаем список шагов (всегда загружаем, чтобы можно было отобразить мастер даже после завершения)
  const { data: stepsData, isLoading: stepsLoading } = useQuery({
    queryKey: ['setup-wizard', 'steps'],
    queryFn: async () => {
      const response = await api.get('/setup-wizard/steps')
      return response.data
    },
    enabled: !statusLoading, // Загружаем всегда, когда статус загружен
  })

  // Мутация для завершения шага
  const completeStepMutation = useMutation({
    mutationFn: async ({ stepId, data }) => {
      const response = await api.post(`/setup-wizard/step/${stepId}/complete`, data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['setup-wizard'])
    },
  })

  // Мутация для тестирования Telegram
  const testTelegramMutation = useMutation({
    mutationFn: async (token) => {
      // Отправляем токен как query параметр
      const response = await api.post(`/setup-wizard/test/telegram?token=${encodeURIComponent(token)}`)
      return response.data
    },
  })

  // Мутация для тестирования MikroTik
  const testMikrotikMutation = useMutation({
    mutationFn: async (testData) => {
      const response = await api.post('/setup-wizard/test/mikrotik', testData)
      return response.data
    },
  })

  // Мутация для завершения мастера
  const completeWizardMutation = useMutation({
    mutationFn: async () => {
      const response = await api.post('/setup-wizard/complete')
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['setup-wizard'])
      navigate('/')
    },
  })

  useEffect(() => {
    // Определяем текущий шаг на основе статуса и stepsData
    if (!status) return // Ждем загрузки статуса
    
    // Если currentStep уже установлен и он соответствует статусу, не меняем его
    if (currentStep && status.current_step === currentStep) {
      return
    }
    
    // Устанавливаем шаг на основе статуса
    if (status.current_step) {
      setCurrentStep(status.current_step)
      return
    }
    
    // Если статус не содержит current_step, используем первый доступный шаг
    if (stepsData?.steps?.[0]) {
      const firstStep = stepsData.steps.find(s => s.id === 'welcome') || stepsData.steps[0]
      if (currentStep !== firstStep.id) {
        setCurrentStep(firstStep.id)
      }
    } else if (!currentStep) {
      // Если stepsData еще не загружен, устанавливаем welcome как дефолт
      setCurrentStep('welcome')
    }
  }, [status, stepsData]) // Не включаем currentStep в зависимости, чтобы избежать циклов

  const handleStepComplete = async (stepId) => {
    try {
      // Сохраняем email администратора из шага security
      if (stepId === 'security' && stepData.admin_email) {
        setAdminEmail(stepData.admin_email)
      }
      
      await completeStepMutation.mutateAsync({ stepId, data: stepData })
      
      // Переходим к следующему шагу
      const currentIndex = stepsData?.steps.findIndex(s => s.id === stepId) || -1
      if (currentIndex >= 0 && currentIndex < stepsData.steps.length - 1) {
        const nextStep = stepsData.steps[currentIndex + 1].id
        setCurrentStep(nextStep)
        
        // Если переходим на notifications и есть сохраненный email, подставляем его
        if (nextStep === 'notifications' && adminEmail) {
          setStepData({ notification_email: adminEmail, notification_method: 'email' })
        } else if (nextStep !== 'notifications') {
          setStepData({})
        }
      }
    } catch (error) {
      alert(`Ошибка: ${error.response?.data?.detail || error.message}`)
    }
  }

  const handleTestTelegram = async () => {
    if (!stepData.telegram_bot_token) {
      alert('Введите токен Telegram бота')
      return
    }
    
    setTestingConnection('telegram')
    try {
      const result = await testTelegramMutation.mutateAsync(stepData.telegram_bot_token)
      if (result.success) {
        alert('✓ Подключение к Telegram успешно!')
      } else {
        alert(`✗ Ошибка: ${result.message}`)
      }
    } catch (error) {
      alert(`Ошибка: ${error.response?.data?.detail || error.message}`)
    } finally {
      setTestingConnection(null)
    }
  }

  const renderStepContent = () => {
    // Если шаги еще загружаются, показываем загрузку
    if (stepsLoading) {
      return <div className="loading">Загрузка шагов мастера...</div>
    }
    
    // Если currentStep не установлен, но есть stepsData, используем первый шаг
    if (!currentStep) {
      if (stepsData?.steps?.[0]) {
        const firstStep = stepsData.steps.find(s => s.id === 'welcome') || stepsData.steps[0]
        return renderStepByType(firstStep.id)
      }
      return <div className="loading">Инициализация мастера...</div>
    }
    
    // Если stepsData не загружен, но currentStep есть, пробуем отобразить шаг напрямую
    if (!stepsData) {
      return renderStepByType(currentStep)
    }

    const step = stepsData.steps.find(s => s.id === currentStep)
    if (!step) {
      // Если шаг не найден в списке, пробуем отобразить по типу
      return renderStepByType(currentStep)
    }
    
    return renderStepByType(step.id)
  }
  
  const renderStepByType = (stepId) => {
    if (!stepId) return null

    switch (stepId) {
      case 'welcome':
        return (
          <div className="wizard-step-content">
            <h3>Добро пожаловать в мастер настройки!</h3>
            <p>Этот мастер поможет вам настроить систему MikroTik 2FA VPN.</p>
            <p>Процесс займет несколько минут и включает настройку:</p>
            <ul>
              <li>Основной информации и языка</li>
              <li>Безопасности и первого администратора</li>
              <li>Telegram бота</li>
              <li>Подключения к MikroTik роутеру</li>
              <li>Уведомлений и дополнительных настроек</li>
            </ul>
            <button
              className="action-btn action-btn-success"
              onClick={() => setCurrentStep('basic_info')}
            >
              Начать настройку
            </button>
          </div>
        )

      case 'basic_info':
        return (
          <div className="wizard-step-content">
            <h3>Основная информация</h3>
            <div className="wizard-form">
              <div className="form-group">
                <label htmlFor="app_name">Название системы</label>
                <input
                  id="app_name"
                  type="text"
                  value={stepData.app_name || 'MikroTik 2FA VPN System'}
                  onChange={(e) => setStepData({ ...stepData, app_name: e.target.value })}
                  placeholder="MikroTik 2FA VPN System"
                />
              </div>
              <div className="form-group">
                <label htmlFor="language">Язык интерфейса</label>
                <select
                  id="language"
                  value={stepData.language || 'ru'}
                  onChange={(e) => setStepData({ ...stepData, language: e.target.value })}
                >
                  <option value="ru">Русский</option>
                  <option value="en">English</option>
                </select>
              </div>
              <div className="form-group">
                <label htmlFor="timezone">Часовой пояс *</label>
                <select
                  id="timezone"
                  value={stepData.timezone || 'UTC'}
                  onChange={(e) => setStepData({ ...stepData, timezone: e.target.value })}
                  required
                >
                  {TIMEZONES.map(tz => (
                    <option key={tz.value} value={tz.value}>{tz.label}</option>
                  ))}
                </select>
                <small>Выберите часовой пояс для системы</small>
              </div>
            </div>
            <div className="wizard-navigation">
              <button
                className="action-btn action-btn-success"
                onClick={() => handleStepComplete('basic_info')}
                disabled={completeStepMutation.isPending || !stepData.timezone}
              >
                {completeStepMutation.isPending ? 'Сохранение...' : 'Далее'}
              </button>
            </div>
          </div>
        )

      case 'security':
        return (
          <div className="wizard-step-content">
            <h3>Безопасность и первый администратор</h3>
            <div className="wizard-form">
              <div className="form-group">
                <label htmlFor="admin_username">Имя пользователя администратора *</label>
                <input
                  id="admin_username"
                  type="text"
                  value={stepData.admin_username || ''}
                  onChange={(e) => setStepData({ ...stepData, admin_username: e.target.value })}
                  placeholder="admin"
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="admin_email">Email администратора *</label>
                <input
                  id="admin_email"
                  type="email"
                  value={stepData.admin_email || ''}
                  onChange={(e) => setStepData({ ...stepData, admin_email: e.target.value })}
                  placeholder="admin@example.com"
                  required
                />
                <small>Этот email будет использоваться для уведомлений по умолчанию</small>
              </div>
              <div className="form-group">
                <label htmlFor="admin_password">Пароль администратора *</label>
                <input
                  id="admin_password"
                  type="password"
                  value={stepData.admin_password || ''}
                  onChange={(e) => setStepData({ ...stepData, admin_password: e.target.value })}
                  placeholder="Введите надежный пароль"
                  required
                />
                <small>Минимум 8 символов, рекомендуется использовать буквы, цифры и спецсимволы</small>
              </div>
              <div className="form-group">
                <label htmlFor="admin_full_name">Полное имя администратора</label>
                <input
                  id="admin_full_name"
                  type="text"
                  value={stepData.admin_full_name || ''}
                  onChange={(e) => setStepData({ ...stepData, admin_full_name: e.target.value })}
                  placeholder="System Administrator"
                />
              </div>
            </div>
            <div className="wizard-navigation">
              <button
                className="action-btn"
                onClick={() => setCurrentStep('basic_info')}
              >
                Назад
              </button>
              <button
                className="action-btn action-btn-success"
                onClick={() => handleStepComplete('security')}
                disabled={completeStepMutation.isPending || !stepData.admin_username || !stepData.admin_email || !stepData.admin_password}
              >
                {completeStepMutation.isPending ? 'Сохранение...' : 'Далее'}
              </button>
            </div>
          </div>
        )

      case 'telegram_bot':
        return (
          <div className="wizard-step-content">
            <h3>Настройка Telegram бота</h3>
            <div className="wizard-help">
              <p><strong>Инструкция:</strong></p>
              <ol>
                <li>Откройте Telegram и найдите бота <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer">@BotFather</a></li>
                <li>Отправьте команду <code>/newbot</code></li>
                <li>Следуйте инструкциям и получите токен бота</li>
                <li>Вставьте токен в поле ниже</li>
                <li>Нажмите "Тестировать подключение" для проверки</li>
              </ol>
            </div>
            <div className="wizard-form">
              <div className="form-group">
                <label htmlFor="telegram_bot_token">Telegram Bot Token *</label>
                <input
                  id="telegram_bot_token"
                  type="password"
                  value={stepData.telegram_bot_token || ''}
                  onChange={(e) => setStepData({ ...stepData, telegram_bot_token: e.target.value })}
                  placeholder="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
                  required
                />
                <small>Токен выдается @BotFather после создания бота</small>
              </div>
              <div className="form-group">
                <label htmlFor="telegram_bot_name">Имя бота (опционально)</label>
                <input
                  id="telegram_bot_name"
                  type="text"
                  value={stepData.telegram_bot_name || ''}
                  onChange={(e) => setStepData({ ...stepData, telegram_bot_name: e.target.value })}
                  placeholder="My VPN Bot"
                />
              </div>
            </div>
            <div className="wizard-actions">
              <button
                className="action-btn"
                onClick={handleTestTelegram}
                disabled={testingConnection === 'telegram' || !stepData.telegram_bot_token}
              >
                {testingConnection === 'telegram' ? 'Тестирование...' : 'Тестировать подключение'}
              </button>
              {testTelegramMutation.data && (
                <div className={testTelegramMutation.data.success ? 'test-success' : 'test-error'}>
                  {testTelegramMutation.data.message}
                </div>
              )}
            </div>
            <div className="wizard-navigation">
              <button
                className="action-btn"
                onClick={() => setCurrentStep('security')}
              >
                Назад
              </button>
              <button
                className="action-btn action-btn-success"
                onClick={() => handleStepComplete('telegram_bot')}
                disabled={completeStepMutation.isPending || !stepData.telegram_bot_token}
              >
                {completeStepMutation.isPending ? 'Сохранение...' : 'Далее'}
              </button>
            </div>
          </div>
        )

      case 'mikrotik':
        return (
          <div className="wizard-step-content">
            <h3>Настройка MikroTik роутера</h3>
            <div className="wizard-help">
              <p>Укажите параметры подключения к вашему MikroTik роутеру.</p>
              <p>Эти настройки можно изменить позже через раздел "MikroTik" в веб-интерфейсе.</p>
            </div>
            <div className="wizard-form">
              <div className="form-group">
                <label htmlFor="mikrotik_host">Хост/IP адрес *</label>
                <input
                  id="mikrotik_host"
                  type="text"
                  value={stepData.mikrotik_host || ''}
                  onChange={(e) => setStepData({ ...stepData, mikrotik_host: e.target.value })}
                  placeholder="192.168.1.1"
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="connection_type">Тип подключения *</label>
                <select
                  id="connection_type"
                  value={stepData.connection_type || 'ssh_password'}
                  onChange={(e) => {
                    const connType = e.target.value
                    const defaultPort = connType === 'rest_api' ? 8728 : 22
                    setStepData({ 
                      ...stepData, 
                      connection_type: connType,
                      // Автоматически меняем порт в зависимости от типа подключения
                      mikrotik_port: defaultPort
                    })
                  }}
                  required
                >
                  <option value="ssh_password">SSH (пароль) - порт 22</option>
                  <option value="ssh_key">SSH (ключ) - порт 22</option>
                  <option value="rest_api">REST API - порт 8728</option>
                </select>
                <small>Выберите способ подключения к MikroTik роутеру</small>
              </div>
              <div className="form-group">
                <label htmlFor="mikrotik_port">Порт *</label>
                <input
                  id="mikrotik_port"
                  type="number"
                  value={stepData.mikrotik_port || (stepData.connection_type === 'rest_api' ? 8728 : 22) || 22}
                  onChange={(e) => {
                    const port = parseInt(e.target.value)
                    setStepData({ ...stepData, mikrotik_port: port || (stepData.connection_type === 'rest_api' ? 8728 : 22) })
                  }}
                  placeholder={stepData.connection_type === 'rest_api' ? '8728' : '22'}
                  required
                />
                <small>Порт по умолчанию: <strong>22</strong> для SSH, <strong>8728</strong> для REST API</small>
              </div>
              <div className="form-group">
                <label htmlFor="mikrotik_username">Имя пользователя *</label>
                <input
                  id="mikrotik_username"
                  type="text"
                  value={stepData.mikrotik_username || ''}
                  onChange={(e) => setStepData({ ...stepData, mikrotik_username: e.target.value })}
                  placeholder="admin"
                  required
                />
              </div>
              <div className="form-group">
                <label htmlFor="mikrotik_password">Пароль</label>
                <input
                  id="mikrotik_password"
                  type="password"
                  value={stepData.mikrotik_password || ''}
                  onChange={(e) => setStepData({ ...stepData, mikrotik_password: e.target.value })}
                  placeholder="Пароль администратора MikroTik"
                />
                <small>Обязателен для SSH (пароль) и REST API</small>
              </div>
            </div>
            <div className="wizard-actions">
              <button
                className="action-btn action-btn-secondary"
                onClick={async () => {
                    if (!stepData.mikrotik_host || !stepData.mikrotik_username) {
                      alert('Заполните обязательные поля (Хост и Имя пользователя)')
                      return
                    }
                    
                    setTestingConnection('mikrotik')
                    try {
                      // Тестируем подключение с временными данными из формы
                      const connType = stepData.connection_type || 'ssh_password'
                      const defaultPort = connType === 'rest_api' ? 8728 : 22
                      const testData = {
                        host: stepData.mikrotik_host,
                        port: stepData.mikrotik_port || defaultPort,
                        username: stepData.mikrotik_username,
                        password: stepData.mikrotik_password || '',
                        connection_type: connType,
                      }
                      
                      const result = await testMikrotikMutation.mutateAsync(testData)
                      if (result.success) {
                        alert('✓ Подключение к MikroTik успешно!')
                      } else {
                        alert(`✗ Ошибка: ${result.message}`)
                      }
                    } catch (error) {
                      alert(`Ошибка: ${error.response?.data?.detail || error.response?.data?.message || error.message}`)
                    } finally {
                      setTestingConnection(null)
                    }
                  }}
                  disabled={testingConnection === 'mikrotik' || !stepData.mikrotik_host || !stepData.mikrotik_username}
                >
                  {testingConnection === 'mikrotik' ? 'Тестирование...' : 'Тестировать подключение'}
                </button>
                {testMikrotikMutation.data && (
                  <div className={testMikrotikMutation.data.success ? 'test-success' : 'test-error'}>
                    {testMikrotikMutation.data.message}
                  </div>
                )}
            </div>
            <div className="wizard-navigation">
              <button
                className="action-btn"
                onClick={() => setCurrentStep('telegram_bot')}
              >
                Назад
              </button>
              <button
                className="action-btn action-btn-success"
                onClick={() => handleStepComplete('mikrotik')}
                disabled={completeStepMutation.isPending || !stepData.mikrotik_host || !stepData.mikrotik_username}
              >
                {completeStepMutation.isPending ? 'Сохранение...' : 'Далее'}
              </button>
            </div>
          </div>
        )

      case 'notifications':
        return (
          <div className="wizard-step-content">
            <h3>Настройка уведомлений</h3>
            <div className="wizard-help">
              <p>Выберите способ получения уведомлений администратором о событиях системы.</p>
            </div>
            <div className="wizard-form">
              <div className="form-group">
                <label htmlFor="notification_method">Способ уведомлений *</label>
                <select
                  id="notification_method"
                  value={stepData.notification_method || (adminEmail ? 'email' : 'none')}
                  onChange={(e) => {
                    const method = e.target.value
                    setStepData({ 
                      ...stepData, 
                      notification_method: method,
                      // Если выбрали email, подставляем email администратора если не указан другой
                      notification_email: (method === 'email' || method === 'both') && !stepData.notification_email ? adminEmail : stepData.notification_email
                    })
                  }}
                  required
                >
                  <option value="email">Email администратора ({adminEmail || 'будет использован email с шага 2'})</option>
                  <option value="telegram_bot">Telegram бот (тот же, что настроен выше)</option>
                  <option value="telegram_other">Другой Telegram бот/чат</option>
                  <option value="both">Email и Telegram (оба)</option>
                  <option value="none">Не отправлять уведомления</option>
                </select>
              </div>
              
              {(stepData.notification_method === 'email' || stepData.notification_method === 'both') && (
                <div className="form-group">
                  <label htmlFor="notification_email">Email для уведомлений</label>
                  <input
                    id="notification_email"
                    type="email"
                    value={stepData.notification_email !== undefined && stepData.notification_email !== null ? stepData.notification_email : (adminEmail || '')}
                    onChange={(e) => setStepData({ ...stepData, notification_email: e.target.value })}
                    placeholder={adminEmail || "admin@example.com"}
                  />
                  {adminEmail && (
                    <small>По умолчанию будет использован email администратора: <strong>{adminEmail}</strong>. Можете указать другой email.</small>
                  )}
                  {!adminEmail && (
                    <small>Укажите email для получения уведомлений</small>
                  )}
                </div>
              )}
              
              {(stepData.notification_method === 'telegram_other' || stepData.notification_method === 'both') && (
                <>
                  <div className="form-group">
                    <label htmlFor="telegram_other_token">Токен другого Telegram бота (опционально)</label>
                    <input
                      id="telegram_other_token"
                      type="password"
                      value={stepData.telegram_other_token || ''}
                      onChange={(e) => setStepData({ ...stepData, telegram_other_token: e.target.value })}
                      placeholder="Токен от @BotFather"
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="telegram_other_chat_id">Chat ID для уведомлений</label>
                    <input
                      id="telegram_other_chat_id"
                      type="text"
                      value={stepData.telegram_other_chat_id || ''}
                      onChange={(e) => setStepData({ ...stepData, telegram_other_chat_id: e.target.value })}
                      placeholder="Например: -1001234567890"
                    />
                    <small>Chat ID можно получить у бота @userinfobot</small>
                  </div>
                </>
              )}
            </div>
            <div className="wizard-navigation">
              <button
                className="action-btn"
                onClick={() => setCurrentStep('mikrotik')}
              >
                Назад
              </button>
              <button
                className="action-btn"
                onClick={() => {
                  setStepData({ notification_method: 'none' })
                  handleStepComplete('notifications')
                }}
                disabled={completeStepMutation.isPending}
              >
                Пропустить
              </button>
              <button
                className="action-btn action-btn-success"
                onClick={() => handleStepComplete('notifications')}
                disabled={completeStepMutation.isPending || !stepData.notification_method}
              >
                {completeStepMutation.isPending ? 'Сохранение...' : 'Далее'}
              </button>
            </div>
          </div>
        )

      case 'additional':
        return (
          <div className="wizard-step-content">
            <h3>Дополнительные настройки</h3>
            <div className="wizard-help">
              <p>Настройте дополнительные параметры системы (все опционально).</p>
            </div>
            <div className="wizard-form">
              <div className="form-group">
                <label htmlFor="domain_name">Доменное имя сервиса</label>
                <input
                  id="domain_name"
                  type="text"
                  value={stepData.domain_name || ''}
                  onChange={(e) => setStepData({ ...stepData, domain_name: e.target.value })}
                  placeholder="vpn.example.com"
                />
                <small>Доменное имя для доступа к веб-интерфейсу (если настроено)</small>
              </div>
              <div className="form-group">
                <label htmlFor="backup_enabled">Включить автоматическое резервное копирование</label>
                <select
                  id="backup_enabled"
                  value={stepData.backup_enabled !== undefined ? String(stepData.backup_enabled) : 'true'}
                  onChange={(e) => setStepData({ ...stepData, backup_enabled: e.target.value === 'true' })}
                >
                  <option value="true">Да</option>
                  <option value="false">Нет</option>
                </select>
              </div>
              {stepData.backup_enabled !== false && (
                <div className="form-group">
                  <label htmlFor="backup_interval_hours">Интервал резервного копирования (часы)</label>
                  <input
                    id="backup_interval_hours"
                    type="number"
                    value={stepData.backup_interval_hours || '24'}
                    onChange={(e) => setStepData({ ...stepData, backup_interval_hours: parseInt(e.target.value) || 24 })}
                    min="1"
                    max="168"
                  />
                  <small>Как часто создавать резервные копии (1-168 часов)</small>
                </div>
              )}
              <div className="form-group">
                <label htmlFor="log_level">Уровень логирования</label>
                <select
                  id="log_level"
                  value={stepData.log_level || 'INFO'}
                  onChange={(e) => setStepData({ ...stepData, log_level: e.target.value })}
                >
                  <option value="DEBUG">DEBUG (детальная отладочная информация)</option>
                  <option value="INFO">INFO (общая информация)</option>
                  <option value="WARNING">WARNING (предупреждения)</option>
                  <option value="ERROR">ERROR (только ошибки)</option>
                </select>
              </div>
            </div>
            <div className="wizard-navigation">
              <button
                className="action-btn"
                onClick={() => {
                  const prevStep = stepsData?.steps.find(s => s.id === 'notifications')?.id || 'notifications'
                  setCurrentStep(prevStep)
                }}
              >
                Назад
              </button>
              <button
                className="action-btn action-btn-success"
                onClick={() => handleStepComplete('additional')}
                disabled={completeStepMutation.isPending}
              >
                {completeStepMutation.isPending ? 'Сохранение...' : 'Далее'}
              </button>
            </div>
          </div>
        )

      case 'review':
        const completedSteps = status?.completed_steps || []
        return (
          <div className="wizard-step-content">
            <h3>Проверка и завершение</h3>
            <p>Проверьте все настройки перед завершением мастера настройки.</p>
            <div className="review-summary">
              <h4>Сводка настроек:</h4>
              <ul>
                {completedSteps.includes('basic_info') ? (
                  <li>✓ Основная информация настроена</li>
                ) : (
                  <li style={{ color: 'var(--danger-color)' }}>✗ Основная информация не настроена</li>
                )}
                {completedSteps.includes('security') ? (
                  <li>✓ Безопасность настроена</li>
                ) : (
                  <li style={{ color: 'var(--danger-color)' }}>✗ Безопасность не настроена (обязательно!)</li>
                )}
                {completedSteps.includes('telegram_bot') ? (
                  <li>✓ Telegram бот настроен</li>
                ) : (
                  <li style={{ color: 'var(--danger-color)' }}>✗ Telegram бот не настроен (обязательно!)</li>
                )}
                {completedSteps.includes('mikrotik') ? (
                  <li>✓ MikroTik роутер настроен</li>
                ) : (
                  <li style={{ color: 'var(--danger-color)' }}>✗ MikroTik роутер не настроен (обязательно!)</li>
                )}
                {completedSteps.includes('notifications') ? (
                  <li>✓ Уведомления настроены</li>
                ) : (
                  <li style={{ color: 'var(--text-secondary)' }}>○ Уведомления не настроены (опционально)</li>
                )}
                {completedSteps.includes('additional') ? (
                  <li>✓ Дополнительные настройки выполнены</li>
                ) : (
                  <li style={{ color: 'var(--text-secondary)' }}>○ Дополнительные настройки не выполнены (опционально)</li>
                )}
              </ul>
              {status?.is_completed && (
                <div style={{ marginTop: '1rem', padding: '1rem', background: 'var(--success-light)', borderRadius: 'var(--radius-md)', border: '1px solid var(--success-color)' }}>
                  <strong>ℹ️ Мастер настройки был завершен ранее.</strong> Вы можете завершить его повторно, чтобы обновить настройки, или перезапустить для полной переконфигурации.
                </div>
              )}
            </div>
            <div className="wizard-navigation">
              <button
                className="action-btn"
                onClick={() => {
                  // Возвращаемся к последнему опциональному шагу, или к mikrotik если он последний обязательный
                  const completedSteps = status?.completed_steps || []
                  const prevStep = completedSteps.includes('additional') ? 'additional' 
                    : completedSteps.includes('notifications') ? 'notifications'
                    : 'mikrotik'
                  setCurrentStep(prevStep)
                }}
              >
                Назад
              </button>
              <button
                className="action-btn action-btn-secondary"
                onClick={async () => {
                  if (window.confirm('Вы уверены, что хотите перезапустить мастер настройки? Все шаги будут сброшены, но сохраненные данные не будут удалены.')) {
                    try {
                      await api.post('/setup-wizard/restart')
                      queryClient.invalidateQueries(['setup-wizard'])
                      setCurrentStep('welcome')
                      setStepData({})
                      alert('✓ Мастер настройки перезапущен. Вы можете пройти настройку заново.')
                    } catch (error) {
                      alert(`Ошибка перезапуска: ${error.response?.data?.detail || error.message}`)
                    }
                  }
                }}
              >
                Перезапустить мастер
              </button>
              <button
                className="action-btn action-btn-success"
                onClick={async () => {
                  try {
                    const result = await completeWizardMutation.mutateAsync()
                    
                    // Проверяем результат
                    if (result && result.message) {
                      // Проверяем успешность через статус
                      const statusResult = result.status || await api.get('/setup-wizard/status').then(r => r.data)
                      if (statusResult?.is_completed) {
                        alert('✓ Мастер настройки успешно завершен! Система готова к работе.')
                        // Небольшая задержка перед редиректом
                        setTimeout(() => {
                          navigate('/')
                        }, 1500)
                      } else {
                        // Показываем, какие шаги нужно завершить
                        const completedSteps = statusResult?.completed_steps || []
                        const missingSteps = []
                        if (!completedSteps.includes('basic_info')) missingSteps.push('Основная информация')
                        if (!completedSteps.includes('security')) missingSteps.push('Безопасность')
                        if (!completedSteps.includes('telegram_bot')) missingSteps.push('Telegram бот')
                        if (!completedSteps.includes('mikrotik')) missingSteps.push('MikroTik роутер')
                        
                        alert(`⚠ Не все обязательные шаги выполнены. Пожалуйста, завершите: ${missingSteps.join(', ')}`)
                      }
                    } else {
                      alert('⚠ Не удалось завершить мастер настройки. Проверьте, что все обязательные шаги выполнены.')
                    }
                  } catch (error) {
                    const errorDetail = error.response?.data?.detail || error.response?.data?.message || error.message || 'Неизвестная ошибка'
                    
                    // Если ошибка 400 - это валидационная ошибка, показываем понятное сообщение
                    if (error.response?.status === 400) {
                      alert(`⚠ ${errorDetail}\n\nПожалуйста, вернитесь к незавершенным шагам и завершите их перед финальным завершением мастера.`)
                    } else {
                      alert(`❌ Ошибка завершения мастера настройки: ${errorDetail}`)
                    }
                  }
                }}
                disabled={completeWizardMutation.isPending}
              >
                {completeWizardMutation.isPending ? 'Завершение...' : (status?.is_completed ? 'Перезавершить настройку' : 'Завершить настройку')}
              </button>
            </div>
          </div>
        )

      default:
        return <div>Неизвестный шаг: {stepId}</div>
    }
  }

  if (statusLoading) {
    return <div className="loading">Загрузка статуса мастера настройки...</div>
  }

  // Если мастер завершен, но пользователь явно открыл страницу мастера, разрешаем работу
  // Не блокируем доступ, позволяем перезапустить или завершить повторно
  // Это позволяет обновлять настройки даже после первого завершения

  const steps = stepsData?.steps || []
  const totalSteps = steps.length || status?.total_steps || 0
  const currentIndex =
    steps.length && currentStep ? steps.findIndex((s) => s.id === currentStep) : -1
  const currentStepNumber = currentIndex >= 0 ? currentIndex + 1 : (status?.completed_steps?.length || 0)
  const progress = totalSteps ? (Math.min(currentStepNumber, totalSteps) / totalSteps) * 100 : 0

  return (
    <div className="setup-wizard-page">
      <div className="wizard-container">
        <div className="wizard-header">
          <h2>Мастер настройки системы</h2>
          <div className="wizard-progress">
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${progress}%` }}></div>
            </div>
            <span>
              Шаг {Math.min(currentStepNumber || 0, totalSteps || 0)} из {totalSteps || 0}
            </span>
          </div>
        </div>

        <div className="wizard-steps-list">
          {stepsData?.steps ? (
            stepsData.steps.map((step, index) => (
              <div
                key={step.id}
              className={`wizard-step-indicator ${
                (status?.completed_steps || []).includes(step.id) ? 'completed' : ''
              } ${currentStep === step.id ? 'active' : ''}`}
              >
                <span className="step-number">{index + 1}</span>
                <span className="step-name">{step.name}</span>
              </div>
            ))
          ) : (
            <div className="loading">Загрузка шагов...</div>
          )}
        </div>

        <div className="wizard-content">
          {renderStepContent()}
        </div>
      </div>
    </div>
  )
}

export default SetupWizardPage
