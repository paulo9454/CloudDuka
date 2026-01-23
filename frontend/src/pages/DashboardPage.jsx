import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore, api, formatCurrency, formatTime } from '../lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import { 
  LayoutDashboard, 
  TrendingUp, 
  Package, 
  AlertTriangle, 
  CreditCard,
  ShoppingCart,
  ArrowRight,
  Wallet,
  Smartphone,
  Users
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

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

  const StatCard = ({ title, value, icon: Icon, color, onClick }) => (
    <Card 
      className={`cursor-pointer card-interactive ${onClick ? 'hover:border-[#007BFF]/50' : ''}`}
      onClick={onClick}
      data-testid={`stat-card-${title.toLowerCase().replace(/\s/g, '-')}`}
    >
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-500">{title}</p>
            <p className="text-2xl font-bold mt-1" style={{ fontFamily: 'Outfit, sans-serif' }}>
              {value}
            </p>
          </div>
          <div className={`p-3 rounded-xl ${color}`}>
            <Icon className="h-6 w-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  );

  if (loading) {
    return (
      <div className="p-4 space-y-4" data-testid="dashboard-loading">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-2 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
        <Skeleton className="h-48 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="p-4 space-y-6" data-testid="dashboard-page">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Hello, {user?.name?.split(' ')[0] || 'there'}!
        </h1>
        <p className="text-slate-500 text-sm mt-1">Here's your shop overview for today</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4">
        <StatCard
          title="Today's Sales"
          value={formatCurrency(stats?.today?.total || 0)}
          icon={TrendingUp}
          color="bg-green-100 text-green-600"
          onClick={() => navigate('/reports')}
        />
        <StatCard
          title="Transactions"
          value={stats?.today?.count || 0}
          icon={ShoppingCart}
          color="bg-blue-100 text-[#007BFF]"
          onClick={() => navigate('/reports')}
        />
        <StatCard
          title="Low Stock"
          value={stats?.low_stock_count || 0}
          icon={AlertTriangle}
          color={stats?.low_stock_count > 0 ? "bg-amber-100 text-amber-600" : "bg-slate-100 text-slate-600"}
          onClick={() => navigate('/products?filter=low-stock')}
        />
        <StatCard
          title="Credit Due"
          value={formatCurrency(stats?.total_credit_outstanding || 0)}
          icon={CreditCard}
          color="bg-orange-100 text-[#FF8C00]"
          onClick={() => navigate('/credit')}
        />
      </div>

      {/* Payment Methods Breakdown */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg flex items-center gap-2">
            <Wallet className="h-5 w-5 text-[#007BFF]" />
            Today by Payment
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between p-3 bg-green-50 rounded-xl">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <Wallet className="h-5 w-5 text-green-600" />
              </div>
              <span className="font-medium">Cash</span>
            </div>
            <span className="font-bold text-green-600">{formatCurrency(stats?.today?.cash || 0)}</span>
          </div>
          
          <div className="flex items-center justify-between p-3 bg-emerald-50 rounded-xl">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-emerald-100 rounded-lg">
                <Smartphone className="h-5 w-5 text-emerald-600" />
              </div>
              <span className="font-medium">M-Pesa</span>
            </div>
            <span className="font-bold text-emerald-600">{formatCurrency(stats?.today?.mpesa || 0)}</span>
          </div>
          
          <div className="flex items-center justify-between p-3 bg-orange-50 rounded-xl">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-orange-100 rounded-lg">
                <Users className="h-5 w-5 text-orange-600" />
              </div>
              <span className="font-medium">Credit</span>
            </div>
            <span className="font-bold text-orange-600">{formatCurrency(stats?.today?.credit || 0)}</span>
          </div>
        </CardContent>
      </Card>

      {/* Weekly Sales Chart */}
      {stats?.weekly_sales && stats.weekly_sales.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Weekly Sales</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={stats.weekly_sales}>
                  <defs>
                    <linearGradient id="salesGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#007BFF" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#007BFF" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis 
                    dataKey="date" 
                    axisLine={false} 
                    tickLine={false}
                    tick={{ fontSize: 12, fill: '#64748b' }}
                  />
                  <YAxis 
                    axisLine={false} 
                    tickLine={false}
                    tick={{ fontSize: 12, fill: '#64748b' }}
                    tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`}
                  />
                  <Tooltip 
                    formatter={(value) => [formatCurrency(value), 'Sales']}
                    contentStyle={{ 
                      borderRadius: '12px', 
                      border: 'none', 
                      boxShadow: '0 4px 12px rgba(0,0,0,0.1)' 
                    }}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="sales" 
                    stroke="#007BFF" 
                    strokeWidth={2}
                    fill="url(#salesGradient)" 
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Low Stock Alert */}
      {stats?.low_stock_items && stats.low_stock_items.length > 0 && (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2 text-amber-700">
              <AlertTriangle className="h-5 w-5" />
              Low Stock Alert
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {stats.low_stock_items.slice(0, 3).map((item) => (
                <div 
                  key={item.id} 
                  className="flex items-center justify-between p-3 bg-white rounded-lg"
                >
                  <div>
                    <p className="font-medium">{item.name}</p>
                    <p className="text-sm text-slate-500">{item.stock_quantity} left</p>
                  </div>
                  <span className="px-3 py-1 bg-amber-100 text-amber-700 rounded-full text-sm font-medium">
                    Restock
                  </span>
                </div>
              ))}
            </div>
            <Button 
              variant="ghost" 
              className="w-full mt-3 text-amber-700"
              onClick={() => navigate('/products?filter=low-stock')}
              data-testid="view-all-low-stock-btn"
            >
              View All <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Recent Transactions */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Recent Sales</CardTitle>
        </CardHeader>
        <CardContent>
          {stats?.recent_sales && stats.recent_sales.length > 0 ? (
            <div className="space-y-3">
              {stats.recent_sales.slice(0, 5).map((sale) => (
                <div 
                  key={sale.id} 
                  className="flex items-center justify-between p-3 bg-slate-50 rounded-xl"
                  data-testid={`recent-sale-${sale.id}`}
                >
                  <div>
                    <p className="font-medium">{sale.receipt_number}</p>
                    <p className="text-sm text-slate-500">
                      {formatTime(sale.created_at)} • {sale.items.length} items
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-bold">{formatCurrency(sale.total_amount)}</p>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      sale.payment_method === 'cash' ? 'bg-green-100 text-green-700' :
                      sale.payment_method === 'mpesa' ? 'bg-emerald-100 text-emerald-700' :
                      'bg-orange-100 text-orange-700'
                    }`}>
                      {sale.payment_method.toUpperCase()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-slate-500">
              <ShoppingCart className="h-12 w-12 mx-auto mb-2 opacity-30" />
              <p>No sales today yet</p>
              <Button 
                className="mt-4 bg-[#007BFF]"
                onClick={() => navigate('/pos')}
                data-testid="start-selling-btn"
              >
                Start Selling
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 gap-4">
        <Button 
          className="h-14 bg-[#007BFF] hover:bg-[#0069D9] rounded-xl"
          onClick={() => navigate('/pos')}
          data-testid="quick-new-sale-btn"
        >
          <ShoppingCart className="mr-2 h-5 w-5" />
          New Sale
        </Button>
        <Button 
          variant="outline"
          className="h-14 border-2 rounded-xl"
          onClick={() => navigate('/products')}
          data-testid="quick-products-btn"
        >
          <Package className="mr-2 h-5 w-5" />
          Products
        </Button>
      </div>
    </div>
  );
}
