import React, { useState, useEffect } from 'react';
import { useAuthStore, api, formatCurrency, formatDate, formatDateTime } from '../lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import { 
  Search, 
  Plus, 
  Users, 
  Phone, 
  CreditCard,
  DollarSign,
  Loader2,
  Check,
  History,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  Mail,
  MapPin,
  Eye,
  Receipt
} from 'lucide-react';

export default function CreditPage() {
  const { user } = useAuthStore();
  const [customers, setCustomers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('all'); // all, with-balance
  
  // Modal states
  const [showAddModal, setShowAddModal] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
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
    setLoading(true);
    try {
      const data = await api.get('/credit-customers');
      setCustomers(data);
    } catch (error) {
      toast.error('Failed to load credit customers');
      console.error('Load customers error:', error);
    } finally {
      setLoading(false);
    }
  };

  const filteredCustomers = customers.filter((c) => {
    const matchesSearch = !searchQuery || 
      c.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.phone.includes(searchQuery);
    const matchesTab = activeTab === 'all' || (activeTab === 'with-balance' && c.current_balance > 0);
    return matchesSearch && matchesTab;
  });

  const totalOutstanding = customers.reduce((sum, c) => sum + c.current_balance, 0);
  const customersWithBalance = customers.filter((c) => c.current_balance > 0).length;
  const totalCreditLimit = customers.reduce((sum, c) => sum + c.credit_limit, 0);

  const handleAddCustomer = async () => {
    if (!formData.name.trim()) {
      toast.error('Customer name is required');
      return;
    }
    if (!formData.phone.trim()) {
      toast.error('Phone number is required');
      return;
    }

    setSaving(true);
    try {
      const newCustomer = await api.post('/credit-customers', {
        name: formData.name.trim(),
        phone: formData.phone.trim(),
        email: formData.email.trim() || undefined,
        address: formData.address.trim() || undefined,
        credit_limit: parseFloat(formData.credit_limit) || 10000,
      });
      
      toast.success(`Credit customer "${newCustomer.name}" added successfully!`, {
        description: `Customer ID: ${newCustomer.id.slice(0, 8)}...`
      });
      
      setShowAddModal(false);
      setFormData({ name: '', phone: '', email: '', address: '', credit_limit: '10000' });
      loadCustomers(); // Refresh the list
    } catch (error) {
      toast.error(error.message || 'Failed to add customer');
    } finally {
      setSaving(false);
    }
  };

  const handleRecordPayment = async () => {
    if (!paymentAmount || parseFloat(paymentAmount) <= 0) {
      toast.error('Enter a valid payment amount');
      return;
    }

    setSaving(true);
    try {
      const result = await api.post('/credit-customers/payment', {
        customer_id: selectedCustomer.id,
        amount: parseFloat(paymentAmount),
        payment_method: 'cash',
        notes: paymentNotes.trim() || undefined,
      });
      
      toast.success('Payment recorded successfully!', {
        description: `New balance: ${formatCurrency(result.new_balance)}`
      });
      
      setShowPaymentModal(false);
      setPaymentAmount('');
      setPaymentNotes('');
      loadCustomers(); // Refresh the list
    } catch (error) {
      toast.error(error.message || 'Failed to record payment');
    } finally {
      setSaving(false);
    }
  };

  const handleViewDetails = async (customer) => {
    setSelectedCustomer(customer);
    setHistoryLoading(true);
    setShowDetailsModal(true);
    
    try {
      const data = await api.get(`/credit-customers/${customer.id}/history`);
      setHistory(data);
    } catch (error) {
      toast.error('Failed to load transaction history');
      setHistory({ sales: [], payments: [] });
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

  // Combine and sort transactions for timeline
  const getTransactionTimeline = () => {
    const sales = (history.sales || []).map(s => ({
      ...s,
      type: 'sale',
      date: s.created_at,
      amount: s.total_amount
    }));
    const payments = (history.payments || []).map(p => ({
      ...p,
      type: 'payment',
      date: p.created_at,
      amount: p.amount
    }));
    
    return [...sales, ...payments].sort((a, b) => 
      new Date(b.date).getTime() - new Date(a.date).getTime()
    );
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
          Add Customer
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-3">
        <Card className="bg-gradient-to-br from-orange-50 to-orange-100 border-orange-200">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-orange-600 mb-1">
              <AlertCircle className="h-4 w-4" />
              <span className="text-sm font-medium">Outstanding</span>
            </div>
            <p className="text-2xl font-bold text-orange-700" style={{ fontFamily: 'Outfit, sans-serif' }}>
              {formatCurrency(totalOutstanding)}
            </p>
            <p className="text-xs text-orange-600 mt-1">
              {customersWithBalance} customer{customersWithBalance !== 1 ? 's' : ''} with balance
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-slate-600 mb-1">
              <Users className="h-4 w-4" />
              <span className="text-sm font-medium">Total Customers</span>
            </div>
            <p className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
              {customers.length}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Credit limit: {formatCurrency(totalCreditLimit)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
        <Input
          placeholder="Search by name or phone..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
          data-testid="search-customers-input"
        />
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="w-full grid grid-cols-2">
          <TabsTrigger value="all" data-testid="tab-all">
            All ({customers.length})
          </TabsTrigger>
          <TabsTrigger value="with-balance" data-testid="tab-with-balance">
            With Balance ({customersWithBalance})
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {/* Customers List */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32 rounded-xl" />
          ))}
        </div>
      ) : filteredCustomers.length === 0 ? (
        <div className="text-center py-12 text-slate-500">
          <Users className="h-16 w-16 mx-auto mb-4 opacity-30" />
          <p className="font-medium">
            {customers.length === 0 ? 'No credit customers yet' : 'No customers match your search'}
          </p>
          {customers.length === 0 && (
            <Button 
              className="mt-4 bg-[#FF8C00]"
              onClick={() => setShowAddModal(true)}
            >
              Add First Customer
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredCustomers.map((customer) => (
            <Card 
              key={customer.id}
              className={`transition-all ${customer.current_balance > 0 ? 'border-orange-200 bg-orange-50/30' : ''}`}
              data-testid={`customer-card-${customer.id}`}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-lg">{customer.name}</h3>
                    <div className="flex items-center gap-2 text-sm text-slate-500 mt-1">
                      <Phone className="h-4 w-4" />
                      {customer.phone}
                    </div>
                    {customer.email && (
                      <div className="flex items-center gap-2 text-sm text-slate-500">
                        <Mail className="h-4 w-4" />
                        {customer.email}
                      </div>
                    )}
                    
                    <div className="mt-3 flex items-center gap-4">
                      <div>
                        <p className="text-xs text-slate-500">Balance</p>
                        <p className={`text-xl font-bold ${customer.current_balance > 0 ? 'text-orange-600' : 'text-green-600'}`}>
                          {formatCurrency(customer.current_balance)}
                        </p>
                      </div>
                      <div className="border-l pl-4">
                        <p className="text-xs text-slate-500">Limit</p>
                        <p className="font-semibold">{formatCurrency(customer.credit_limit)}</p>
                      </div>
                    </div>
                    
                    <p className="text-xs text-slate-400 mt-2">
                      ID: {customer.id.slice(0, 8)}... • Added: {formatDate(customer.created_at)}
                    </p>
                  </div>
                  
                  <div className="flex flex-col gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleViewDetails(customer)}
                      data-testid={`view-details-${customer.id}`}
                    >
                      <Eye className="h-4 w-4 mr-1" />
                      Details
                    </Button>
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
            <DialogDescription>
              Create a new credit customer account. They will be available for credit sales immediately.
            </DialogDescription>
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
                data-testid="customer-email-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Address (Optional)</Label>
              <Input
                value={formData.address}
                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                placeholder="Physical address"
                data-testid="customer-address-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Credit Limit (KES)</Label>
              <Input
                type="number"
                value={formData.credit_limit}
                onChange={(e) => setFormData({ ...formData, credit_limit: e.target.value })}
                placeholder="10000"
                data-testid="customer-limit-input"
              />
              <p className="text-xs text-slate-500">Maximum amount the customer can owe</p>
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
            <DialogDescription>
              Record a payment received from this credit customer
            </DialogDescription>
          </DialogHeader>
          
          {selectedCustomer && (
            <div className="space-y-4 py-4">
              <div className="p-4 bg-slate-50 rounded-xl">
                <p className="font-semibold text-lg">{selectedCustomer.name}</p>
                <p className="text-sm text-slate-500">{selectedCustomer.phone}</p>
                <div className="mt-3 p-3 bg-orange-100 rounded-lg">
                  <p className="text-sm text-orange-600">Current Balance</p>
                  <p className="text-2xl font-bold text-orange-700">
                    {formatCurrency(selectedCustomer.current_balance)}
                  </p>
                </div>
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
                  data-testid="payment-notes-input"
                />
              </div>

              {paymentAmount && parseFloat(paymentAmount) > 0 && (
                <div className="p-3 bg-green-50 rounded-lg">
                  <p className="text-sm text-green-600">New Balance After Payment</p>
                  <p className="text-xl font-bold text-green-700">
                    {formatCurrency(Math.max(0, selectedCustomer.current_balance - parseFloat(paymentAmount)))}
                  </p>
                </div>
              )}
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

      {/* Customer Details Modal */}
      <Dialog open={showDetailsModal} onOpenChange={setShowDetailsModal}>
        <DialogContent className="max-w-md mx-4 max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Customer Details</DialogTitle>
            <DialogDescription className="sr-only">
              View customer information and transaction history
            </DialogDescription>
          </DialogHeader>
          
          {selectedCustomer && (
            <div className="space-y-4 py-4">
              {/* Customer Info */}
              <div className="p-4 bg-slate-50 rounded-xl">
                <h3 className="font-bold text-lg">{selectedCustomer.name}</h3>
                <div className="space-y-1 mt-2 text-sm text-slate-600">
                  <div className="flex items-center gap-2">
                    <Phone className="h-4 w-4" />
                    {selectedCustomer.phone}
                  </div>
                  {selectedCustomer.email && (
                    <div className="flex items-center gap-2">
                      <Mail className="h-4 w-4" />
                      {selectedCustomer.email}
                    </div>
                  )}
                  {selectedCustomer.address && (
                    <div className="flex items-center gap-2">
                      <MapPin className="h-4 w-4" />
                      {selectedCustomer.address}
                    </div>
                  )}
                </div>
                <p className="text-xs text-slate-400 mt-2">
                  Customer ID: {selectedCustomer.id}
                </p>
              </div>

              {/* Balance Summary */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-orange-50 rounded-lg border border-orange-200">
                  <p className="text-xs text-orange-600">Outstanding</p>
                  <p className="text-xl font-bold text-orange-700">
                    {formatCurrency(selectedCustomer.current_balance)}
                  </p>
                </div>
                <div className="p-3 bg-slate-50 rounded-lg">
                  <p className="text-xs text-slate-500">Credit Limit</p>
                  <p className="text-xl font-bold">
                    {formatCurrency(selectedCustomer.credit_limit)}
                  </p>
                </div>
              </div>

              {/* Available Credit */}
              <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                <p className="text-xs text-blue-600">Available Credit</p>
                <p className="text-lg font-bold text-blue-700">
                  {formatCurrency(Math.max(0, selectedCustomer.credit_limit - selectedCustomer.current_balance))}
                </p>
              </div>

              {/* Transaction History */}
              <div>
                <h4 className="font-semibold mb-3 flex items-center gap-2">
                  <History className="h-4 w-4" />
                  Transaction History
                </h4>
                
                {historyLoading ? (
                  <div className="space-y-2">
                    {[1, 2, 3].map((i) => (
                      <Skeleton key={i} className="h-16 rounded-lg" />
                    ))}
                  </div>
                ) : getTransactionTimeline().length === 0 ? (
                  <p className="text-sm text-slate-400 text-center py-4">
                    No transactions yet
                  </p>
                ) : (
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {getTransactionTimeline().map((txn, idx) => (
                      <div 
                        key={txn.id || idx}
                        className={`p-3 rounded-lg ${
                          txn.type === 'sale' ? 'bg-orange-50' : 'bg-green-50'
                        }`}
                      >
                        <div className="flex justify-between items-start">
                          <div className="flex items-center gap-2">
                            {txn.type === 'sale' ? (
                              <TrendingUp className="h-4 w-4 text-orange-600" />
                            ) : (
                              <TrendingDown className="h-4 w-4 text-green-600" />
                            )}
                            <span className="text-sm font-medium">
                              {txn.type === 'sale' ? 'Credit Sale' : 'Payment'}
                            </span>
                          </div>
                          <span className={`font-bold ${
                            txn.type === 'sale' ? 'text-orange-600' : 'text-green-600'
                          }`}>
                            {txn.type === 'sale' ? '+' : '-'}{formatCurrency(txn.amount)}
                          </span>
                        </div>
                        <p className="text-xs text-slate-500 mt-1">
                          {formatDateTime(txn.date)}
                        </p>
                        {txn.type === 'sale' && txn.receipt_number && (
                          <p className="text-xs text-slate-400 flex items-center gap-1 mt-1">
                            <Receipt className="h-3 w-3" />
                            {txn.receipt_number}
                          </p>
                        )}
                        {txn.notes && (
                          <p className="text-xs text-slate-500 mt-1 italic">
                            "{txn.notes}"
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Quick Actions */}
              {selectedCustomer.current_balance > 0 && (
                <Button 
                  className="w-full bg-green-600"
                  onClick={() => {
                    setShowDetailsModal(false);
                    openPaymentModal(selectedCustomer);
                  }}
                >
                  <DollarSign className="h-4 w-4 mr-2" />
                  Record Payment
                </Button>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDetailsModal(false)} className="w-full">
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
