import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore, api, formatCurrency } from '../lib/store';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import { 
  ShoppingCart, 
  Users, 
  BarChart3, 
  Package,
  AlertTriangle,
  ChevronRight,
  Cloud
} from 'lucide-react';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const data = await api.get('/reports/dashboard');
      setStats(data);
    } catch (error) {
      console.error('Failed to load dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  // Calculate days remaining in trial
  const getDaysRemaining = () => {
    if (!user?.trial_ends_at) return 0;
    const trialEnd = new Date(user.trial_ends_at);
    const now = new Date();
    const days = Math.ceil((trialEnd - now) / (1000 * 60 * 60 * 24));
    return Math.max(0, days);
  };

  const daysRemaining = getDaysRemaining();

  if (loading) {
    return (
      <div className="min-h-screen bg-white" data-testid="dashboard-loading">
        <div className="bg-[#007BFF] h-32" />
        <div className="p-4 space-y-4">
          <Skeleton className="h-24 rounded-xl" />
          <div className="grid grid-cols-2 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-28 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-32 rounded-xl" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-100" data-testid="dashboard-page">
      {/* Header with Logo */}
      <div className="bg-[#007BFF] pt-4 pb-8 px-4">
        <div className="flex items-center justify-center gap-2 mb-3">
          <Cloud className="h-8 w-8 text-white" />
          <h1 className="text-2xl font-bold text-white" style={{ fontFamily: 'Outfit, sans-serif' }}>
            Cloud<span className="text-[#FF8C00]">Duka</span>
          </h1>
        </div>
        
        {/* Trial Banner */}
        <div className="text-center">
          <p className="text-white font-semibold text-lg">
            Free Trial: {daysRemaining} Days Remaining
          </p>
        </div>
      </div>

      {/* Upgrade Banner */}
      <div className="bg-slate-200 py-2 px-4 text-center border-b border-slate-300">
        <p className="text-sm text-slate-700">
          Upgrade to Full Version: <span className="font-semibold">KES 300 Monthly</span> or <span className="font-semibold">KES 3,000 Yearly</span>
        </p>
      </div>

      {/* Main Content */}
      <div className="p-4 space-y-4 -mt-4">
        {/* Action Buttons Grid */}
        <div className="grid grid-cols-2 gap-4">
          {/* New Sale */}
          <button
            onClick={() => navigate('/pos')}
            className="bg-[#22C55E] hover:bg-[#16A34A] text-white rounded-2xl p-6 flex flex-col items-center justify-center gap-3 shadow-lg transition-all active:scale-95"
            data-testid="btn-new-sale"
          >
            <div className="bg-white/20 p-3 rounded-xl">
              <ShoppingCart className="h-8 w-8" />
            </div>
            <span className="font-semibold text-lg">New Sale</span>
          </button>

          {/* Credit Sale */}
          <button
            onClick={() => navigate('/credit')}
            className="bg-[#FF8C00] hover:bg-[#E07B00] text-white rounded-2xl p-6 flex flex-col items-center justify-center gap-3 shadow-lg transition-all active:scale-95"
            data-testid="btn-credit-sale"
          >
            <div className="bg-white/20 p-3 rounded-xl">
              <Users className="h-8 w-8" />
            </div>
            <span className="font-semibold text-lg">Credit Sale</span>
          </button>

          {/* Today's Sales */}
          <button
            onClick={() => navigate('/reports')}
            className="bg-[#3B82F6] hover:bg-[#2563EB] text-white rounded-2xl p-6 flex flex-col items-center justify-center gap-3 shadow-lg transition-all active:scale-95"
            data-testid="btn-todays-sales"
          >
            <div className="bg-white/20 p-3 rounded-xl">
              <BarChart3 className="h-8 w-8" />
            </div>
            <span className="font-semibold text-lg">Today's Sales</span>
          </button>

          {/* Stock */}
          <button
            onClick={() => navigate('/products')}
            className="bg-[#8B5CF6] hover:bg-[#7C3AED] text-white rounded-2xl p-6 flex flex-col items-center justify-center gap-3 shadow-lg transition-all active:scale-95"
            data-testid="btn-stock"
          >
            <div className="bg-white/20 p-3 rounded-xl">
              <Package className="h-8 w-8" />
            </div>
            <span className="font-semibold text-lg">Stock</span>
          </button>
        </div>

        {/* Today's Summary Card */}
        <Card className="shadow-md">
          <CardContent className="p-0">
            <div 
              className="flex items-center justify-between p-4 border-b cursor-pointer hover:bg-slate-50"
              onClick={() => navigate('/reports')}
            >
              <h2 className="font-bold text-lg text-slate-800">Today's Summary</h2>
              <ChevronRight className="h-5 w-5 text-slate-400" />
            </div>
            
            <div className="grid grid-cols-3 divide-x">
              <div className="p-4 text-center">
                <p className="text-sm text-slate-500 font-medium">Cash</p>
                <p className="text-lg font-bold text-slate-800">
                  KES {(stats?.today?.cash || 0).toLocaleString()}
                </p>
              </div>
              <div className="p-4 text-center">
                <p className="text-sm text-slate-500 font-medium">M-Pesa</p>
                <p className="text-lg font-bold text-slate-800">
                  KES {(stats?.today?.mpesa || 0).toLocaleString()}
                </p>
              </div>
              <div className="p-4 text-center">
                <p className="text-sm text-slate-500 font-medium">Credit</p>
                <p className="text-lg font-bold text-slate-800">
                  KES {(stats?.today?.credit || 0).toLocaleString()}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Low Stock Alert Card */}
        <Card className="shadow-md border-l-4 border-l-[#FF8C00]">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <div className="bg-orange-100 p-2 rounded-lg">
                <AlertTriangle className="h-6 w-6 text-[#FF8C00]" />
              </div>
              <div className="flex-1">
                <h3 className="font-bold text-[#FF8C00] text-lg">Low Stock Alert!</h3>
                <p className="text-slate-600 mt-1">
                  {stats?.low_stock_count || 0} Item{(stats?.low_stock_count || 0) !== 1 ? 's' : ''} running low!
                </p>
              </div>
            </div>
            
            <Button 
              className="w-full mt-4 bg-[#FF8C00] hover:bg-[#E07B00] text-white rounded-full h-12 font-semibold"
              onClick={() => navigate('/products?filter=low-stock')}
              data-testid="btn-view-stock"
            >
              View Stock
            </Button>
          </CardContent>
        </Card>

        {/* Quick Stats */}
        <div className="grid grid-cols-2 gap-4">
          <Card className="shadow-md">
            <CardContent className="p-4 text-center">
              <p className="text-sm text-slate-500">Total Sales Today</p>
              <p className="text-2xl font-bold text-[#007BFF]" style={{ fontFamily: 'Outfit, sans-serif' }}>
                {formatCurrency(stats?.today?.total || 0)}
              </p>
              <p className="text-xs text-slate-400 mt-1">
                {stats?.today?.count || 0} transactions
              </p>
            </CardContent>
          </Card>
          
          <Card className="shadow-md">
            <CardContent className="p-4 text-center">
              <p className="text-sm text-slate-500">Credit Outstanding</p>
              <p className="text-2xl font-bold text-[#FF8C00]" style={{ fontFamily: 'Outfit, sans-serif' }}>
                {formatCurrency(stats?.total_credit_outstanding || 0)}
              </p>
              <p className="text-xs text-slate-400 mt-1">
                from credit sales
              </p>
            </CardContent>
          </Card>
        </div>

        <Card className="shadow-md">
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-slate-800">Restock Suggestions</h3>
              <Button variant="ghost" className="text-[#007BFF]" onClick={() => navigate('/purchases')}>
                Order stock
              </Button>
            </div>
            {(stats?.restock_suggestions || []).slice(0, 3).map((item) => (
              <div key={item.product_id} className="rounded-xl bg-slate-50 px-3 py-2 flex items-center justify-between gap-3">
                <div>
                  <p className="font-medium text-slate-800">{item.product_name}</p>
                  <p className="text-xs text-slate-500">Stock {item.stock_quantity} / Min {item.min_stock_level}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-semibold text-[#FF8C00]">Restock {item.recommended_restock}</p>
                  <p className="text-xs text-slate-500">{formatCurrency(item.estimated_restock_cost || 0)}</p>
                </div>
              </div>
            ))}
            {(stats?.restock_suggestions || []).length === 0 ? (
              <p className="text-sm text-slate-500">No urgent restocks today.</p>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
