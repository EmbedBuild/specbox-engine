import { type ReactNode, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Heart, TestTube2, ArrowUpCircle, ClipboardList, Gauge, Menu, X } from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/healing', icon: Heart, label: 'Self-Healing' },
  { to: '/e2e', icon: TestTube2, label: 'E2E Testing' },
  { to: '/upgrades', icon: ArrowUpCircle, label: 'Upgrades' },
  { to: '/spec-driven', icon: ClipboardList, label: 'Spec-Driven' },
]

export default function Layout({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="min-h-screen flex">
      {/* Mobile backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar — hidden on mobile, icon-only on tablet, full on desktop */}
      <aside className={`
        fixed md:sticky top-0 h-screen z-50
        bg-slate-900 border-r border-slate-800 flex flex-col
        transition-transform duration-200 ease-in-out
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
        md:translate-x-0 md:w-16 lg:w-60
        w-60
      `}>
        <div className="p-3 lg:p-5 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
              <Gauge className="w-5 h-5 text-white" />
            </div>
            <div className="lg:block hidden">
              <h1 className="text-sm font-bold text-white leading-tight">La Sala de</h1>
              <h1 className="text-sm font-bold text-blue-400 leading-tight">Maquinas</h1>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-2 lg:p-3 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`
              }
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              <span className="lg:inline hidden">{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="p-3 lg:p-4 border-t border-slate-800">
          <p className="text-xs text-slate-600 lg:block hidden">Dev Engine MCP v2.6.0</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto min-w-0">
        {/* Mobile header */}
        <div className="md:hidden sticky top-0 z-30 bg-slate-950/90 backdrop-blur border-b border-slate-800 px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="p-1.5 rounded-lg hover:bg-slate-800 transition-colors"
          >
            {mobileOpen ? <X className="w-5 h-5 text-slate-300" /> : <Menu className="w-5 h-5 text-slate-300" />}
          </button>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-md bg-blue-600 flex items-center justify-center">
              <Gauge className="w-4 h-4 text-white" />
            </div>
            <span className="text-sm font-bold text-white">Sala de Maquinas</span>
          </div>
        </div>

        <div className="max-w-7xl mx-auto p-3 md:p-6">
          {children}
        </div>
      </main>
    </div>
  )
}
