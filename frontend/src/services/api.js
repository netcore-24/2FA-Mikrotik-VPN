import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Интерсептор для добавления токена авторизации
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth-storage')
    if (token) {
      try {
        const parsed = JSON.parse(token)
        if (parsed.state?.token) {
          config.headers.Authorization = `Bearer ${parsed.state.token}`
        }
      } catch (e) {
        // Игнорируем ошибки парсинга
      }
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Интерсептор для обработки ошибок
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Попытка обновить токен
      const authStorage = localStorage.getItem('auth-storage')
      if (authStorage) {
        try {
          const parsed = JSON.parse(authStorage)
          if (parsed.state?.refreshToken) {
            const response = await axios.post('/api/auth/refresh', {
              refresh_token: parsed.state.refreshToken,
            })
            const { access_token } = response.data
            
            // Обновляем токен в localStorage
            parsed.state.token = access_token
            localStorage.setItem('auth-storage', JSON.stringify(parsed))
            
            // Повторяем запрос с новым токеном
            error.config.headers.Authorization = `Bearer ${access_token}`
            return axios.request(error.config)
          }
        } catch (refreshError) {
          // Если обновление не удалось, редиректим на логин
          localStorage.removeItem('auth-storage')
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

export default api
