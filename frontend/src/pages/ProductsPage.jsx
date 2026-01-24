import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuthStore, api, formatCurrency } from '../lib/store';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../components/ui/dialog';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import { 
  Search, 
  Plus, 
  Package, 
  Edit2, 
  Trash2, 
  AlertTriangle,
  Loader2,
  Check
} from 'lucide-react';

export default function ProductsPage() {
  const [searchParams] = useSearchParams();
  const { user } = useAuthStore();
  const isOwner = user?.role === 'owner';
  
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterLowStock, setFilterLowStock] = useState(searchParams.get('filter') === 'low-stock');
  const [selectedCategory, setSelectedCategory] = useState('all');
  
  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [saving, setSaving] = useState(false);
  
  // Simple form state - retail unit only
  const [formData, setFormData] = useState({
    name: '',
    sku: '',
    category: '',
    unit_price: '',
    cost_price: '',
    stock_quantity: '',
    min_stock_level: '5',
  });

  useEffect(() => {
    loadProducts();
    loadCategories();
  }, []);

  const loadProducts = async () => {
    try {
      const data = await api.get('/products');
      setProducts(data);
    } catch (error) {
      toast.error('Failed to load products');
    } finally {
      setLoading(false);
    }
  };

  const loadCategories = async () => {
    try {
      const data = await api.get('/products/categories/list');
      setCategories(data);
    } catch (error) {
      console.error('Failed to load categories');
    }
  };

  const filteredProducts = products.filter((p) => {
    const matchesSearch = !searchQuery || 
      p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.sku && p.sku.toLowerCase().includes(searchQuery.toLowerCase()));
    const matchesLowStock = !filterLowStock || p.stock_quantity <= p.min_stock_level;
    const matchesCategory = selectedCategory === 'all' || p.category === selectedCategory;
    return matchesSearch && matchesLowStock && matchesCategory;
  });

  const handleOpenModal = (product = null) => {
    if (product) {
      setEditingProduct(product);
      setFormData({
        name: product.name,
        sku: product.sku || '',
        category: product.category || '',
        unit_price: product.unit_price.toString(),
        cost_price: product.cost_price?.toString() || '',
        stock_quantity: product.stock_quantity.toString(),
        min_stock_level: product.min_stock_level.toString(),
      });
    } else {
      setEditingProduct(null);
      setFormData({
        name: '',
        sku: '',
        category: '',
        unit_price: '',
        cost_price: '',
        stock_quantity: '',
        min_stock_level: '5',
      });
    }
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!formData.name || !formData.unit_price) {
      toast.error('Name and selling price are required');
      return;
    }

    setSaving(true);
    try {
      const data = {
        name: formData.name,
        sku: formData.sku || undefined,
        category: formData.category || undefined,
        unit_price: parseFloat(formData.unit_price),
        cost_price: formData.cost_price ? parseFloat(formData.cost_price) : undefined,
        stock_quantity: parseInt(formData.stock_quantity) || 0,
        min_stock_level: parseInt(formData.min_stock_level) || 5,
        unit: 'piece', // Always retail unit
      };

      if (editingProduct) {
        await api.put(`/products/${editingProduct.id}`, data);
        toast.success('Product updated');
      } else {
        await api.post('/products', data);
        toast.success('Product added');
      }

      setShowModal(false);
      loadProducts();
      loadCategories();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (product) => {
    if (!window.confirm(`Delete "${product.name}"?`)) return;
    
    try {
      await api.delete(`/products/${product.id}`);
      toast.success('Product deleted');
      loadProducts();
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleUpdateStock = async (product, newQuantity) => {
    try {
      await api.put(`/products/${product.id}`, { stock_quantity: newQuantity });
      loadProducts();
    } catch (error) {
      toast.error('Failed to update stock');
    }
  };

  return (
    <div className="p-4 space-y-4" data-testid="products-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Products
        </h1>
        <Button 
          className="bg-[#007BFF] rounded-full"
          onClick={() => handleOpenModal()}
          data-testid="add-product-btn"
        >
          <Plus className="mr-1 h-4 w-4" />
          Add
        </Button>
      </div>

      {/* Search and Filter */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
          <Input
            placeholder="Search products..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10"
            data-testid="search-products-input"
          />
        </div>
        <Button
          variant={filterLowStock ? 'default' : 'outline'}
          className={filterLowStock ? 'bg-amber-500' : ''}
          onClick={() => setFilterLowStock(!filterLowStock)}
          data-testid="filter-low-stock-btn"
        >
          <AlertTriangle className="h-4 w-4" />
        </Button>
      </div>

      {/* Category Filter - Simple chips */}
      {categories.length > 0 && (
        <div className="flex gap-2 overflow-x-auto pb-2">
          <Button
            variant={selectedCategory === 'all' ? 'default' : 'outline'}
            size="sm"
            className={`rounded-full whitespace-nowrap ${selectedCategory === 'all' ? 'bg-[#007BFF]' : ''}`}
            onClick={() => setSelectedCategory('all')}
            data-testid="filter-all-btn"
          >
            All
          </Button>
          {categories.map((cat) => (
            <Button
              key={cat}
              variant={selectedCategory === cat ? 'default' : 'outline'}
              size="sm"
              className={`rounded-full whitespace-nowrap ${selectedCategory === cat ? 'bg-[#007BFF]' : ''}`}
              onClick={() => setSelectedCategory(cat)}
              data-testid={`filter-${cat}-btn`}
            >
              {cat}
            </Button>
          ))}
        </div>
      )}

      {/* Products List */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      ) : filteredProducts.length === 0 ? (
        <div className="text-center py-12 text-slate-500">
          <Package className="h-16 w-16 mx-auto mb-4 opacity-30" />
          <p className="font-medium">No products found</p>
          <Button 
            className="mt-4 bg-[#007BFF]"
            onClick={() => handleOpenModal()}
          >
            Add First Product
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredProducts.map((product) => (
            <Card 
              key={product.id} 
              className={`${product.stock_quantity <= product.min_stock_level ? 'border-amber-300 bg-amber-50/50' : ''}`}
              data-testid={`product-item-${product.id}`}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="font-semibold">{product.name}</h3>
                      {product.stock_quantity <= product.min_stock_level && (
                        <span className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-xs">
                          Low Stock
                        </span>
                      )}
                    </div>
                    {product.sku && (
                      <p className="text-sm text-slate-500">SKU: {product.sku}</p>
                    )}
                    <div className="flex items-center gap-4 mt-2">
                      <span className="text-lg font-bold text-[#007BFF]">
                        {formatCurrency(product.unit_price)}
                      </span>
                      {product.category && (
                        <span className="text-sm text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                          {product.category}
                        </span>
                      )}
                    </div>
                  </div>
                  
                  <div className="flex flex-col items-end gap-2">
                    <div className="flex items-center gap-2">
                      <Button
                        size="icon"
                        variant="outline"
                        className="h-8 w-8"
                        onClick={() => handleUpdateStock(product, Math.max(0, product.stock_quantity - 1))}
                        data-testid={`stock-minus-${product.id}`}
                      >
                        -
                      </Button>
                      <span className="w-12 text-center font-bold">{product.stock_quantity}</span>
                      <Button
                        size="icon"
                        variant="outline"
                        className="h-8 w-8"
                        onClick={() => handleUpdateStock(product, product.stock_quantity + 1)}
                        data-testid={`stock-plus-${product.id}`}
                      >
                        +
                      </Button>
                    </div>
                    <span className="text-xs text-slate-500">units</span>
                    
                    <div className="flex gap-1 mt-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8"
                        onClick={() => handleOpenModal(product)}
                        data-testid={`edit-product-${product.id}`}
                      >
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      {isOwner && (
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-8 w-8 text-red-500"
                          onClick={() => handleDelete(product)}
                          data-testid={`delete-product-${product.id}`}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Add/Edit Product Modal - Simple fields only */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-w-md mx-4 max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingProduct ? 'Edit Product' : 'Add Product'}</DialogTitle>
            <DialogDescription className="sr-only">
              Enter product details
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Product Name *</Label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Milk 500ml"
                data-testid="product-name-input"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Selling Price *</Label>
                <Input
                  type="number"
                  value={formData.unit_price}
                  onChange={(e) => setFormData({ ...formData, unit_price: e.target.value })}
                  placeholder="0"
                  data-testid="product-price-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Cost Price</Label>
                <Input
                  type="number"
                  value={formData.cost_price}
                  onChange={(e) => setFormData({ ...formData, cost_price: e.target.value })}
                  placeholder="0"
                  data-testid="product-cost-input"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Stock Quantity</Label>
                <Input
                  type="number"
                  value={formData.stock_quantity}
                  onChange={(e) => setFormData({ ...formData, stock_quantity: e.target.value })}
                  placeholder="0"
                  data-testid="product-stock-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Min Stock Level</Label>
                <Input
                  type="number"
                  value={formData.min_stock_level}
                  onChange={(e) => setFormData({ ...formData, min_stock_level: e.target.value })}
                  placeholder="5"
                  data-testid="product-min-stock-input"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Category (Optional)</Label>
              <Input
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                placeholder="e.g., Beverages, Snacks"
                list="categories"
                data-testid="product-category-input"
              />
              <datalist id="categories">
                {categories.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
              <p className="text-xs text-slate-500">For filtering only - optional</p>
            </div>

            <div className="space-y-2">
              <Label>SKU (Optional)</Label>
              <Input
                value={formData.sku}
                onChange={(e) => setFormData({ ...formData, sku: e.target.value })}
                placeholder="Auto-generated if empty"
                data-testid="product-sku-input"
              />
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowModal(false)}>
              Cancel
            </Button>
            <Button 
              className="bg-[#007BFF]"
              onClick={handleSave}
              disabled={saving}
              data-testid="save-product-btn"
            >
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
              {editingProduct ? 'Update' : 'Add Product'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
