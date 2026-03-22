import React, { useEffect, useState } from 'react';
import { api, formatCurrency, formatDate } from '../lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { AlertTriangle, CreditCard, Package, ShoppingBag } from 'lucide-react';

const summaryCards = (stats) => [
  { label: 'Products', value: stats?.products_count || 0, icon: Package },
  { label: 'Pending Orders', value: stats?.pending_orders || 0, icon: ShoppingBag },
  { label: 'Collected', value: formatCurrency(stats?.payments_summary?.total_collected || 0), icon: CreditCard },
  { label: 'Restock Alerts', value: stats?.restock_suggestions?.length || 0, icon: AlertTriangle },
];

export default function VendorDashboardPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api.get('/dashboard/vendor');
        setStats(data);
      } catch (error) {
        toast.error(error.message || 'Failed to load dashboard');
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  return (
    <div className="p-4 space-y-4" data-testid="vendor-dashboard-page">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Vendor Dashboard</h1>
          <p className="text-sm text-slate-500">Monitor sell-through, restock pressure, and marketplace receipts.</p>
        </div>
        <Button variant="outline" onClick={() => window.location.reload()}>Refresh</Button>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {summaryCards(stats).map(({ label, value, icon: Icon }) => (
          <Card key={label}>
            <CardContent className="p-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-sm text-slate-500">{label}</p>
                <p className="text-xl font-bold">{loading ? '…' : value}</p>
              </div>
              <div className="bg-slate-100 rounded-full p-3"><Icon className="h-5 w-5 text-slate-600" /></div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Restock Suggestions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(stats?.restock_suggestions || []).length === 0 ? (
              <p className="text-sm text-slate-500">No urgent restocks right now.</p>
            ) : (
              stats.restock_suggestions.map((item) => (
                <div key={item.product_id} className="rounded-xl border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="font-semibold">{item.product_name}</p>
                      <p className="text-xs text-slate-500">Stock {item.stock_quantity} / Min {item.min_stock_level}</p>
                    </div>
                    <Badge variant="secondary">Restock {item.recommended_restock}</Badge>
                  </div>
                  <p className="mt-2 text-sm text-slate-600">Estimated spend: {formatCurrency(item.estimated_restock_cost || 0)}</p>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Marketplace Orders</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(stats?.marketplace_orders || []).length === 0 ? (
              <p className="text-sm text-slate-500">No marketplace orders yet.</p>
            ) : (
              stats.marketplace_orders.map((order) => (
                <div key={order.id} className="rounded-xl border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="font-semibold">{order.order_number}</p>
                      <p className="text-xs text-slate-500">{order.vendor_name || order.customer_name}</p>
                    </div>
                    <Badge>{order.status}</Badge>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-sm text-slate-600">
                    <span>{formatDate(order.created_at)}</span>
                    <span>{formatCurrency(order.total_amount)}</span>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Payment Mix</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {Object.entries(stats?.payments_summary?.by_method || {}).map(([method, detail]) => (
            <div key={method} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
              <span className="capitalize">{method.replace('_', ' ')}</span>
              <span>{detail.count} payments · {formatCurrency(detail.amount)}</span>
            </div>
          ))}
          {Object.keys(stats?.payments_summary?.by_method || {}).length === 0 ? <p className="text-slate-500">No payments recorded yet.</p> : null}
        </CardContent>
      </Card>
    </div>
  );
}
