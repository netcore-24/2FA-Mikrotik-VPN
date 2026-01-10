import { create } from 'zustand'
import api from '../services/api'

// Функция для работы с localStorage
const loadFromStorage = (key) => {
  try {
    const item = localStorage.getItem(key)
    return item ? JSON.parse(item) : null
  } catch {
    return null
  }
}

const saveToStorage = (key, value) => {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Игнорируем ошибки
  }
}

const useAuthStore = create((set, get) => {
  // Загружаем начальное состояние из localStorage
  const saved = loadFromStorage('auth-storage')
  const initialState = saved?.state || {
    token: null,
    refreshToken: null,
    admin: null,
    isAuthenticated: false,
  }

  // Инициализируем API с сохраненным токеном
  if (initialState.token) {
    api.defaults.headers.common['Authorization'] = `Bearer ${initialState.token}`
  }

  return {
    ...initialState,

    login: async (username, password) => {
      try {
        const response = await api.post('/auth/login', {
          username,
          password,
        })
        const { access_token, refresh_token, admin } = response.data
        
        const newState = {
          token: access_token,
          refreshToken: refresh_token,
          admin,
          isAuthenticated: true,
        }
        
        set(newState)
        saveToStorage('auth-storage', { state: newState })

        // Устанавливаем токен в заголовки API
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
        
        return { success: true }
      } catch (error) {
        return {
          success: false,
          error: error.response?.data?.detail || 'Ошибка входа',
        }
      }
    },

    logout: () => {
      const newState = {
        token: null,
        refreshToken: null,
        admin: null,
        isAuthenticated: false,
      }
      set(newState)
      saveToStorage('auth-storage', { state: newState })
      delete api.defaults.headers.common['Authorization']
    },

    refreshAuth: async () => {
      const { refreshToken } = get()
      if (!refreshToken) return false

      try {
        const response = await api.post('/auth/refresh', {
          refresh_token: refreshToken,
        })
        const { access_token } = response.data
        
        const newState = {
          ...get(),
          token: access_token,
          isAuthenticated: true,
        }
        
        set(newState)
        saveToStorage('auth-storage', { state: newState })

        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
        return true
      } catch (error) {
        get().logout()
        return false
      }
    },

    initialize: () => {
      const { token } = get()
      if (token) {
        api.defaults.headers.common['Authorization'] = `Bearer ${token}`
      }
    },
  }
})

// Инициализируем при загрузке
useAuthStore.getState().initialize()

export { useAuthStore }

      token: null,
      refreshToken: null,
      admin: null,
      isAuthenticated: false,

      login: async (username, password) => {
        try {
          const response = await api.post('/auth/login', {
            username,
            password,
          })
          const { access_token, refresh_token, admin } = response.data
          
          set({
            token: access_token,
            refreshToken: refresh_token,
            admin,
            isAuthenticated: true,
          })

          // Устанавливаем токен в заголовки API
          api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
          
          return { success: true }
        } catch (error) {
          return {
            success: false,
            error: error.response?.data?.detail || 'Ошибка входа',
          }
        }
      },

      logout: () => {
        set({
          token: null,
          refreshToken: null,
          admin: null,
          isAuthenticated: false,
        })
        delete api.defaults.headers.common['Authorization']
      },

      refreshAuth: async () => {
        const { refreshToken } = get()
        if (!refreshToken) return false

        try {
          const response = await api.post('/auth/refresh', {
            refresh_token: refreshToken,
          })
          const { access_token } = response.data
          
          set({
            token: access_token,
            isAuthenticated: true,
          })

          api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
          return true
        } catch (error) {
          get().logout()
          return false
        }
      },

      initialize: () => {
        const { token } = get()
        if (token) {
          api.defaults.headers.common['Authorization'] = `Bearer ${token}`
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        refreshToken: state.refreshToken,
        admin: state.admin,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)

// Инициализируем при загрузке
useAuthStore.getState().initialize()

export { useAuthStore }
