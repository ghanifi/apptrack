import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'
import DashboardLayout from '@/components/layout/DashboardLayout'
import LandingPage from '@/pages/LandingPage'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import ProjectsPage from '@/pages/ProjectsPage'
import NewProjectPage from '@/pages/NewProjectPage'
import ProjectDetailPage from '@/pages/ProjectDetailPage'
import ProjectStorePage from '@/pages/ProjectStorePage'
import SettingsPage from '@/pages/SettingsPage'
import UsagePage from '@/pages/UsagePage'
import AuditPage from '@/pages/AuditPage'
import OnboardingPage from '@/pages/OnboardingPage'
import TermsPage from '@/pages/TermsPage'
import PrivacyPage from '@/pages/PrivacyPage'
import SLAPage from '@/pages/SLAPage'
import StatusPage from '@/pages/StatusPage'
import SupportPage from '@/pages/SupportPage'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuthStore()
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

function PublicHome() {
  const { token } = useAuthStore()
  return token ? <Navigate to="/dashboard" replace /> : <LandingPage />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PublicHome />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/terms" element={<TermsPage />} />
        <Route path="/privacy" element={<PrivacyPage />} />
        <Route path="/sla" element={<SLAPage />} />
        <Route path="/status" element={<StatusPage />} />
        <Route path="/support" element={<SupportPage />} />
        <Route
          path="/onboarding"
          element={
            <PrivateRoute>
              <OnboardingPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/dashboard"
          element={
            <PrivateRoute>
              <DashboardLayout />
            </PrivateRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="projects" element={<ProjectsPage />} />
          <Route path="projects/new" element={<NewProjectPage />} />
          <Route path="projects/:id" element={<ProjectDetailPage />} />
          <Route path="projects/:id/store" element={<ProjectStorePage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="usage" element={<UsagePage />} />
          <Route path="audit" element={<AuditPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
