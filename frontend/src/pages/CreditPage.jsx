import React, { useState, useEffect } from 'react';
import { useAuthStore, api, formatCurrency, formatDate } from '../lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import { 
  Search, 
  Plus, 
  Users, 
  Phone, 
  CreditCard,
  DollarSign,
  ChevronRight,
  Loader2,
  Check,
  History,
  X
} from 'lucide-react';

export default function CreditPage() {
  const { user } = useAuthStore();
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Modal states
  const [showAddModal, setShowAddModal] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [saving, setSaving] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    email: '',
    address: '',
    credit_limit: '10000',
  });
  
  // Payment state
  const [paymentAmount, setPaymentAmount] = useState('');
  const [paymentNotes, setPaymentNotes] = useState('');
  
  // History state
  const [history, setHistory] = useState({ sales: [], payments: [] });
  const [historyLoading, setHistoryLoading] = useState(false);

  useEffect(() => {
    loadCustomers();
  }, []);

  const loadCustomers = async () => {
    try {
      const data = await api.get('/credit-customers');
      setCustomers(data);
    } catch (error) {
      toast.error('Failed to load customers');
    } finally {
      setLoading(false);
    }
  };

  const filteredCustomers = customers.filter((c) => {
    const matchesSearch = !searchQuery || 
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.phone.includes(searchQuery);
    return matchesSearch;
  });

  const totalOutstanding = customers.reduce((sum, c) => sum + c.current_balance, 0);
  const customersWithBalance = customers.filter((c) => c.current_balance > 0).length;

  const handleAddCustomer = async () => {
    if (!formData.name || !formData.phone) {
      toast.error('Name and phone are required');
      return;
    }

    setSaving(true);
    try {
      await api.post('/credit-customers', {
        name: formData.name,
        phone: formData.phone,
        email: formData.email || undefined,
        address: formData.address || undefined,
        credit_limit: parseFloat(formData.credit_limit) || 10000,
      });
      toast.success('Customer added');
      setShowAddModal(false);
      setFormData({ name: '', phone: '', email: '', address: '', credit_limit: '10000' });
      loadCustomers();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  const handleRecordPayment = async () => {
    if (!paymentAmount || parseFloat(paymentAmount) <= 0) {
      toast.error('Enter a valid amount');
      return;
    }

    setSaving(true);
    try {
      await api.post('/credit-customers/payment', {
        customer_id: selectedCustomer.id,
        amount: parseFloat(paymentAmount),
        payment_method: 'cash',
        notes: paymentNotes || undefined,
      });
      toast.success('Payment recorded');
      setShowPaymentModal(false);
      setPaymentAmount('');
      setPaymentNotes('');
      loadCustomers();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  const handleViewHistory = async (customer) => {
    setSelectedCustomer(customer);
    setHistoryLoading(true);
    setShowHistoryModal(true);
    
    try {
      const data = await api.get(`/credit-customers/${customer.id}/history`);
      setHistory(data);
    } catch (error) {
      toast.error('Failed to load history');
    } finally {
      setHistoryLoading(false);
    }
  };

  const openPaymentModal = (customer) => {
    setSelectedCustomer(customer);
    setPaymentAmount('');
    setPaymentNotes('');
    setShowPaymentModal(true);
  };

  return (
    <div className="p-4 space-y-4" data-testid="credit-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Credit Customers
        </h1>
        <Button 
          className="bg-[#FF8C00] rounded-full"
          onClick={() => setShowAddModal(true)}
          data-testid="add-customer-btn"
        >
          <Plus className="mr-1 h-4 w-4" />
          Add
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4">
        <Card className="bg-orange-50 border-orange-200">
          <CardContent className="p-4">
            <p className="text-sm text-orange-600">Total Outstanding</p>
            <p className="text-2xl font-bold text-orange-700" style={{ fontFamily: 'Outfit, sans-serif' }}>
              {formatCurrency(totalOutstanding)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <p className="text-sm text-slate-500">With Balance</p>
            <p className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
              {customersWithBalance} / {customers.length}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
        <Input
          placeholder="Search customers..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
          data-testid="search-customers-input"
        />
      </div>

      {/* Customers List */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      ) : filteredCustomers.length === 0 ? (
        <div className="text-center py-12 text-slate-500">
          <Users className="h-16 w-16 mx-auto mb-4 opacity-30" />
          <p className="font-medium">No credit customers</p>
          <Button 
            className="mt-4 bg-[#FF8C00]"
            onClick={() => setShowAddModal(true)}
          >
            Add First Customer
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredCustomers.map((customer) => (
            <Card 
              key={customer.id}
              className={customer.current_balance > 0 ? 'border-orange-200' : ''}
              data-testid={`customer-card-${customer.id}`}
            >
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold">{customer.name}</h3>
                    <div className="flex items-center gap-2 text-sm text-slate-500 mt-1">
                      <Phone className="h-4 w-4" />
                      {customer.phone}
                    </div>
                    <div className="mt-2">
                      <span className={`text-lg font-bold ${customer.current_balance > 0 ? 'text-orange-600' : 'text-green-600'}`}>
                        {formatCurrency(customer.current_balance)}
                      </span>
                      <span className="text-sm text-slate-500 ml-2">
                        / {formatCurrency(customer.credit_limit)}
                      </span>
                    </div>
                  </div>
                  
                  <div className="flex flex-col gap-2">
                    {customer.current_balance > 0 && (
                      <Button
                        size="sm"
                        className="bg-green-600"
                        onClick={() => openPaymentModal(customer)}
                        data-testid={`record-payment-${customer.id}`}
                      >
                        <DollarSign className="h-4 w-4 mr-1" />
                        Pay
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleViewHistory(customer)}
                      data-testid={`view-history-${customer.id}`}
                    >
                      <History className="h-4 w-4 mr-1" />
                      History
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Add Customer Modal */}
      <Dialog open={showAddModal} onOpenChange={setShowAddModal}>
        <DialogContent className="max-w-md mx-4">
          <DialogHeader>
            <DialogTitle>Add Credit Customer</DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Customer Name *</Label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Full name"
                data-testid="customer-name-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Phone Number *</Label>
              <Input
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                placeholder="0712 345 678"
                data-testid="customer-phone-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Email (Optional)</Label>
              <Input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="email@example.com"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Address (Optional)</Label>
              <Input
                value={formData.address}
                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                placeholder="Physical address"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Credit Limit</Label>
              <Input
                type="number"
                value={formData.credit_limit}
                onChange={(e) => setFormData({ ...formData, credit_limit: e.target.value })}
                placeholder="10000"
                data-testid="customer-limit-input"
              />
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowAddModal(false)}>
              Cancel
            </Button>
            <Button 
              className="bg-[#FF8C00]"
              onClick={handleAddCustomer}
              disabled={saving}
              data-testid="save-customer-btn"
            >
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
              Add Customer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Record Payment Modal */}
      <Dialog open={showPaymentModal} onOpenChange={setShowPaymentModal}>
        <DialogContent className="max-w-md mx-4">
          <DialogHeader>
            <DialogTitle>Record Payment</DialogTitle>
          </DialogHeader>
          
          {selectedCustomer && (
            <div className="space-y-4 py-4">
              <div className="p-4 bg-slate-50 rounded-xl">
                <p className="font-semibold">{selectedCustomer.name}</p>
                <p className="text-sm text-slate-500">{selectedCustomer.phone}</p>
                <p className="text-lg font-bold text-orange-600 mt-2">
                  Balance: {formatCurrency(selectedCustomer.current_balance)}
                </p>
              </div>
              
              <div className="space-y-2">
                <Label>Payment Amount *</Label>
                <Input
                  type="number"
                  value={paymentAmount}
                  onChange={(e) => setPaymentAmount(e.target.value)}
                  placeholder="Enter amount"
                  className="text-lg"
                  data-testid="payment-amount-input"
                />
              </div>
              
              <div className="space-y-2">
                <Label>Notes (Optional)</Label>
                <Input
                  value={paymentNotes}
                  onChange={(e) => setPaymentNotes(e.target.value)}
                  placeholder="Payment notes"
                />
              </div>
            </div>
          )}

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowPaymentModal(false)}>
              Cancel
            </Button>
            <Button 
              className="bg-green-600"
              onClick={handleRecordPayment}
              disabled={saving}
              data-testid="confirm-payment-btn"
            >
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
              Record Payment
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* History Modal */}
      <Dialog open={showHistoryModal} onOpenChange={setShowHistoryModal}>
        <DialogContent className="max-w-md mx-4 max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Transaction History</DialogTitle>
          </DialogHeader>
          
          {selectedCustomer && (
            <div className="space-y-4 py-4">
              <div className="p-4 bg-slate-50 rounded-xl">
                <p className="font-semibold">{selectedCustomer.name}</p>
                <p className="text-lg font-bold text-orange-600 mt-1">
                  Current Balance: {formatCurrency(selectedCustomer.current_balance)}
                </p>
              </div>
              
              {historyLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-16 rounded-lg" />
                  ))}
                </div>
              ) : (
                <>
                  {/* Credit Purchases */}
                  <div>
                    <h4 className="font-semibold text-sm text-slate-500 mb-2">Credit Purchases</h4>
                    {history.sales.length === 0 ? (
                      <p className="text-sm text-slate-400">No credit purchases</p>
                    ) : (
                      <div className="space-y-2">
                        {history.sales.map((sale) => (
                          <div key={sale.id} className="p-3 bg-orange-50 rounded-lg">
                            <div className="flex justify-between">
                              <span className="text-sm">{sale.receipt_number}</span>
                              <span className="font-bold text-orange-600">+{formatCurrency(sale.total_amount)}</span>
                            </div>
                            <p className="text-xs text-slate-500">{formatDate(sale.created_at)}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  
                  {/* Payments */}
                  <div>
                    <h4 className="font-semibold text-sm text-slate-500 mb-2">Payments Received</h4>
                    {history.payments.length === 0 ? (
                      <p className="text-sm text-slate-400">No payments recorded</p>
                    ) : (
                      <div className="space-y-2">
                        {history.payments.map((payment) => (
                          <div key={payment.id} className="p-3 bg-green-50 rounded-lg">
                            <div className="flex justify-between">
                              <span className="text-sm">Payment</span>
                              <span className="font-bold text-green-600">-{formatCurrency(payment.amount)}</span>
                            </div>
                            <p className="text-xs text-slate-500">{formatDate(payment.created_at)}</p>
                            {payment.notes && (
                              <p className="text-xs text-slate-600 mt-1">{payment.notes}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowHistoryModal(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
