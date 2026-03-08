import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import { useAuthStore } from '@/store/authStore'
import ErrorBoundary from '@/components/ErrorBoundary'
import LoadingSpinner from '@/components/LoadingSpinner'
import DashboardLayout from '@/components/layout/DashboardLayout'

const LandingPage = lazy(() => import('./pages/LandingPage'))
const LoginPage = lazy(() => import('./pages/LoginPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const ProjectsPage = lazy(() => import('./pages/ProjectsPage'))
const NewProjectPage = lazy(() => import('./pages/NewProjectPage'))
const ProjectDetailPage = lazy(() => import('./pages/ProjectDetailPage'))
const ProjectStorePage = lazy(() => import('./pages/ProjectStorePage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const UsagePage = lazy(() => import('./pages/UsagePage'))
const AuditPage = lazy(() => import('./pages/AuditPage'))
const OnboardingPage = lazy(() => import('./pages/OnboardingPage'))
const TermsPage = lazy(() => import('./pages/TermsPage'))
const PrivacyPage = lazy(() => import('./pages/PrivacyPage'))
const SLAPage = lazy(() => import('./pages/SLAPage'))
const StatusPage = lazy(() => import('./pages/StatusPage'))
const SupportPage = lazy(() => import('./pages/SupportPage'))
const GitHubCallbackPage = lazy(() => import('./pages/GitHubCallbackPage'))
const OTAPage = lazy(() => import('./pages/OTAPage'))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'))

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
    <ErrorBoundary>
      <BrowserRouter>
        <Toaster
          position="top-right"
          toastOptions={{
            className: 'bg-gray-900 text-white border border-gray-800',
          }}
        />
        <Suspense fallback={<LoadingSpinner />}>
          <Routes>
            <Route path="/" element={<PublicHome />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/terms" element={<TermsPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/sla" element={<SLAPage />} />
            <Route path="/status" element={<StatusPage />} />
            <Route path="/support" element={<SupportPage />} />
            <Route path="/auth/github/callback" element={<GitHubCallbackPage />} />
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
              <Route path="projects/:id/ota" element={<OTAPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="usage" element={<UsagePage />} />
              <Route path="audit" element={<AuditPage />} />
              <Route path="status" element={<StatusPage />} />
            </Route>
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
