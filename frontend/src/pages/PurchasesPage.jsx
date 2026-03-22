import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { api, formatCurrency, formatDate } from '../lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Textarea } from '../components/ui/textarea';
import { toast } from 'sonner';

const emptyItem = { product_id: '', quantity: '1', unit_cost: '' };

export default function PurchasesPage() {
  const [vendors, setVendors] = useState([]);
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [paymentGuide, setPaymentGuide] = useState(null);
  const [activeTab, setActiveTab] = useState('new');
  const [showAddItem, setShowAddItem] = useState(false);
  const [saving, setSaving] = useState(false);
  const [orderForm, setOrderForm] = useState({ vendor_id: '', payment_method: 'mpesa', notes: '' });
  const [itemForm, setItemForm] = useState(emptyItem);
  const [items, setItems] = useState([]);

  const loadData = useCallback(async () => {
    try {
      const [vendorsData, productsData, ordersData, compareData] = await Promise.all([
        api.get('/marketplace/vendors'),
        api.get('/products'),
        api.get('/marketplace/orders'),
        api.get('/payments/providers/compare'),
      ]);
      setVendors(vendorsData);
      setProducts(productsData);
      setOrders(ordersData);
      setPaymentGuide(compareData);
    } catch (error) {
      toast.error(error.message || 'Failed to load marketplace data');
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const totalAmount = useMemo(
    () => items.reduce((sum, item) => sum + (Number(item.quantity) * Number(item.unit_cost)), 0),
    [items]
  );

  const addItem = () => {
    const product = products.find((entry) => entry.id === itemForm.product_id);
    if (!product) {
      toast.error('Select a product to order');
      return;
    }

    const quantity = Number(itemForm.quantity);
    const unitCost = Number(itemForm.unit_cost);
    if (quantity <= 0 || unitCost <= 0) {
      toast.error('Enter a valid quantity and unit cost');
      return;
    }

    setItems((current) => [
      ...current,
      {
        product_id: product.id,
        product_name: product.name,
        quantity,
        unit_cost: unitCost,
      },
    ]);
    setItemForm(emptyItem);
    setShowAddItem(false);
  };

  const submitOrder = async () => {
    if (!orderForm.vendor_id) {
      toast.error('Select a marketplace vendor');
      return;
    }
    if (items.length === 0) {
      toast.error('Add at least one order item');
      return;
    }

    setSaving(true);
    try {
      await api.post('/marketplace/orders', {
        vendor_id: orderForm.vendor_id,
        payment_method: orderForm.payment_method,
        notes: orderForm.notes || undefined,
        items,
      });
      toast.success('Marketplace order created');
      setItems([]);
      setOrderForm({ vendor_id: '', payment_method: 'mpesa', notes: '' });
      setActiveTab('history');
      loadData();
    } catch (error) {
      toast.error(error.message || 'Failed to create marketplace order');
    } finally {
      setSaving(false);
    }
  };

  const updateOrderStatus = async (orderId, status) => {
    try {
      await api.post(`/marketplace/orders/${orderId}/receive`, { status });
      toast.success(`Order marked as ${status}`);
      loadData();
    } catch (error) {
      toast.error(error.message || 'Failed to update order');
    }
  };

  return (
    <div className="p-4 space-y-4" data-testid="purchases-page">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Marketplace Ordering</h1>
          <p className="text-sm text-slate-500">Create vendor orders, receive deliveries, and keep shop subscriptions/payment strategy separate per shop.</p>
        </div>
        <div className="rounded-xl border bg-slate-50 px-3 py-2 text-sm">
          <p className="font-medium">Recommended scale provider</p>
          <p className="capitalize text-emerald-700">{paymentGuide?.recommended_provider || '—'}</p>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <Card><CardContent className="p-4"><p className="text-sm text-slate-500">Open Orders</p><p className="text-2xl font-bold">{orders.filter((order) => order.status === 'ordered').length}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-sm text-slate-500">Delivered</p><p className="text-2xl font-bold">{orders.filter((order) => order.status === 'delivered').length}</p></CardContent></Card>
        <Card><CardContent className="p-4"><p className="text-sm text-slate-500">Pipeline Value</p><p className="text-2xl font-bold">{formatCurrency(orders.filter((order) => order.status !== 'cancelled').reduce((sum, order) => sum + order.total_amount, 0))}</p></CardContent></Card>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="new">New Order</TabsTrigger>
          <TabsTrigger value="history">Order History</TabsTrigger>
        </TabsList>

        <TabsContent value="new" className="space-y-4 mt-4">
          <Card>
            <CardHeader><CardTitle>Create Marketplace Order</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2">
                  <Label>Vendor</Label>
                  <Select value={orderForm.vendor_id} onValueChange={(value) => setOrderForm((current) => ({ ...current, vendor_id: value }))}>
                    <SelectTrigger><SelectValue placeholder="Choose a vendor" /></SelectTrigger>
                    <SelectContent>
                      {vendors.map((vendor) => <SelectItem key={vendor.id} value={vendor.id}>{vendor.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Payment Method</Label>
                  <Select value={orderForm.payment_method} onValueChange={(value) => setOrderForm((current) => ({ ...current, payment_method: value }))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="mpesa">M-Pesa</SelectItem>
                      <SelectItem value="paystack">Paystack</SelectItem>
                      <SelectItem value="bank_transfer">Bank transfer</SelectItem>
                      <SelectItem value="cash">Cash</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Notes</Label>
                <Textarea value={orderForm.notes} onChange={(event) => setOrderForm((current) => ({ ...current, notes: event.target.value }))} placeholder="Delivery timing, package notes, reorder reason..." />
              </div>

              <div className="rounded-xl border p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold">Order Items</h3>
                  <Button type="button" variant="outline" onClick={() => setShowAddItem(true)}>Add Item</Button>
                </div>
                {items.length === 0 ? <p className="text-sm text-slate-500">No items added yet.</p> : null}
                {items.map((item, index) => (
                  <div key={`${item.product_id}-${index}`} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                    <span>{item.product_name} × {item.quantity}</span>
                    <div className="flex items-center gap-3">
                      <span>{formatCurrency(item.quantity * item.unit_cost)}</span>
                      <Button type="button" size="sm" variant="ghost" onClick={() => setItems((current) => current.filter((_, itemIndex) => itemIndex !== index))}>Remove</Button>
                    </div>
                  </div>
                ))}
                <div className="flex items-center justify-between border-t pt-3 font-semibold">
                  <span>Total</span>
                  <span>{formatCurrency(totalAmount)}</span>
                </div>
              </div>

              <Button className="w-full" onClick={submitOrder} disabled={saving}>{saving ? 'Saving…' : 'Create Marketplace Order'}</Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="history" className="space-y-4 mt-4">
          {(orders || []).map((order) => (
            <Card key={order.id}>
              <CardContent className="p-4 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{order.order_number}</p>
                    <p className="text-sm text-slate-500">{order.vendor_name || order.customer_name} · {formatDate(order.created_at)}</p>
                  </div>
                  <div className="text-right">
                    <Badge>{order.status}</Badge>
                    <p className="mt-2 font-semibold">{formatCurrency(order.total_amount)}</p>
                  </div>
                </div>
                <div className="space-y-2 text-sm">
                  {order.items.map((item) => (
                    <div key={`${order.id}-${item.product_id}`} className="flex items-center justify-between">
                      <span>{item.product_name} × {item.quantity}</span>
                      <span>{formatCurrency(item.total)}</span>
                    </div>
                  ))}
                </div>
                {order.status === 'ordered' ? (
                  <div className="flex gap-2 pt-2">
                    <Button size="sm" onClick={() => updateOrderStatus(order.id, 'delivered')}>Mark Delivered</Button>
                    <Button size="sm" variant="outline" onClick={() => updateOrderStatus(order.id, 'cancelled')}>Cancel</Button>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          ))}
          {orders.length === 0 ? <Card><CardContent className="p-6 text-sm text-slate-500">No marketplace orders yet.</CardContent></Card> : null}
        </TabsContent>
      </Tabs>

      <Dialog open={showAddItem} onOpenChange={setShowAddItem}>
        <DialogContent>
          <DialogHeader><DialogTitle>Add Marketplace Item</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-2">
              <Label>Product</Label>
              <Select value={itemForm.product_id} onValueChange={(value) => setItemForm((current) => ({ ...current, product_id: value }))}>
                <SelectTrigger><SelectValue placeholder="Choose a product" /></SelectTrigger>
                <SelectContent>
                  {products.map((product) => <SelectItem key={product.id} value={product.id}>{product.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>Quantity</Label>
                <Input type="number" min="1" value={itemForm.quantity} onChange={(event) => setItemForm((current) => ({ ...current, quantity: event.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label>Unit Cost</Label>
                <Input type="number" min="0" step="0.01" value={itemForm.unit_cost} onChange={(event) => setItemForm((current) => ({ ...current, unit_cost: event.target.value }))} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowAddItem(false)}>Cancel</Button>
            <Button onClick={addItem}>Add Item</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
