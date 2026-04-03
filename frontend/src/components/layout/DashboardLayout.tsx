import { useState, useEffect } from 'react'
import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, FolderGit2, LogOut, Settings, BarChart3, Shield, AlertTriangle, ChevronLeft, ChevronRight } from 'lucide-react'
import logoImg from '@/assets/logo.png'
import { useAuthStore } from '@/store/authStore'
import clsx from 'clsx'
import NotificationDropdown from '../ui/NotificationDropdown'

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', exact: true },
  { to: '/dashboard/projects', icon: FolderGit2, label: 'Projects' },
  { to: '/dashboard/usage', icon: BarChart3, label: 'Usage & Billing' },
  { to: '/dashboard/audit', icon: Shield, label: 'Audit Log' },
  { to: '/dashboard/status', icon: AlertTriangle, label: 'Status' },
  { to: '/dashboard/settings', icon: Settings, label: 'Settings' },
]

const SIDEBAR_KEY = 'apptrack-sidebar-collapsed'

export default function DashboardLayout() {
  const { user, clearAuth } = useAuthStore()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(() => {
    return localStorage.getItem(SIDEBAR_KEY) === 'true'
  })

  useEffect(() => {
    localStorage.setItem(SIDEBAR_KEY, String(collapsed))
  }, [collapsed])

  const handleLogout = () => {
    clearAuth()
    navigate('/login')
  }

  return (
    <div className="flex h-screen bg-gray-950">
      <aside
        className={clsx(
          'flex flex-col bg-gray-900 border-r border-gray-800 transition-all duration-300 ease-in-out relative',
          collapsed ? 'w-16' : 'w-60'
        )}
      >
        {/* Logo */}
        <div className={clsx(
          'flex items-center border-b border-gray-800 h-[62px]',
          collapsed ? 'justify-center px-2' : 'gap-2 px-5'
        )}>
          <img src={logoImg} alt="AppTrack" className="w-7 h-7 flex-shrink-0 object-contain" />
          <span className={clsx(
            'font-bold text-lg tracking-tight transition-all duration-300 overflow-hidden whitespace-nowrap',
            collapsed ? 'w-0 opacity-0' : 'w-auto opacity-100'
          )}>
            AppTrack
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-2 py-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label, exact }) => (
            <NavLink
              key={to}
              to={to}
              end={exact}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                clsx(
                  'flex items-center rounded-lg text-sm font-medium transition-colors relative group',
                  collapsed ? 'justify-center px-0 py-2.5' : 'gap-3 px-3 py-2',
                  isActive
                    ? 'bg-primary-600 text-white'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                )
              }
            >
              <Icon size={16} className="flex-shrink-0" />
              <span className={clsx(
                'transition-all duration-300 overflow-hidden whitespace-nowrap',
                collapsed ? 'w-0 opacity-0' : 'w-auto opacity-100'
              )}>
                {label}
              </span>
              {/* Tooltip on hover when collapsed */}
              {collapsed && (
                <div className="absolute left-full ml-2 px-2 py-1 bg-gray-800 text-white text-xs rounded shadow-lg whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200" style={{ zIndex: 9999 }}>
                  {label}
                </div>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User Profile */}
        <div className="px-2 py-4 border-t border-gray-800">
          <div className={clsx(
            'flex items-center px-2 py-2 mb-1',
            collapsed ? 'justify-center' : 'gap-3'
          )}>
            <div className="w-8 h-8 rounded-full bg-primary-600 flex items-center justify-center text-sm font-semibold flex-shrink-0" title={collapsed ? user?.name : undefined}>
              {user?.name?.[0]?.toUpperCase() ?? 'U'}
            </div>
            <div className={clsx(
              'flex-1 min-w-0 transition-all duration-300 overflow-hidden',
              collapsed ? 'w-0 opacity-0' : 'w-auto opacity-100'
            )}>
              <p className="text-sm font-medium truncate">{user?.name}</p>
              <p className="text-xs text-gray-500 truncate">{user?.email}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            title={collapsed ? 'Logout' : undefined}
            className={clsx(
              'flex items-center w-full rounded-lg text-sm text-gray-400 hover:bg-gray-800 hover:text-white transition-colors group relative',
              collapsed ? 'justify-center px-0 py-2.5' : 'gap-3 px-3 py-2'
            )}
          >
            <LogOut size={16} className="flex-shrink-0" />
            <span className={clsx(
              'transition-all duration-300 overflow-hidden whitespace-nowrap',
              collapsed ? 'w-0 opacity-0' : 'w-auto opacity-100'
            )}>
              Logout
            </span>
            {collapsed && (
              <div className="absolute left-full ml-2 px-2 py-1 bg-gray-800 text-white text-xs rounded shadow-lg whitespace-nowrap opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity duration-200" style={{ zIndex: 9999 }}>
                Logout
              </div>
            )}
          </button>
        </div>

        {/* Collapse Toggle Button */}
        <button
          onClick={() => setCollapsed(c => !c)}
          className="absolute -right-3 top-[72px] w-6 h-6 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center text-gray-400 hover:text-white hover:bg-gray-700 transition-colors shadow-md"
          style={{ zIndex: 50 }}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="flex items-center justify-end px-6 py-3 border-b border-gray-800 bg-gray-900">
          <NotificationDropdown />
        </header>
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
