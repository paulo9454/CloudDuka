import React, { useState, useEffect } from 'react';
import { useAuthStore, api, formatCurrency, formatDate } from '../lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import { 
  Plus, 
  Package, 
  AlertTriangle,
  Trash2,
  Loader2,
  Check,
  Search
} from 'lucide-react';

const REASONS = [
  { value: 'damaged', label: 'Damaged' },
  { value: 'expired', label: 'Expired' },
  { value: 'spoiled', label: 'Spoiled' },
  { value: 'other', label: 'Other' },
];

export default function DamagedPage() {
  const { user } = useAuthStore();
  const [items, setItems] = useState([]);
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  
  // Form state
  const [selectedProduct, setSelectedProduct] = useState('');
  const [quantity, setQuantity] = useState('1');
  const [reason, setReason] = useState('damaged');
  const [notes, setNotes] = useState('');

  useEffect(() => {
    loadDamagedStock();
    loadProducts();
  }, []);

  const loadDamagedStock = async () => {
    try {
      const today = new Date();
      const start = new Date(today.getFullYear(), today.getMonth(), 1).toISOString();
      const end = new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString();
      
      const data = await api.get(`/damaged-stock?start_date=${start}&end_date=${end}`);
      setItems(data);
    } catch (error) {
      toast.error('Failed to load damaged stock');
    } finally {
      setLoading(false);
    }
  };

  const loadProducts = async () => {
    try {
      const data = await api.get('/products');
      setProducts(data);
    } catch (error) {
      console.error('Failed to load products');
    }
  };

  const filteredItems = items.filter((item) => {
    const matchesSearch = !searchQuery || 
      item.product_name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  const totalDamaged = items.reduce((sum, i) => sum + i.quantity, 0);
  const byReason = items.reduce((acc, i) => {
    acc[i.reason] = (acc[i.reason] || 0) + i.quantity;
    return acc;
  }, {});

  const handleSubmit = async () => {
    if (!selectedProduct || !quantity) {
      toast.error('Select a product and quantity');
      return;
    }

    setSaving(true);
    try {
      await api.post('/damaged-stock', {
        product_id: selectedProduct,
        quantity: parseInt(quantity),
        reason,
        notes: notes || undefined,
      });
      toast.success('Damaged stock logged');
      setShowModal(false);
      setSelectedProduct('');
      setQuantity('1');
      setReason('damaged');
      setNotes('');
      loadDamagedStock();
      loadProducts();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  const selectedProductInfo = products.find((p) => p.id === selectedProduct);

  return (
    <div className="p-4 space-y-4" data-testid="damaged-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Damaged/Spoiled
        </h1>
        <Button 
          className="bg-red-600 rounded-full"
          onClick={() => setShowModal(true)}
          data-testid="log-damaged-btn"
        >
          <Plus className="mr-1 h-4 w-4" />
          Log
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4">
        <Card className="bg-red-50 border-red-200">
          <CardContent className="p-4">
            <p className="text-sm text-red-600">This Month</p>
            <p className="text-2xl font-bold text-red-700" style={{ fontFamily: 'Outfit, sans-serif' }}>
              {totalDamaged} items
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-sm text-slate-500">Categories</p>
            <div className="flex flex-wrap gap-1 mt-1">
              {Object.entries(byReason).map(([r, count]) => (
                <span 
                  key={r} 
                  className="text-xs px-2 py-0.5 bg-slate-100 rounded-full"
                >
                  {r}: {count}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
        <Input
          placeholder="Search items..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
          data-testid="search-damaged-input"
        />
      </div>

      {/* Items List */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-20 rounded-xl" />
          ))}
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="text-center py-12 text-slate-500">
          <Trash2 className="h-16 w-16 mx-auto mb-4 opacity-30" />
          <p className="font-medium">No damaged stock logged</p>
          <p className="text-sm mt-1">That's good news!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredItems.map((item) => (
            <Card key={item.id} data-testid={`damaged-item-${item.id}`}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-semibold">{item.product_name}</h3>
                    <p className="text-sm text-slate-500">{formatDate(item.created_at)}</p>
                  </div>
                  <div className="text-right">
                    <span className="text-lg font-bold text-red-600">-{item.quantity}</span>
                    <p className={`text-xs px-2 py-0.5 rounded-full inline-block ml-2 ${
                      item.reason === 'damaged' ? 'bg-red-100 text-red-700' :
                      item.reason === 'expired' ? 'bg-amber-100 text-amber-700' :
                      item.reason === 'spoiled' ? 'bg-orange-100 text-orange-700' :
                      'bg-slate-100 text-slate-700'
                    }`}>
                      {item.reason}
                    </p>
                  </div>
                </div>
                {item.notes && (
                  <p className="text-sm text-slate-500 mt-2 italic">"{item.notes}"</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Log Damaged Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-w-md mx-4">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-600" />
              Log Damaged/Spoiled Stock
            </DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Select Product *</Label>
              <Select value={selectedProduct} onValueChange={setSelectedProduct}>
                <SelectTrigger data-testid="damaged-product-select">
                  <SelectValue placeholder="Choose a product" />
                </SelectTrigger>
                <SelectContent>
                  {products.map((p) => (
                    <SelectItem key={p.id} value={p.id}>
                      {p.name} (Stock: {p.stock_quantity})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            {selectedProductInfo && (
              <div className="p-3 bg-slate-50 rounded-lg">
                <p className="text-sm text-slate-500">Current Stock</p>
                <p className="font-bold">{selectedProductInfo.stock_quantity} {selectedProductInfo.unit}</p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Quantity *</Label>
                <Input
                  type="number"
                  value={quantity}
                  onChange={(e) => setQuantity(e.target.value)}
                  min="1"
                  max={selectedProductInfo?.stock_quantity || 999}
                  data-testid="damaged-quantity-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Reason *</Label>
                <Select value={reason} onValueChange={setReason}>
                  <SelectTrigger data-testid="damaged-reason-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {REASONS.map((r) => (
                      <SelectItem key={r.value} value={r.value}>
                        {r.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Notes (Optional)</Label>
              <Input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Additional details..."
                data-testid="damaged-notes-input"
              />
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowModal(false)}>
              Cancel
            </Button>
            <Button 
              className="bg-red-600"
              onClick={handleSubmit}
              disabled={saving}
              data-testid="submit-damaged-btn"
            >
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
              Log Stock Loss
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
