import React, { useEffect, useState } from 'react';
import { api, formatCurrency, formatDate } from '../lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { toast } from 'sonner';

export default function AdminDashboardPage() {
  const [stats, setStats] = useState(null);
  const [paymentGuide, setPaymentGuide] = useState(null);

  useEffect(() => {
    Promise.all([api.get('/dashboard/admin'), api.get('/payments/providers/compare')])
      .then(([dashboard, compare]) => {
        setStats(dashboard);
        setPaymentGuide(compare);
      })
      .catch((error) => toast.error(error.message || 'Failed to load admin analytics'));
  }, []);

  return (
    <div className="p-4 space-y-4" data-testid="admin-dashboard-page">
      <div>
        <h1 className="text-2xl font-bold">Admin Dashboard</h1>
        <p className="text-sm text-slate-500">Review cross-shop demand, outstanding vendor orders, and payment strategy.</p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ['Shops', stats?.shops_count || 0],
          ['Users', stats?.users_count || 0],
          ['Orders', stats?.orders_count || 0],
          ['Revenue', formatCurrency(stats?.total_revenue || 0)],
        ].map(([label, value]) => (
          <Card key={label}><CardContent className="p-4"><p className="text-sm text-slate-500">{label}</p><p className="text-2xl font-bold">{value}</p></CardContent></Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Cross-shop Restock Queue</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {(stats?.restock_suggestions || []).map((item) => (
              <div key={`${item.shop_id}-${item.product_id}`} className="rounded-xl border p-3">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold">{item.product_name}</p>
                    <p className="text-xs text-slate-500">{item.shop_name} · stock {item.stock_quantity}/{item.min_stock_level}</p>
                  </div>
                  <Badge variant="secondary">Restock {item.recommended_restock}</Badge>
                </div>
              </div>
            ))}
            {(stats?.restock_suggestions || []).length === 0 ? <p className="text-sm text-slate-500">All shops are above minimum stock.</p> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Payment Recommendation</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="rounded-xl bg-emerald-50 border border-emerald-200 p-3">
              <p className="font-semibold text-emerald-700">Recommended: {paymentGuide?.recommended_provider || '—'}</p>
              <p className="text-slate-700 mt-1">{paymentGuide?.guidance}</p>
            </div>
            {(paymentGuide?.comparison || []).map((provider) => (
              <div key={provider.provider} className="rounded-xl border p-3">
                <p className="font-semibold capitalize">{provider.provider}</p>
                <p className="text-slate-600 mt-1">Best for: {provider.best_for}</p>
                <p className="text-slate-500 mt-2">Strengths: {provider.strengths.join(', ')}</p>
                <p className="text-slate-500 mt-1">Tradeoffs: {provider.tradeoffs.join(', ')}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Marketplace Orders</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {(stats?.marketplace_orders || []).map((order) => (
              <div key={order.id} className="rounded-xl border p-3 flex items-center justify-between gap-3">
                <div>
                  <p className="font-semibold">{order.order_number}</p>
                  <p className="text-xs text-slate-500">{order.vendor_name || order.customer_name} · {formatDate(order.created_at)}</p>
                </div>
                <div className="text-right">
                  <Badge>{order.status}</Badge>
                  <p className="mt-2 text-sm font-medium">{formatCurrency(order.total_amount)}</p>
                </div>
              </div>
            ))}
            {(stats?.marketplace_orders || []).length === 0 ? <p className="text-sm text-slate-500">No marketplace orders created yet.</p> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Payment Mix</CardTitle></CardHeader>
          <CardContent className="space-y-2 text-sm">
            {Object.entries(stats?.payments_summary?.by_method || {}).map(([method, detail]) => (
              <div key={method} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                <span className="capitalize">{method.replace('_', ' ')}</span>
                <span>{detail.count} payments · {formatCurrency(detail.amount)}</span>
              </div>
            ))}
            {Object.keys(stats?.payments_summary?.by_method || {}).length === 0 ? <p className="text-slate-500">No payments available.</p> : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
