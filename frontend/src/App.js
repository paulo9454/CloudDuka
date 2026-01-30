import React, { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import { useAuthStore, useOfflineStore } from './lib/store';
import { 
  LayoutDashboard, 
  ShoppingCart, 
  Package, 
  MoreHorizontal,
  Users,
  CreditCard,
  Trash2,
  BarChart3,
  Settings,
  WifiOff,
  Truck,
  ShoppingBag,
  HelpCircle,
  MessageSquare
} from 'lucide-react';

// Pages
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import POSPage from './pages/POSPage';
import ProductsPage from './pages/ProductsPage';
import CreditPage from './pages/CreditPage';
import DamagedPage from './pages/DamagedPage';
import ReportsPage from './pages/ReportsPage';
import UsersPage from './pages/UsersPage';
import SettingsPage from './pages/SettingsPage';
import SuppliersPage from './pages/SuppliersPage';
import PurchasesPage from './pages/PurchasesPage';

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated } = useAuthStore();
  
  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }
  
  return children;
};

// Owner Only Route
const OwnerRoute = ({ children }) => {
  const { isAuthenticated, user } = useAuthStore();
  
  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }
  
  if (user?.role !== 'owner') {
    return <Navigate to="/dashboard" replace />;
  }
  
  return children;
};

// Bottom Navigation Component
const BottomNav = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [showMore, setShowMore] = useState(false);
  
  const mainNavItems = [
    { path: '/dashboard', icon: LayoutDashboard, label: 'Home' },
    { path: '/pos', icon: ShoppingCart, label: 'POS' },
    { path: '/products', icon: Package, label: 'Products' },
    { path: '/more', icon: MoreHorizontal, label: 'More', isMore: true },
  ];
  
  const moreItems = [
    { path: '/credit', icon: CreditCard, label: 'Credit' },
    { path: '/damaged', icon: Trash2, label: 'Damaged' },
    { path: '/reports', icon: BarChart3, label: 'Reports' },
    ...(user?.role === 'owner' ? [{ path: '/users', icon: Users, label: 'Users' }] : []),
    { path: '/settings', icon: Settings, label: 'Settings' },
  ];

  const handleNavClick = (item) => {
    if (item.isMore) {
      setShowMore(!showMore);
    } else {
      navigate(item.path);
      setShowMore(false);
    }
  };

  const isActive = (path) => {
    if (path === '/more') {
      return moreItems.some(item => location.pathname === item.path);
    }
    return location.pathname === path;
  };

  return (
    <>
      {/* More Menu Overlay */}
      {showMore && (
        <div 
          className="fixed inset-0 bg-black/20 z-40"
          onClick={() => setShowMore(false)}
        />
      )}
      
      {/* More Menu */}
      {showMore && (
        <div className="fixed bottom-16 right-4 bg-white rounded-2xl shadow-xl border z-50 p-2 min-w-[180px] animate-in slide-in-from-bottom-4">
          {moreItems.map((item) => (
            <button
              key={item.path}
              onClick={() => { navigate(item.path); setShowMore(false); }}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-colors ${
                location.pathname === item.path 
                  ? 'bg-[#007BFF]/10 text-[#007BFF]' 
                  : 'hover:bg-slate-50'
              }`}
              data-testid={`nav-more-${item.label.toLowerCase()}`}
            >
              <item.icon className="h-5 w-5" />
              <span className="font-medium">{item.label}</span>
            </button>
          ))}
        </div>
      )}
      
      {/* Bottom Navigation */}
      <nav className="bottom-nav" data-testid="bottom-nav">
        <div className="flex justify-around items-center max-w-md mx-auto">
          {mainNavItems.map((item) => (
            <button
              key={item.path}
              onClick={() => handleNavClick(item)}
              className={`flex flex-col items-center justify-center py-2 px-4 rounded-xl transition-all min-w-[64px] ${
                isActive(item.path)
                  ? 'text-[#007BFF]'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
              data-testid={`nav-${item.label.toLowerCase()}`}
            >
              <item.icon className={`h-6 w-6 ${isActive(item.path) ? 'scale-110' : ''}`} />
              <span className="text-xs mt-1 font-medium">{item.label}</span>
              {isActive(item.path) && (
                <div className="absolute bottom-1 w-1 h-1 rounded-full bg-[#007BFF]" />
              )}
            </button>
          ))}
        </div>
      </nav>
    </>
  );
};

// Main Layout with Bottom Nav
const MainLayout = ({ children }) => {
  const { isOnline, setOnlineStatus, pendingSales, syncPendingSales } = useOfflineStore();
  
  useEffect(() => {
    const handleOnline = () => {
      setOnlineStatus(true);
      if (pendingSales.length > 0) {
        syncPendingSales();
      }
    };
    const handleOffline = () => setOnlineStatus(false);
    
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [setOnlineStatus, pendingSales, syncPendingSales]);

  return (
    <div className="app-container bg-slate-50">
      {/* Offline Banner */}
      {!isOnline && (
        <div className="offline-banner flex items-center justify-center gap-2" data-testid="offline-banner">
          <WifiOff className="h-4 w-4" />
          <span>You're offline. Sales will sync when back online.</span>
        </div>
      )}
      
      {/* Main Content */}
      <main className="main-content">
        {children}
      </main>
      
      {/* Bottom Navigation */}
      <BottomNav />
    </div>
  );
};

function App() {
  return (
    <>
      <BrowserRouter>
        <Routes>
          {/* Public Route */}
          <Route path="/" element={<LoginPage />} />
          
          {/* Protected Routes */}
          <Route 
            path="/dashboard" 
            element={
              <ProtectedRoute>
                <MainLayout>
                  <DashboardPage />
                </MainLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/pos" 
            element={
              <ProtectedRoute>
                <MainLayout>
                  <POSPage />
                </MainLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/products" 
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ProductsPage />
                </MainLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/credit" 
            element={
              <ProtectedRoute>
                <MainLayout>
                  <CreditPage />
                </MainLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/damaged" 
            element={
              <ProtectedRoute>
                <MainLayout>
                  <DamagedPage />
                </MainLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/reports" 
            element={
              <ProtectedRoute>
                <MainLayout>
                  <ReportsPage />
                </MainLayout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/users" 
            element={
              <OwnerRoute>
                <MainLayout>
                  <UsersPage />
                </MainLayout>
              </OwnerRoute>
            } 
          />
          <Route 
            path="/settings" 
            element={
              <ProtectedRoute>
                <MainLayout>
                  <SettingsPage />
                </MainLayout>
              </ProtectedRoute>
            } 
          />
          
          {/* Catch all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-center" richColors />
    </>
  );
}

export default App;
