import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import api from './services/api'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import UsersPage from './pages/UsersPage'
import VPNSessionsPage from './pages/VPNSessionsPage'
import SettingsPage from './pages/SettingsPage'
import MikroTikPage from './pages/MikroTikPage'
import AuditLogsPage from './pages/AuditLogsPage'
import StatsPage from './pages/StatsPage'
import SetupWizardPage from './pages/SetupWizardPage'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'

function App() {
  const { isAuthenticated } = useAuthStore()
  const location = useLocation()

  // Проверяем статус мастера настройки только для авторизованных пользователей
  const { data: wizardStatus } = useQuery({
    queryKey: ['setup-wizard', 'status'],
    queryFn: async () => {
      const response = await api.get('/setup-wizard/status')
      return response.data
    },
    enabled: isAuthenticated && location.pathname !== '/login',
    retry: false,
  })

  // Автоматически перенаправляем на мастер настройки, если настройка не завершена
  useEffect(() => {
    if (
      isAuthenticated &&
      wizardStatus &&
      !wizardStatus.is_completed &&
      location.pathname !== '/setup-wizard' &&
      location.pathname !== '/login'
    ) {
      // Не делаем автоматический редирект, чтобы не мешать работе
      // Мастер можно открыть через меню настроек
    }
  }, [isAuthenticated, wizardStatus, location.pathname])

  return (
    <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/" /> : <LoginPage />} />
      <Route path="/setup-wizard" element={<SetupWizardPage />} />
      
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/users" element={<UsersPage />} />
        {/* legacy: заявки теперь встроены в /users */}
        <Route path="/registration-requests" element={<Navigate to="/users" />} />
        <Route path="/vpn-sessions" element={<VPNSessionsPage />} />
        <Route path="/mikrotik" element={<MikroTikPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/audit-logs" element={<AuditLogsPage />} />
        <Route path="/stats" element={<StatsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  )
}

export default App
