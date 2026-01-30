import React, { useState, useEffect } from 'react';
import { api, formatDate } from '../lib/store';
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
  Phone, 
  MessageSquare,
  Mail,
  Loader2,
  Check,
  Edit2,
  Trash2,
  Truck,
  StickyNote
} from 'lucide-react';

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Modal states
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState(null);
  const [saving, setSaving] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    notes: '',
  });

  useEffect(() => {
    loadSuppliers();
  }, []);

  const loadSuppliers = async () => {
    setLoading(true);
    try {
      const data = await api.get('/suppliers');
      setSuppliers(data);
    } catch (error) {
      toast.error('Failed to load suppliers');
    } finally {
      setLoading(false);
    }
  };

  const filteredSuppliers = suppliers.filter((s) => {
    const matchesSearch = !searchQuery || 
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.phone.includes(searchQuery);
    return matchesSearch;
  });

  const handleOpenModal = (supplier = null) => {
    if (supplier) {
      setEditingSupplier(supplier);
      setFormData({
        name: supplier.name,
        phone: supplier.phone,
        notes: supplier.notes || '',
      });
    } else {
      setEditingSupplier(null);
      setFormData({ name: '', phone: '', notes: '' });
    }
    setShowAddModal(true);
  };

  const handleSaveSupplier = async () => {
    if (!formData.name.trim()) {
      toast.error('Supplier name is required');
      return;
    }
    if (!formData.phone.trim()) {
      toast.error('Phone number is required');
      return;
    }

    setSaving(true);
    try {
      if (editingSupplier) {
        await api.put(`/suppliers/${editingSupplier.id}`, formData);
        toast.success('Supplier updated');
      } else {
        await api.post('/suppliers', formData);
        toast.success('Supplier added');
      }
      setShowAddModal(false);
      loadSuppliers();
    } catch (error) {
      toast.error(error.message || 'Failed to save supplier');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteSupplier = async (supplier) => {
    if (!window.confirm(`Delete supplier "${supplier.name}"?`)) return;
    
    try {
      await api.delete(`/suppliers/${supplier.id}`);
      toast.success('Supplier deleted');
      loadSuppliers();
    } catch (error) {
      toast.error(error.message || 'Failed to delete supplier');
    }
  };

  // Format phone for various actions
  const formatPhoneForAction = (phone) => {
    // Remove spaces, dashes, and other formatting
    let cleaned = phone.replace(/[\s\-\(\)]/g, '');
    // Convert to international format if needed
    if (cleaned.startsWith('0')) {
      cleaned = '254' + cleaned.slice(1);
    } else if (!cleaned.startsWith('+') && !cleaned.startsWith('254')) {
      cleaned = '254' + cleaned;
    }
    return cleaned.replace('+', '');
  };

  const handleCall = (phone) => {
    window.location.href = `tel:${phone}`;
  };

  const handleWhatsApp = (phone, supplierName) => {
    const formattedPhone = formatPhoneForAction(phone);
    const message = encodeURIComponent(`Hello ${supplierName}, I'm contacting you from CloudDuka POS.`);
    window.open(`https://wa.me/${formattedPhone}?text=${message}`, '_blank');
  };

  const handleSMS = (phone) => {
    window.location.href = `sms:${phone}`;
  };

  return (
    <div className="p-4 space-y-4" data-testid="suppliers-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Suppliers
        </h1>
        <Button 
          className="bg-[#007BFF] rounded-full"
          onClick={() => handleOpenModal()}
          data-testid="add-supplier-btn"
        >
          <Plus className="mr-1 h-4 w-4" />
          Add
        </Button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
        <Input
          placeholder="Search suppliers..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
          data-testid="search-suppliers-input"
        />
      </div>

      {/* Suppliers List */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32 rounded-xl" />
          ))}
        </div>
      ) : filteredSuppliers.length === 0 ? (
        <div className="text-center py-12 text-slate-500">
          <Truck className="h-16 w-16 mx-auto mb-4 opacity-30" />
          <p className="font-medium">
            {suppliers.length === 0 ? 'No suppliers yet' : 'No suppliers match your search'}
          </p>
          {suppliers.length === 0 && (
            <Button 
              className="mt-4 bg-[#007BFF]"
              onClick={() => handleOpenModal()}
            >
              Add First Supplier
            </Button>
          )}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredSuppliers.map((supplier) => (
            <Card 
              key={supplier.id}
              data-testid={`supplier-card-${supplier.id}`}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="font-semibold text-lg">{supplier.name}</h3>
                    <div className="flex items-center gap-2 text-sm text-slate-500 mt-1">
                      <Phone className="h-4 w-4" />
                      {supplier.phone}
                    </div>
                    {supplier.notes && (
                      <div className="flex items-start gap-2 text-sm text-slate-500 mt-2">
                        <StickyNote className="h-4 w-4 mt-0.5 flex-shrink-0" />
                        <span className="line-clamp-2">{supplier.notes}</span>
                      </div>
                    )}
                    <p className="text-xs text-slate-400 mt-2">
                      Added: {formatDate(supplier.created_at)}
                    </p>
                  </div>
                  
                  <div className="flex flex-col gap-2">
                    <div className="flex gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8"
                        onClick={() => handleOpenModal(supplier)}
                        data-testid={`edit-supplier-${supplier.id}`}
                      >
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8 text-red-500"
                        onClick={() => handleDeleteSupplier(supplier)}
                        data-testid={`delete-supplier-${supplier.id}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
                
                {/* Contact Actions */}
                <div className="flex gap-2 mt-4 pt-3 border-t">
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1"
                    onClick={() => handleCall(supplier.phone)}
                    data-testid={`call-supplier-${supplier.id}`}
                  >
                    <Phone className="h-4 w-4 mr-1 text-blue-600" />
                    Call
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1 border-green-200 hover:bg-green-50"
                    onClick={() => handleWhatsApp(supplier.phone, supplier.name)}
                    data-testid={`whatsapp-supplier-${supplier.id}`}
                  >
                    <MessageSquare className="h-4 w-4 mr-1 text-green-600" />
                    WhatsApp
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="flex-1"
                    onClick={() => handleSMS(supplier.phone)}
                    data-testid={`sms-supplier-${supplier.id}`}
                  >
                    <Mail className="h-4 w-4 mr-1 text-slate-600" />
                    SMS
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Add/Edit Supplier Modal */}
      <Dialog open={showAddModal} onOpenChange={setShowAddModal}>
        <DialogContent className="max-w-md mx-4">
          <DialogHeader>
            <DialogTitle>{editingSupplier ? 'Edit Supplier' : 'Add Supplier'}</DialogTitle>
            <DialogDescription>
              {editingSupplier ? 'Update supplier details' : 'Add a new supplier to your list'}
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Supplier Name *</Label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., ABC Wholesale"
                data-testid="supplier-name-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Phone Number *</Label>
              <Input
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                placeholder="+254 722 123 456"
                data-testid="supplier-phone-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Notes (Optional)</Label>
              <Input
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                placeholder="e.g., Main supplier for beverages"
                data-testid="supplier-notes-input"
              />
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowAddModal(false)}>
              Cancel
            </Button>
            <Button 
              className="bg-[#007BFF]"
              onClick={handleSaveSupplier}
              disabled={saving}
              data-testid="save-supplier-btn"
            >
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
              {editingSupplier ? 'Update' : 'Add Supplier'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
