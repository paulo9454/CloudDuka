import React, { useCallback, useEffect, useState } from 'react';
import { api, formatCurrency, formatDate } from '../lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';

export default function OrdersPage() {
  const [orders, setOrders] = useState([]);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(true);

  const loadOrders = useCallback(async () => {
    try {
      const query = status ? `?status=${encodeURIComponent(status)}` : '';
      const data = await api.get(`/orders${query}`);
      setOrders(Array.isArray(data) ? data : (data?.data || []));
    } catch (error) {
      toast.error(error.message || 'Failed to load orders');
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    loadOrders();
  }, [loadOrders]);

  return (
    <div className="p-4 space-y-4" data-testid="orders-page">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Orders</h1>
          <p className="text-sm text-slate-500">Track checkout activity and fulfillment status.</p>
        </div>
        <Button variant="outline" onClick={loadOrders}>Refresh</Button>
      </div>

      <Input placeholder="Filter by status (paid, pending, shipped...)" value={status} onChange={(e) => setStatus(e.target.value)} />

      <div className="grid gap-3">
        {loading ? <Card><CardContent className="p-6 text-sm text-slate-500">Loading orders...</CardContent></Card> : null}
        {!loading && orders.length === 0 ? <Card><CardContent className="p-6 text-sm text-slate-500">No orders found.</CardContent></Card> : null}
        {orders.map((order) => (
          <Card key={order.id}>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="text-base">{order.order_number || order.id}</CardTitle>
                <div className="flex gap-2">
                  <Badge variant="secondary">{order.payment_status || 'unknown'}</Badge>
                  <Badge>{order.status}</Badge>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between"><span>Total</span><span className="font-semibold">{formatCurrency(order.total_amount)}</span></div>
              <div className="flex justify-between"><span>Payment</span><span>{order.payment_method}</span></div>
              <div className="flex justify-between"><span>Created</span><span>{formatDate(order.created_at)}</span></div>
              <div className="pt-2 border-t">
                {(order.items || []).map((item) => (
                  <div key={`${order.id}-${item.product_id}`} className="flex justify-between py-1">
                    <span>{item.product_name} × {item.quantity}</span>
                    <span>{formatCurrency(item.total)}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
