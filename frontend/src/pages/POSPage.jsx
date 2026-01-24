import React, { useState, useEffect, useMemo } from 'react';
import { useAuthStore, useCartStore, api, formatCurrency, useOfflineStore } from '../lib/store';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import { 
  Search, 
  Plus, 
  Minus, 
  Trash2, 
  ShoppingCart, 
  Wallet, 
  Smartphone, 
  CreditCard,
  Check,
  Loader2,
  Package
} from 'lucide-react';

export default function POSPage() {
  const { user } = useAuthStore();
  const { items, addItem, updateQuantity, removeItem, clearCart, getTotal } = useCartStore();
  const { isOnline, addPendingSale } = useOfflineStore();
  
  const [products, setProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('all');
  
  // Payment modal state
  const [showPayment, setShowPayment] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [amountReceived, setAmountReceived] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [creditCustomers, setCreditCustomers] = useState([]);
  const [processing, setProcessing] = useState(false);
  
  // M-Pesa modal state
  const [showMpesaConfirm, setShowMpesaConfirm] = useState(false);
  const [mpesaCheckoutId, setMpesaCheckoutId] = useState(null);

  useEffect(() => {
    loadProducts();
    loadCategories();
    loadCreditCustomers();
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

  const loadCreditCustomers = async () => {
    try {
      const data = await api.get('/credit-customers');
      setCreditCustomers(data);
    } catch (error) {
      console.error('Failed to load credit customers');
    }
  };

  const filteredProducts = useMemo(() => {
    return products.filter((p) => {
      const matchesSearch = !searchQuery || 
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (p.sku && p.sku.toLowerCase().includes(searchQuery.toLowerCase()));
      const matchesCategory = selectedCategory === 'all' || p.category === selectedCategory;
      return matchesSearch && matchesCategory;
    });
  }, [products, searchQuery, selectedCategory]);

  const handleAddToCart = (product) => {
    if (product.stock_quantity <= 0) {
      toast.error('Out of stock');
      return;
    }
    const cartItem = items.find((i) => i.product_id === product.id);
    if (cartItem && cartItem.quantity >= product.stock_quantity) {
      toast.error('Not enough stock');
      return;
    }
    addItem(product);
    toast.success(`${product.name} added`);
  };

  const handleCheckout = () => {
    if (items.length === 0) {
      toast.error('Cart is empty');
      return;
    }
    setShowPayment(true);
    setPaymentMethod('cash');
    setAmountReceived('');
    setCustomerPhone('');
    setSelectedCustomer(null);
  };

  const handleProcessPayment = async () => {
    const total = getTotal();
    
    if (paymentMethod === 'cash') {
      const received = parseFloat(amountReceived) || 0;
      if (received < total) {
        toast.error('Amount received is less than total');
        return;
      }
    }
    
    if (paymentMethod === 'credit' && !selectedCustomer) {
      toast.error('Please select a credit customer');
      return;
    }
    
    if (paymentMethod === 'mpesa' && !customerPhone) {
      toast.error('Please enter customer phone for M-Pesa');
      return;
    }

    setProcessing(true);
    
    try {
      const saleData = {
        items: items.map((i) => ({
          product_id: i.product_id,
          product_name: i.product_name,
          quantity: i.quantity,
          unit_price: i.unit_price,
          total: i.total,
        })),
        payment_method: paymentMethod,
        total_amount: total,
        customer_id: paymentMethod === 'credit' ? selectedCustomer : null,
        customer_phone: paymentMethod === 'mpesa' ? customerPhone : null,
        amount_paid: paymentMethod === 'cash' ? parseFloat(amountReceived) : total,
        change_amount: paymentMethod === 'cash' ? (parseFloat(amountReceived) || 0) - total : 0,
      };

      if (!isOnline) {
        addPendingSale(saleData);
        toast.success('Sale saved offline. Will sync when online.');
        clearCart();
        setShowPayment(false);
        return;
      }

      const sale = await api.post('/sales', saleData);
      
      if (paymentMethod === 'mpesa') {
        const mpesaRes = await api.post('/mpesa/stk-push', {
          phone: customerPhone,
          amount: total,
          sale_id: sale.id,
        });
        setMpesaCheckoutId(mpesaRes.checkout_request_id);
        setShowPayment(false);
        setShowMpesaConfirm(true);
      } else {
        toast.success('Sale completed!', {
          description: `Receipt: ${sale.receipt_number}`,
        });
        clearCart();
        setShowPayment(false);
        loadProducts();
      }
    } catch (error) {
      toast.error(error.message || 'Failed to process sale');
    } finally {
      setProcessing(false);
    }
  };

  const handleConfirmMpesa = async () => {
    setProcessing(true);
    try {
      await api.post(`/mpesa/confirm/${mpesaCheckoutId}`);
      toast.success('M-Pesa payment confirmed!');
      clearCart();
      setShowMpesaConfirm(false);
      loadProducts();
    } catch (error) {
      toast.error('Failed to confirm M-Pesa payment');
    } finally {
      setProcessing(false);
    }
  };

  const total = getTotal();
  const changeAmount = paymentMethod === 'cash' ? (parseFloat(amountReceived) || 0) - total : 0;

  return (
    <div className="flex flex-col h-full" data-testid="pos-page">
      {/* Search Header */}
      <div className="p-4 bg-white border-b sticky top-0 z-10">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
          <Input
            placeholder="Search products..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 h-12 bg-slate-50"
            data-testid="pos-search-input"
          />
        </div>
        
        {/* Category Filter - Simple optional chips */}
        {categories.length > 0 && (
          <div className="flex gap-2 mt-3 overflow-x-auto pb-2">
            <Button
              variant={selectedCategory === 'all' ? 'default' : 'outline'}
              size="sm"
              className={`rounded-full whitespace-nowrap ${selectedCategory === 'all' ? 'bg-[#007BFF]' : ''}`}
              onClick={() => setSelectedCategory('all')}
              data-testid="category-all-btn"
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
                data-testid={`category-${cat}-btn`}
              >
                {cat}
              </Button>
            ))}
          </div>
        )}
      </div>

      {/* Products Grid */}
      <div className="flex-1 overflow-y-auto p-4 pb-40">
        {loading ? (
          <div className="grid grid-cols-2 gap-3">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <Skeleton key={i} className="h-32 rounded-xl" />
            ))}
          </div>
        ) : filteredProducts.length === 0 ? (
          <div className="text-center py-12 text-slate-500">
            <Package className="h-16 w-16 mx-auto mb-4 opacity-30" />
            <p className="font-medium">No products found</p>
            <p className="text-sm mt-1">Try a different search or category</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3">
            {filteredProducts.map((product) => (
              <Card 
                key={product.id}
                className={`cursor-pointer transition-all active:scale-95 ${
                  product.stock_quantity <= 0 ? 'opacity-50' : 'hover:border-[#007BFF]/50'
                }`}
                onClick={() => handleAddToCart(product)}
                data-testid={`product-card-${product.id}`}
              >
                <CardContent className="p-3">
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-medium text-sm truncate">{product.name}</h3>
                      <p className="text-lg font-bold text-[#007BFF] mt-1">
                        {formatCurrency(product.unit_price)}
                      </p>
                    </div>
                    <div className={`p-2 rounded-lg ${
                      product.stock_quantity <= product.min_stock_level 
                        ? 'bg-amber-100 text-amber-700' 
                        : 'bg-slate-100'
                    }`}>
                      <span className="text-xs font-medium">{product.stock_quantity}</span>
                    </div>
                  </div>
                  <div className="flex items-center justify-between mt-2">
                    <span className="text-xs text-slate-500">
                      {product.category || 'No category'}
                    </span>
                    <Plus className="h-5 w-5 text-[#007BFF]" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Cart Summary - Fixed at bottom */}
      {items.length > 0 && (
        <div className="fixed bottom-16 left-0 right-0 bg-white border-t shadow-lg p-4 z-20">
          <div className="max-w-md mx-auto">
            {/* Cart Items Preview */}
            <div className="max-h-40 overflow-y-auto mb-4 space-y-2">
              {items.map((item) => (
                <div 
                  key={item.product_id} 
                  className="flex items-center justify-between bg-slate-50 rounded-lg p-2 cart-item"
                  data-testid={`cart-item-${item.product_id}`}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{item.product_name}</p>
                    <p className="text-xs text-slate-500">{formatCurrency(item.unit_price)} × {item.quantity}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="icon"
                      variant="outline"
                      className="h-8 w-8"
                      onClick={(e) => { e.stopPropagation(); updateQuantity(item.product_id, item.quantity - 1); }}
                      data-testid={`cart-minus-${item.product_id}`}
                    >
                      <Minus className="h-4 w-4" />
                    </Button>
                    <span className="w-8 text-center font-medium">{item.quantity}</span>
                    <Button
                      size="icon"
                      variant="outline"
                      className="h-8 w-8"
                      onClick={(e) => { 
                        e.stopPropagation(); 
                        if (item.quantity < item.stock_quantity) {
                          updateQuantity(item.product_id, item.quantity + 1);
                        } else {
                          toast.error('Not enough stock');
                        }
                      }}
                      data-testid={`cart-plus-${item.product_id}`}
                    >
                      <Plus className="h-4 w-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8 text-red-500"
                      onClick={(e) => { e.stopPropagation(); removeItem(item.product_id); }}
                      data-testid={`cart-remove-${item.product_id}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
            
            {/* Total and Checkout */}
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500">Total ({items.length} items)</p>
                <p className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
                  {formatCurrency(total)}
                </p>
              </div>
              <Button 
                className="h-12 px-6 bg-[#007BFF] hover:bg-[#0069D9] rounded-full"
                onClick={handleCheckout}
                data-testid="checkout-btn"
              >
                <ShoppingCart className="mr-2 h-5 w-5" />
                Checkout
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Payment Modal */}
      <Dialog open={showPayment} onOpenChange={setShowPayment}>
        <DialogContent className="max-w-md mx-4">
          <DialogHeader>
            <DialogTitle className="text-xl">Select Payment Method</DialogTitle>
            <DialogDescription className="sr-only">Choose how you want to complete this sale</DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            {/* Payment Method Selection */}
            <div className="grid grid-cols-3 gap-3">
              <Button
                variant={paymentMethod === 'cash' ? 'default' : 'outline'}
                className={`h-20 flex-col gap-2 ${paymentMethod === 'cash' ? 'bg-green-600' : ''}`}
                onClick={() => setPaymentMethod('cash')}
                data-testid="payment-cash-btn"
              >
                <Wallet className="h-6 w-6" />
                Cash
              </Button>
              <Button
                variant={paymentMethod === 'mpesa' ? 'default' : 'outline'}
                className={`h-20 flex-col gap-2 ${paymentMethod === 'mpesa' ? 'bg-emerald-600' : ''}`}
                onClick={() => setPaymentMethod('mpesa')}
                data-testid="payment-mpesa-btn"
              >
                <Smartphone className="h-6 w-6" />
                M-Pesa
              </Button>
              <Button
                variant={paymentMethod === 'credit' ? 'default' : 'outline'}
                className={`h-20 flex-col gap-2 ${paymentMethod === 'credit' ? 'bg-orange-600' : ''}`}
                onClick={() => setPaymentMethod('credit')}
                data-testid="payment-credit-btn"
              >
                <CreditCard className="h-6 w-6" />
                Credit
              </Button>
            </div>

            {/* Total Display */}
            <div className="text-center py-4 bg-slate-50 rounded-xl">
              <p className="text-sm text-slate-500">Amount Due</p>
              <p className="text-3xl font-bold text-[#007BFF]" style={{ fontFamily: 'Outfit, sans-serif' }}>
                {formatCurrency(total)}
              </p>
            </div>

            {/* Cash Payment Fields */}
            {paymentMethod === 'cash' && (
              <div className="space-y-3">
                <Input
                  type="number"
                  placeholder="Amount received"
                  value={amountReceived}
                  onChange={(e) => setAmountReceived(e.target.value)}
                  className="h-14 text-lg text-center"
                  data-testid="cash-amount-input"
                />
                {changeAmount > 0 && (
                  <div className="text-center p-3 bg-green-50 rounded-lg">
                    <p className="text-sm text-green-600">Change</p>
                    <p className="text-2xl font-bold text-green-700">{formatCurrency(changeAmount)}</p>
                  </div>
                )}
              </div>
            )}

            {/* M-Pesa Fields */}
            {paymentMethod === 'mpesa' && (
              <div className="space-y-3">
                <Input
                  type="tel"
                  placeholder="Customer phone (254...)"
                  value={customerPhone}
                  onChange={(e) => setCustomerPhone(e.target.value)}
                  className="h-14"
                  data-testid="mpesa-phone-input"
                />
                <p className="text-sm text-slate-500 text-center">
                  STK Push will be sent to this number (Mock mode)
                </p>
              </div>
            )}

            {/* Credit Customer Selection */}
            {paymentMethod === 'credit' && (
              <div className="space-y-3">
                <Select value={selectedCustomer || ''} onValueChange={setSelectedCustomer}>
                  <SelectTrigger className="h-14" data-testid="credit-customer-select">
                    <SelectValue placeholder="Select credit customer" />
                  </SelectTrigger>
                  <SelectContent>
                    {creditCustomers.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.name} - {c.phone} (Balance: {formatCurrency(c.current_balance)})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {creditCustomers.length === 0 && (
                  <p className="text-sm text-amber-600 text-center">
                    No credit customers. Add one from Credit page.
                  </p>
                )}
              </div>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button 
              variant="outline" 
              onClick={() => setShowPayment(false)}
              className="flex-1"
            >
              Cancel
            </Button>
            <Button 
              className="flex-1 bg-[#007BFF]"
              onClick={handleProcessPayment}
              disabled={processing}
              data-testid="confirm-payment-btn"
            >
              {processing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Check className="mr-2 h-4 w-4" />
              )}
              Confirm
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* M-Pesa Confirmation Modal */}
      <Dialog open={showMpesaConfirm} onOpenChange={setShowMpesaConfirm}>
        <DialogContent className="max-w-sm mx-4">
          <DialogHeader>
            <DialogTitle>M-Pesa Payment</DialogTitle>
            <DialogDescription className="sr-only">Confirm M-Pesa STK Push payment</DialogDescription>
          </DialogHeader>
          <div className="py-6 text-center">
            <div className="w-16 h-16 mx-auto mb-4 bg-emerald-100 rounded-full flex items-center justify-center">
              <Smartphone className="h-8 w-8 text-emerald-600" />
            </div>
            <p className="text-slate-600">
              STK Push sent to <strong>{customerPhone}</strong>
            </p>
            <p className="text-sm text-slate-500 mt-2">
              (Mock Mode - Click confirm to simulate payment)
            </p>
          </div>
          <DialogFooter className="gap-2">
            <Button 
              variant="outline" 
              onClick={() => setShowMpesaConfirm(false)}
            >
              Cancel
            </Button>
            <Button 
              className="bg-emerald-600"
              onClick={handleConfirmMpesa}
              disabled={processing}
              data-testid="confirm-mpesa-btn"
            >
              {processing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Confirm Payment
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
