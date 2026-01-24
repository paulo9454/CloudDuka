import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuthStore, api, formatCurrency } from '../lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Skeleton } from '../components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import { 
  Search, 
  Plus, 
  Package, 
  Edit2, 
  Trash2, 
  AlertTriangle,
  Loader2,
  Check,
  FolderOpen,
  Tag
} from 'lucide-react';

const UNITS = ['piece', 'kg', 'gram', 'liter', 'ml', 'pack', 'box', 'dozen'];

const DEFAULT_CATEGORY_COLORS = [
  '#007BFF', '#FF8C00', '#10B981', '#8B5CF6', '#EC4899', 
  '#F59E0B', '#06B6D4', '#EF4444', '#84CC16', '#6366F1'
];

export default function ProductsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { user } = useAuthStore();
  const isOwner = user?.role === 'owner';
  
  const [activeTab, setActiveTab] = useState('products');
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterLowStock, setFilterLowStock] = useState(searchParams.get('filter') === 'low-stock');
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState('all');
  
  // Product Modal state
  const [showProductModal, setShowProductModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);
  const [savingProduct, setSavingProduct] = useState(false);
  
  // Category Modal state
  const [showCategoryModal, setShowCategoryModal] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);
  const [savingCategory, setSavingCategory] = useState(false);
  
  // Product Form state
  const [productForm, setProductForm] = useState({
    name: '',
    sku: '',
    category: '',
    unit_price: '',
    cost_price: '',
    stock_quantity: '',
    min_stock_level: '5',
    unit: 'piece',
  });
  
  // Category Form state
  const [categoryForm, setCategoryForm] = useState({
    name: '',
    description: '',
    color: '#007BFF',
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
      const data = await api.get('/categories');
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
    const matchesCategory = selectedCategoryFilter === 'all' || 
      (selectedCategoryFilter === 'other' && (!p.category || p.category === '')) ||
      p.category === selectedCategoryFilter;
    return matchesSearch && matchesLowStock && matchesCategory;
  });

  // Product handlers
  const handleOpenProductModal = (product = null) => {
    if (product) {
      setEditingProduct(product);
      setProductForm({
        name: product.name,
        sku: product.sku || '',
        category: product.category || '',
        unit_price: product.unit_price.toString(),
        cost_price: product.cost_price?.toString() || '',
        stock_quantity: product.stock_quantity.toString(),
        min_stock_level: product.min_stock_level.toString(),
        unit: product.unit,
      });
    } else {
      setEditingProduct(null);
      setProductForm({
        name: '',
        sku: '',
        category: '',
        unit_price: '',
        cost_price: '',
        stock_quantity: '',
        min_stock_level: '5',
        unit: 'piece',
      });
    }
    setShowProductModal(true);
  };

  const handleSaveProduct = async () => {
    if (!productForm.name || !productForm.unit_price) {
      toast.error('Name and price are required');
      return;
    }

    setSavingProduct(true);
    try {
      const data = {
        name: productForm.name,
        sku: productForm.sku || undefined,
        category: productForm.category || undefined,
        unit_price: parseFloat(productForm.unit_price),
        cost_price: productForm.cost_price ? parseFloat(productForm.cost_price) : undefined,
        stock_quantity: parseInt(productForm.stock_quantity) || 0,
        min_stock_level: parseInt(productForm.min_stock_level) || 5,
        unit: productForm.unit,
      };

      if (editingProduct) {
        await api.put(`/products/${editingProduct.id}`, data);
        toast.success('Product updated');
      } else {
        await api.post('/products', data);
        toast.success('Product added');
      }

      setShowProductModal(false);
      loadProducts();
      loadCategories();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSavingProduct(false);
    }
  };

  const handleDeleteProduct = async (product) => {
    if (!window.confirm(`Delete "${product.name}"?`)) return;
    
    try {
      await api.delete(`/products/${product.id}`);
      toast.success('Product deleted');
      loadProducts();
      loadCategories();
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

  // Category handlers
  const handleOpenCategoryModal = (category = null) => {
    if (category && category.id !== 'other') {
      setEditingCategory(category);
      setCategoryForm({
        name: category.name,
        description: category.description || '',
        color: category.color || '#007BFF',
      });
    } else {
      setEditingCategory(null);
      setCategoryForm({
        name: '',
        description: '',
        color: DEFAULT_CATEGORY_COLORS[categories.length % DEFAULT_CATEGORY_COLORS.length],
      });
    }
    setShowCategoryModal(true);
  };

  const handleSaveCategory = async () => {
    if (!categoryForm.name) {
      toast.error('Category name is required');
      return;
    }

    setSavingCategory(true);
    try {
      if (editingCategory) {
        await api.put(`/categories/${editingCategory.id}`, categoryForm);
        toast.success('Category updated');
      } else {
        await api.post('/categories', categoryForm);
        toast.success('Category created');
      }

      setShowCategoryModal(false);
      loadCategories();
      loadProducts();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSavingCategory(false);
    }
  };

  const handleDeleteCategory = async (category) => {
    if (category.id === 'other') {
      toast.error('Cannot delete the "Other" category');
      return;
    }
    if (!window.confirm(`Delete "${category.name}"? Products will become uncategorized.`)) return;
    
    try {
      await api.delete(`/categories/${category.id}`);
      toast.success('Category deleted');
      loadCategories();
      loadProducts();
    } catch (error) {
      toast.error(error.message);
    }
  };

  const getCategoryNames = () => {
    return categories.filter(c => c.id !== 'other').map(c => c.name);
  };

  return (
    <div className="p-4 space-y-4" data-testid="products-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Products
        </h1>
      </div>

      {/* Tabs for Products/Categories */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full grid grid-cols-2">
          <TabsTrigger value="products" data-testid="products-tab">
            <Package className="h-4 w-4 mr-1" />
            Products
          </TabsTrigger>
          <TabsTrigger value="categories" data-testid="categories-tab">
            <FolderOpen className="h-4 w-4 mr-1" />
            Categories
          </TabsTrigger>
        </TabsList>

        {/* Products Tab */}
        <TabsContent value="products" className="space-y-4 mt-4">
          {/* Actions Row */}
          <div className="flex gap-2">
            <Button 
              className="bg-[#007BFF] rounded-full"
              onClick={() => handleOpenProductModal()}
              data-testid="add-product-btn"
            >
              <Plus className="mr-1 h-4 w-4" />
              Add Product
            </Button>
          </div>

          {/* Search and Filters */}
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

          {/* Category Filter */}
          {categories.length > 0 && (
            <div className="flex gap-2 overflow-x-auto pb-2">
              <Button
                variant={selectedCategoryFilter === 'all' ? 'default' : 'outline'}
                size="sm"
                className={`rounded-full whitespace-nowrap ${selectedCategoryFilter === 'all' ? 'bg-[#007BFF]' : ''}`}
                onClick={() => setSelectedCategoryFilter('all')}
                data-testid="filter-category-all"
              >
                All
              </Button>
              {categories.map((cat) => (
                <Button
                  key={cat.id}
                  variant={selectedCategoryFilter === (cat.id === 'other' ? 'other' : cat.name) ? 'default' : 'outline'}
                  size="sm"
                  className="rounded-full whitespace-nowrap"
                  style={selectedCategoryFilter === (cat.id === 'other' ? 'other' : cat.name) ? { backgroundColor: cat.color } : {}}
                  onClick={() => setSelectedCategoryFilter(cat.id === 'other' ? 'other' : cat.name)}
                  data-testid={`filter-category-${cat.id}`}
                >
                  {cat.name} ({cat.product_count})
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
                onClick={() => handleOpenProductModal()}
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
                        <div className="flex items-center gap-2 flex-wrap">
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
                        <div className="flex items-center gap-4 mt-2 flex-wrap">
                          <span className="text-lg font-bold text-[#007BFF]">
                            {formatCurrency(product.unit_price)}
                          </span>
                          {product.category && (
                            <span 
                              className="px-2 py-0.5 rounded-full text-xs text-white"
                              style={{ 
                                backgroundColor: categories.find(c => c.name === product.category)?.color || '#6B7280' 
                              }}
                            >
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
                        <span className="text-xs text-slate-500">{product.unit}</span>
                        
                        <div className="flex gap-1 mt-1">
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8"
                            onClick={() => handleOpenProductModal(product)}
                            data-testid={`edit-product-${product.id}`}
                          >
                            <Edit2 className="h-4 w-4" />
                          </Button>
                          {isOwner && (
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-8 w-8 text-red-500"
                              onClick={() => handleDeleteProduct(product)}
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
        </TabsContent>

        {/* Categories Tab */}
        <TabsContent value="categories" className="space-y-4 mt-4">
          {isOwner && (
            <Button 
              className="bg-[#FF8C00] rounded-full"
              onClick={() => handleOpenCategoryModal()}
              data-testid="add-category-btn"
            >
              <Plus className="mr-1 h-4 w-4" />
              Add Category
            </Button>
          )}

          {categories.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <FolderOpen className="h-16 w-16 mx-auto mb-4 opacity-30" />
              <p className="font-medium">No categories yet</p>
              {isOwner && (
                <Button 
                  className="mt-4 bg-[#FF8C00]"
                  onClick={() => handleOpenCategoryModal()}
                >
                  Create First Category
                </Button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {categories.map((category) => (
                <Card 
                  key={category.id}
                  className="overflow-hidden"
                  data-testid={`category-card-${category.id}`}
                >
                  <div 
                    className="h-2" 
                    style={{ backgroundColor: category.color }}
                  />
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div>
                        <h3 className="font-semibold flex items-center gap-2">
                          <Tag className="h-4 w-4" style={{ color: category.color }} />
                          {category.name}
                        </h3>
                        {category.description && (
                          <p className="text-sm text-slate-500 mt-1">{category.description}</p>
                        )}
                        <p className="text-sm font-medium mt-2">
                          {category.product_count} product{category.product_count !== 1 ? 's' : ''}
                        </p>
                      </div>
                      
                      {isOwner && category.id !== 'other' && (
                        <div className="flex gap-1">
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8"
                            onClick={() => handleOpenCategoryModal(category)}
                            data-testid={`edit-category-${category.id}`}
                          >
                            <Edit2 className="h-4 w-4" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8 text-red-500"
                            onClick={() => handleDeleteCategory(category)}
                            data-testid={`delete-category-${category.id}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Add/Edit Product Modal */}
      <Dialog open={showProductModal} onOpenChange={setShowProductModal}>
        <DialogContent className="max-w-md mx-4 max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingProduct ? 'Edit Product' : 'Add Product'}</DialogTitle>
            <DialogDescription className="sr-only">
              {editingProduct ? 'Edit product details' : 'Add a new product to your inventory'}
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Product Name *</Label>
              <Input
                value={productForm.name}
                onChange={(e) => setProductForm({ ...productForm, name: e.target.value })}
                placeholder="e.g., Milk 500ml"
                data-testid="product-name-input"
              />
            </div>

            <div className="space-y-2">
              <Label>Category</Label>
              <Select 
                value={productForm.category} 
                onValueChange={(v) => setProductForm({ ...productForm, category: v })}
              >
                <SelectTrigger data-testid="product-category-select">
                  <SelectValue placeholder="Select category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">No Category</SelectItem>
                  {getCategoryNames().map((name) => (
                    <SelectItem key={name} value={name}>{name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Selling Price *</Label>
                <Input
                  type="number"
                  value={productForm.unit_price}
                  onChange={(e) => setProductForm({ ...productForm, unit_price: e.target.value })}
                  placeholder="0"
                  data-testid="product-price-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Cost Price</Label>
                <Input
                  type="number"
                  value={productForm.cost_price}
                  onChange={(e) => setProductForm({ ...productForm, cost_price: e.target.value })}
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
                  value={productForm.stock_quantity}
                  onChange={(e) => setProductForm({ ...productForm, stock_quantity: e.target.value })}
                  placeholder="0"
                  data-testid="product-stock-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Min Stock Level</Label>
                <Input
                  type="number"
                  value={productForm.min_stock_level}
                  onChange={(e) => setProductForm({ ...productForm, min_stock_level: e.target.value })}
                  placeholder="5"
                  data-testid="product-min-stock-input"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Unit</Label>
                <Select value={productForm.unit} onValueChange={(v) => setProductForm({ ...productForm, unit: v })}>
                  <SelectTrigger data-testid="product-unit-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {UNITS.map((u) => (
                      <SelectItem key={u} value={u}>{u}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>SKU (Optional)</Label>
                <Input
                  value={productForm.sku}
                  onChange={(e) => setProductForm({ ...productForm, sku: e.target.value })}
                  placeholder="Auto-generated"
                  data-testid="product-sku-input"
                />
              </div>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowProductModal(false)}>
              Cancel
            </Button>
            <Button 
              className="bg-[#007BFF]"
              onClick={handleSaveProduct}
              disabled={savingProduct}
              data-testid="save-product-btn"
            >
              {savingProduct ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
              {editingProduct ? 'Update' : 'Add Product'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add/Edit Category Modal */}
      <Dialog open={showCategoryModal} onOpenChange={setShowCategoryModal}>
        <DialogContent className="max-w-md mx-4">
          <DialogHeader>
            <DialogTitle>{editingCategory ? 'Edit Category' : 'Create Category'}</DialogTitle>
            <DialogDescription className="sr-only">
              {editingCategory ? 'Edit category details' : 'Create a new product category'}
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Category Name *</Label>
              <Input
                value={categoryForm.name}
                onChange={(e) => setCategoryForm({ ...categoryForm, name: e.target.value })}
                placeholder="e.g., Beverages"
                data-testid="category-name-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Description (Optional)</Label>
              <Input
                value={categoryForm.description}
                onChange={(e) => setCategoryForm({ ...categoryForm, description: e.target.value })}
                placeholder="e.g., Drinks and refreshments"
                data-testid="category-description-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Color</Label>
              <div className="flex gap-2 flex-wrap">
                {DEFAULT_CATEGORY_COLORS.map((color) => (
                  <button
                    key={color}
                    type="button"
                    className={`w-8 h-8 rounded-full transition-transform ${categoryForm.color === color ? 'ring-2 ring-offset-2 ring-slate-400 scale-110' : ''}`}
                    style={{ backgroundColor: color }}
                    onClick={() => setCategoryForm({ ...categoryForm, color })}
                    data-testid={`color-${color}`}
                  />
                ))}
              </div>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowCategoryModal(false)}>
              Cancel
            </Button>
            <Button 
              className="bg-[#FF8C00]"
              onClick={handleSaveCategory}
              disabled={savingCategory}
              data-testid="save-category-btn"
            >
              {savingCategory ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
              {editingCategory ? 'Update' : 'Create Category'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
