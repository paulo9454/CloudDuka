import React, { useState, useEffect } from 'react';
import { useAuthStore, api, formatCurrency, formatDate, formatDateTime } from '../lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import { 
  Plus, 
  Package,
  Truck,
  Loader2,
  Check,
  Calendar,
  Filter,
  ShoppingBag,
  Trash2,
  X
} from 'lucide-react';

export default function PurchasesPage() {
  const { user } = useAuthStore();
  const isOwner = user?.role === 'owner';
  
  const [activeTab, setActiveTab] = useState('new');
  const [suppliers, setSuppliers] = useState([]);
  const [products, setProducts] = useState([]);
  const [purchases, setPurchases] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ today_total: 0, month_total: 0, supplier_count: 0 });
  
  // New Purchase Form
  const [selectedSupplier, setSelectedSupplier] = useState('');
  const [purchaseItems, setPurchaseItems] = useState([]);
  const [purchaseNotes, setPurchaseNotes] = useState('');
  const [saving, setSaving] = useState(false);
  
  // Add Item Modal
  const [showAddItem, setShowAddItem] = useState(false);
  const [itemForm, setItemForm] = useState({
    product_id: '',
    quantity: '1',
    unit_type: 'units',
    units_per_package: '1',
    cost: '',
  });
  
  // Filter state
  const [filterSupplier, setFilterSupplier] = useState('all');
  const [filterDateStart, setFilterDateStart] = useState('');
  const [filterDateEnd, setFilterDateEnd] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [suppliersData, productsData, purchasesData, statsData] = await Promise.all([
        api.get('/suppliers'),
        api.get('/products'),
        api.get('/purchases'),
        api.get('/purchases/stats/summary')
      ]);
      setSuppliers(suppliersData);
      setProducts(productsData);
      setPurchases(purchasesData);
      setStats(statsData);
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const loadPurchases = async () => {
    try {
      let endpoint = '/purchases?';
      if (filterSupplier !== 'all') endpoint += `supplier_id=${filterSupplier}&`;
      if (filterDateStart) endpoint += `start_date=${filterDateStart}T00:00:00&`;
      if (filterDateEnd) endpoint += `end_date=${filterDateEnd}T23:59:59&`;
      
      const data = await api.get(endpoint);
      setPurchases(data);
    } catch (error) {
      toast.error('Failed to load purchases');
    }
  };

  useEffect(() => {
    if (!loading) {
      loadPurchases();
    }
  }, [filterSupplier, filterDateStart, filterDateEnd]);

  const handleAddItem = () => {
    const product = products.find(p => p.id === itemForm.product_id);
    if (!product) {
      toast.error('Please select a product');
      return;
    }
    if (!itemForm.cost || parseFloat(itemForm.cost) <= 0) {
      toast.error('Please enter a valid cost');
      return;
    }

    const newItem = {
      product_id: product.id,
      product_name: product.name,
      quantity: parseInt(itemForm.quantity) || 1,
      unit_type: itemForm.unit_type,
      units_per_package: parseInt(itemForm.units_per_package) || 1,
      cost: parseFloat(itemForm.cost),
    };

    setPurchaseItems([...purchaseItems, newItem]);
    setShowAddItem(false);
    setItemForm({
      product_id: '',
      quantity: '1',
      unit_type: 'units',
      units_per_package: '1',
      cost: '',
    });
    toast.success(`${product.name} added`);
  };

  const handleRemoveItem = (index) => {
    setPurchaseItems(purchaseItems.filter((_, i) => i !== index));
  };

  const getTotalCost = () => {
    return purchaseItems.reduce((sum, item) => sum + item.cost, 0);
  };

  const getTotalUnits = (item) => {
    return item.quantity * item.units_per_package;
  };

  const handleCreatePurchase = async () => {
    if (!selectedSupplier) {
      toast.error('Please select a supplier');
      return;
    }
    if (purchaseItems.length === 0) {
      toast.error('Please add at least one item');
      return;
    }

    setSaving(true);
    try {
      await api.post('/purchases', {
        supplier_id: selectedSupplier,
        items: purchaseItems,
        total_cost: getTotalCost(),
        notes: purchaseNotes.trim() || undefined,
      });

      toast.success('Purchase recorded! Stock updated.');
      
      // Reset form
      setSelectedSupplier('');
      setPurchaseItems([]);
      setPurchaseNotes('');
      setActiveTab('history');
      
      // Reload data
      loadData();
    } catch (error) {
      toast.error(error.message || 'Failed to create purchase');
    } finally {
      setSaving(false);
    }
  };

  const handleDeletePurchase = async (purchase) => {
    if (!window.confirm(`Delete purchase ${purchase.purchase_number}?`)) return;
    
    try {
      await api.delete(`/purchases/${purchase.id}`);
      toast.success('Purchase deleted');
      loadPurchases();
    } catch (error) {
      toast.error(error.message || 'Only owners can delete purchases');
    }
  };

  return (
    <div className="p-4 space-y-4" data-testid="purchases-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Purchases
        </h1>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-3">
        <Card className="bg-gradient-to-br from-blue-50 to-blue-100 border-blue-200">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-blue-600 mb-1">
              <ShoppingBag className="h-4 w-4" />
              <span className="text-sm font-medium">Today</span>
            </div>
            <p className="text-2xl font-bold text-blue-700" style={{ fontFamily: 'Outfit, sans-serif' }}>
              {formatCurrency(stats.today_total)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-slate-600 mb-1">
              <Truck className="h-4 w-4" />
              <span className="text-sm font-medium">Suppliers</span>
            </div>
            <p className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
              {stats.supplier_count}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full grid grid-cols-2">
          <TabsTrigger value="new" data-testid="tab-new-purchase">
            <Plus className="h-4 w-4 mr-1" />
            New Purchase
          </TabsTrigger>
          <TabsTrigger value="history" data-testid="tab-history">
            <Calendar className="h-4 w-4 mr-1" />
            History
          </TabsTrigger>
        </TabsList>

        {/* New Purchase Tab */}
        <TabsContent value="new" className="space-y-4 mt-4">
          {/* Select Supplier */}
          <div className="space-y-2">
            <Label>Select Supplier *</Label>
            <Select value={selectedSupplier} onValueChange={setSelectedSupplier}>
              <SelectTrigger data-testid="select-supplier">
                <SelectValue placeholder="Choose a supplier" />
              </SelectTrigger>
              <SelectContent>
                {suppliers.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name} - {s.phone}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {suppliers.length === 0 && (
              <p className="text-sm text-amber-600">No suppliers yet. Add one first.</p>
            )}
          </div>

          {/* Items List */}
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">Items</CardTitle>
                <Button
                  size="sm"
                  className="bg-[#007BFF]"
                  onClick={() => setShowAddItem(true)}
                  data-testid="add-item-btn"
                >
                  <Plus className="h-4 w-4 mr-1" />
                  Add Item
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {purchaseItems.length === 0 ? (
                <div className="text-center py-8 text-slate-500">
                  <Package className="h-12 w-12 mx-auto mb-2 opacity-30" />
                  <p>No items added yet</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {purchaseItems.map((item, index) => (
                    <div 
                      key={index}
                      className="flex items-center justify-between p-3 bg-slate-50 rounded-lg"
                    >
                      <div className="flex-1">
                        <p className="font-medium">{item.product_name}</p>
                        <p className="text-sm text-slate-500">
                          {item.quantity} {item.unit_type} × {item.units_per_package} = {getTotalUnits(item)} units
                        </p>
                      </div>
                      <div className="text-right">
                        <p className="font-bold text-[#007BFF]">{formatCurrency(item.cost)}</p>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-6 w-6 text-red-500"
                          onClick={() => handleRemoveItem(index)}
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                  
                  {/* Total */}
                  <div className="flex justify-between items-center pt-3 border-t">
                    <span className="font-semibold">Total Cost</span>
                    <span className="text-xl font-bold text-[#007BFF]">
                      {formatCurrency(getTotalCost())}
                    </span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Notes */}
          <div className="space-y-2">
            <Label>Notes (Optional)</Label>
            <Input
              value={purchaseNotes}
              onChange={(e) => setPurchaseNotes(e.target.value)}
              placeholder="e.g., Weekly restock"
              data-testid="purchase-notes-input"
            />
          </div>

          {/* Submit Button */}
          <Button
            className="w-full h-12 bg-green-600 hover:bg-green-700"
            onClick={handleCreatePurchase}
            disabled={saving || purchaseItems.length === 0}
            data-testid="confirm-purchase-btn"
          >
            {saving ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Check className="mr-2 h-4 w-4" />
            )}
            Confirm Purchase ({formatCurrency(getTotalCost())})
          </Button>
        </TabsContent>

        {/* History Tab */}
        <TabsContent value="history" className="space-y-4 mt-4">
          {/* Filters */}
          <div className="flex gap-2">
            <Select value={filterSupplier} onValueChange={setFilterSupplier}>
              <SelectTrigger className="flex-1" data-testid="filter-supplier">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue placeholder="All Suppliers" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Suppliers</SelectItem>
                {suppliers.map((s) => (
                  <SelectItem key={s.id} value={s.id}>{s.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-xs">From Date</Label>
              <Input
                type="date"
                value={filterDateStart}
                onChange={(e) => setFilterDateStart(e.target.value)}
                data-testid="filter-date-start"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">To Date</Label>
              <Input
                type="date"
                value={filterDateEnd}
                onChange={(e) => setFilterDateEnd(e.target.value)}
                data-testid="filter-date-end"
              />
            </div>
          </div>

          {/* Purchases List */}
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-32 rounded-xl" />
              ))}
            </div>
          ) : purchases.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <ShoppingBag className="h-16 w-16 mx-auto mb-4 opacity-30" />
              <p className="font-medium">No purchases found</p>
            </div>
          ) : (
            <div className="space-y-3">
              {purchases.map((purchase) => (
                <Card key={purchase.id} data-testid={`purchase-card-${purchase.id}`}>
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
                            {purchase.purchase_number}
                          </span>
                          <span className="text-xs text-slate-500">
                            {formatDateTime(purchase.created_at)}
                          </span>
                        </div>
                        <p className="font-semibold mt-2">
                          <Truck className="h-4 w-4 inline mr-1" />
                          {purchase.supplier_name}
                        </p>
                        
                        {/* Items summary */}
                        <div className="mt-2 space-y-1">
                          {purchase.items.map((item, idx) => (
                            <p key={idx} className="text-sm text-slate-600">
                              • {item.product_name}: {item.quantity} {item.unit_type} ({item.quantity * item.units_per_package} units) - {formatCurrency(item.cost)}
                            </p>
                          ))}
                        </div>
                        
                        {purchase.notes && (
                          <p className="text-sm text-slate-500 mt-2 italic">"{purchase.notes}"</p>
                        )}
                      </div>
                      
                      <div className="text-right">
                        <p className="text-xl font-bold text-[#007BFF]">
                          {formatCurrency(purchase.total_cost)}
                        </p>
                        {isOwner && (
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8 text-red-500 mt-2"
                            onClick={() => handleDeletePurchase(purchase)}
                            data-testid={`delete-purchase-${purchase.id}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Add Item Modal */}
      <Dialog open={showAddItem} onOpenChange={setShowAddItem}>
        <DialogContent className="max-w-md mx-4">
          <DialogHeader>
            <DialogTitle>Add Purchase Item</DialogTitle>
            <DialogDescription>
              Select a product and enter purchase details
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Product *</Label>
              <Select 
                value={itemForm.product_id} 
                onValueChange={(v) => setItemForm({ ...itemForm, product_id: v })}
              >
                <SelectTrigger data-testid="item-product-select">
                  <SelectValue placeholder="Select product" />
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
            
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>Quantity</Label>
                <Input
                  type="number"
                  value={itemForm.quantity}
                  onChange={(e) => setItemForm({ ...itemForm, quantity: e.target.value })}
                  min="1"
                  data-testid="item-quantity-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Unit Type</Label>
                <Select 
                  value={itemForm.unit_type} 
                  onValueChange={(v) => {
                    let unitsPerPkg = '1';
                    if (v === 'dozens') unitsPerPkg = '12';
                    else if (v === 'packets') unitsPerPkg = '10';
                    else if (v === 'boxes') unitsPerPkg = '24';
                    setItemForm({ ...itemForm, unit_type: v, units_per_package: unitsPerPkg });
                  }}
                >
                  <SelectTrigger data-testid="item-unit-type-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="units">Units</SelectItem>
                    <SelectItem value="packets">Packets</SelectItem>
                    <SelectItem value="dozens">Dozens</SelectItem>
                    <SelectItem value="boxes">Boxes</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            
            {itemForm.unit_type !== 'units' && (
              <div className="space-y-2">
                <Label>Units per {itemForm.unit_type.slice(0, -1)}</Label>
                <Input
                  type="number"
                  value={itemForm.units_per_package}
                  onChange={(e) => setItemForm({ ...itemForm, units_per_package: e.target.value })}
                  min="1"
                  data-testid="item-units-per-package-input"
                />
              </div>
            )}
            
            <div className="space-y-2">
              <Label>Total Cost (KES) *</Label>
              <Input
                type="number"
                value={itemForm.cost}
                onChange={(e) => setItemForm({ ...itemForm, cost: e.target.value })}
                placeholder="0"
                data-testid="item-cost-input"
              />
            </div>

            {itemForm.cost && itemForm.quantity && (
              <div className="p-3 bg-blue-50 rounded-lg text-sm">
                <p className="text-blue-700">
                  <strong>Total units:</strong> {parseInt(itemForm.quantity || 0) * parseInt(itemForm.units_per_package || 1)} units
                </p>
                <p className="text-blue-700">
                  <strong>Cost per unit:</strong> {formatCurrency(parseFloat(itemForm.cost || 0) / (parseInt(itemForm.quantity || 1) * parseInt(itemForm.units_per_package || 1)))}
                </p>
              </div>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowAddItem(false)}>
              Cancel
            </Button>
            <Button 
              className="bg-[#007BFF]"
              onClick={handleAddItem}
              data-testid="confirm-add-item-btn"
            >
              <Check className="mr-2 h-4 w-4" />
              Add Item
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
