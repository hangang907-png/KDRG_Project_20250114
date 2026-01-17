import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import {
  LayoutDashboard,
  Users,
  BarChart3,
  FileCode,
  FileSpreadsheet,
  GitCompare,
  Calculator,
  Settings,
  LogOut,
  Menu,
  X,
  ChevronRight,
  HelpCircle,
  TrendingUp,
} from 'lucide-react';
import { useState, useEffect } from 'react';
import clsx from 'clsx';
import Tooltip from './Tooltip';
import UpdateReminderModal from './UpdateReminderModal';
import { checkSyncStatus } from '../services/updateService';

const navigation = [
  { name: '대시보드', href: '/dashboard', icon: LayoutDashboard, description: '전체 현황 요약' },
  { name: '환자관리', href: '/patients', icon: Users, description: '환자 데이터 조회/등록' },
  { name: '분석', href: '/analysis', icon: BarChart3, description: 'DRG 분석 결과' },
  { name: 'KDRG', href: '/kdrg', icon: FileCode, description: 'KDRG 코드 관리' },
  { name: 'Pre-Grouper', href: '/pregrouper', icon: Calculator, description: '사전 DRG 분류' },
  { name: '최적화', href: '/optimization', icon: TrendingUp, description: '전역 KDRG 최적화' },
  {
    name: '환류데이터',
    href: '/feedback',
    icon: FileSpreadsheet,
    description: '심평원 환류 데이터',
  },
  { name: '비교분석', href: '/comparison', icon: GitCompare, description: '청구 vs 심사 비교' },
  { name: '설정', href: '/settings', icon: Settings, description: '시스템 설정' },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showUpdateReminder, setShowUpdateReminder] = useState(false);

  // 업데이트 알림 체크 (컴포넌트 마운트 시)
  useEffect(() => {
    const syncStatus = checkSyncStatus(7); // 7일 주기
    if (syncStatus.needsReminder) {
      // 약간의 지연 후 표시 (UX 개선)
      const timer = setTimeout(() => {
        setShowUpdateReminder(true);
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleLogout = () => {
    if (window.confirm('로그아웃 하시겠습니까?')) {
      logout();
      navigate('/login');
    }
  };

  // Get current page name for breadcrumb
  const currentPage = navigation.find(item => location.pathname.startsWith(item.href));

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 lg:hidden transition-opacity"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed top-0 left-0 z-50 h-full w-64 bg-white border-r border-gray-200 transform transition-transform duration-200 ease-in-out lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
        role="navigation"
        aria-label="메인 네비게이션"
      >
        {/* Logo */}
        <div className="flex items-center justify-between h-16 px-6 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <span className="text-sm font-bold text-white">K</span>
            </div>
            <h1 className="text-lg font-bold text-gray-900">KDRG</h1>
          </div>
          <button
            className="lg:hidden p-2 rounded-lg hover:bg-gray-100 transition-colors"
            onClick={() => setSidebarOpen(false)}
            aria-label="메뉴 닫기"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="p-4 space-y-1 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 180px)' }}>
          {navigation.map(item => (
            <NavLink
              key={item.name}
              to={item.href}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all group',
                  isActive
                    ? 'bg-primary-50 text-primary-600 shadow-sm'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                )
              }
            >
              <item.icon className="h-5 w-5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <span>{item.name}</span>
                <p className="text-xs text-gray-400 group-hover:text-gray-500 truncate mt-0.5 hidden lg:block">
                  {item.description}
                </p>
              </div>
            </NavLink>
          ))}
        </nav>

        {/* User section */}
        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-200 bg-white">
          <div className="flex items-center gap-3 px-2">
            <div className="w-10 h-10 bg-gradient-to-br from-primary-400 to-primary-600 rounded-full flex items-center justify-center shadow-sm">
              <span className="text-sm font-semibold text-white">
                {user?.username?.[0]?.toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">{user?.username}</p>
              <p className="text-xs text-gray-500 truncate">{user?.department || '부서 미지정'}</p>
            </div>
            <Tooltip content="로그아웃">
              <button
                onClick={handleLogout}
                className="p-2 text-gray-400 hover:text-red-600 rounded-lg hover:bg-red-50 transition-colors"
                aria-label="로그아웃"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </Tooltip>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Header */}
        <header className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-gray-200">
          <div className="flex items-center justify-between h-16 px-4 lg:px-8">
            {/* Mobile menu button */}
            <button
              className="lg:hidden p-2 rounded-lg hover:bg-gray-100 transition-colors"
              onClick={() => setSidebarOpen(true)}
              aria-label="메뉴 열기"
            >
              <Menu className="h-5 w-5" />
            </button>

            {/* Breadcrumb */}
            <div className="hidden lg:flex items-center gap-2 text-sm">
              <span className="text-gray-400">홈</span>
              {currentPage && (
                <>
                  <ChevronRight className="h-4 w-4 text-gray-300" />
                  <span className="font-medium text-gray-700">{currentPage.name}</span>
                </>
              )}
            </div>

            {/* Right side */}
            <div className="flex items-center gap-4">
              <Tooltip content="도움말">
                <button
                  className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors"
                  aria-label="도움말"
                >
                  <HelpCircle className="h-5 w-5" />
                </button>
              </Tooltip>
              <div className="text-sm text-gray-500 hidden sm:block">
                {new Date().toLocaleDateString('ko-KR', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                  weekday: 'short',
                })}
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 lg:p-8 animate-in fade-in duration-300">
          <Outlet />
        </main>

        {/* Footer */}
        <footer className="px-4 lg:px-8 py-4 border-t border-gray-100 text-center text-xs text-gray-400">
          KDRG Enterprise v1.0 | © 2025 All rights reserved.
        </footer>
      </div>

      {/* Update Reminder Modal */}
      <UpdateReminderModal
        isOpen={showUpdateReminder}
        onClose={() => setShowUpdateReminder(false)}
      />
    </div>
  );
}
