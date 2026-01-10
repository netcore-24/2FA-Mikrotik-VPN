import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import UsersPage from './pages/UsersPage'
import RegistrationRequestsPage from './pages/RegistrationRequestsPage'
import VPNSessionsPage from './pages/VPNSessionsPage'
import SettingsPage from './pages/SettingsPage'
import MikroTikPage from './pages/MikroTikPage'
import AuditLogsPage from './pages/AuditLogsPage'
import StatsPage from './pages/StatsPage'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'

function App() {
  const { isAuthenticated } = useAuthStore()

  return (
    <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/" /> : <LoginPage />} />
      
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="/registration-requests" element={<RegistrationRequestsPage />} />
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
