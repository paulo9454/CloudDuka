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
  Plus, 
  Users, 
  Phone,
  Trash2,
  Loader2,
  Check,
  Shield,
  Lock
} from 'lucide-react';

export default function UsersPage() {
  const { user } = useAuthStore();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [saving, setSaving] = useState(false);
  
  // Form state
  const [formData, setFormData] = useState({
    name: '',
    phone: '',
    pin: '',
  });

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const data = await api.get('/users');
      setUsers(data);
    } catch (error) {
      toast.error('Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  const handleAddUser = async () => {
    if (!formData.name || !formData.phone || !formData.pin) {
      toast.error('All fields are required');
      return;
    }
    if (formData.pin.length < 4) {
      toast.error('PIN must be at least 4 digits');
      return;
    }

    setSaving(true);
    try {
      await api.post('/users', {
        name: formData.name,
        phone: formData.phone,
        pin: formData.pin,
        role: 'shopkeeper',
      });
      toast.success('Shopkeeper added');
      setShowModal(false);
      setFormData({ name: '', phone: '', pin: '' });
      loadUsers();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteUser = async (userId) => {
    if (!window.confirm('Delete this shopkeeper?')) return;
    
    try {
      await api.delete(`/users/${userId}`);
      toast.success('User deleted');
      loadUsers();
    } catch (error) {
      toast.error(error.message);
    }
  };

  return (
    <div className="p-4 space-y-4" data-testid="users-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
          Users
        </h1>
        <Button 
          className="bg-[#007BFF] rounded-full"
          onClick={() => setShowModal(true)}
          data-testid="add-user-btn"
        >
          <Plus className="mr-1 h-4 w-4" />
          Add
        </Button>
      </div>

      {/* Info Card */}
      <Card className="bg-blue-50 border-blue-200">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <Shield className="h-5 w-5 text-blue-600 mt-0.5" />
            <div>
              <p className="font-medium text-blue-900">User Roles</p>
              <p className="text-sm text-blue-700 mt-1">
                <strong>Owner:</strong> Full access to all features<br />
                <strong>Shopkeeper:</strong> Sales, M-Pesa, and credit sales only
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Users List */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 rounded-xl" />
          ))}
        </div>
      ) : users.length === 0 ? (
        <div className="text-center py-12 text-slate-500">
          <Users className="h-16 w-16 mx-auto mb-4 opacity-30" />
          <p className="font-medium">No users yet</p>
        </div>
      ) : (
        <div className="space-y-3">
          {users.map((u) => (
            <Card 
              key={u.id}
              className={u.role === 'owner' ? 'border-blue-200 bg-blue-50/30' : ''}
              data-testid={`user-card-${u.id}`}
            >
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`p-3 rounded-full ${u.role === 'owner' ? 'bg-blue-100' : 'bg-slate-100'}`}>
                      <Users className={`h-5 w-5 ${u.role === 'owner' ? 'text-blue-600' : 'text-slate-600'}`} />
                    </div>
                    <div>
                      <h3 className="font-semibold flex items-center gap-2">
                        {u.name}
                        {u.role === 'owner' && (
                          <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs">
                            Owner
                          </span>
                        )}
                      </h3>
                      <div className="flex items-center gap-2 text-sm text-slate-500">
                        <Phone className="h-4 w-4" />
                        {u.phone}
                      </div>
                    </div>
                  </div>
                  
                  {u.role !== 'owner' && (
                    <Button
                      size="icon"
                      variant="ghost"
                      className="text-red-500"
                      onClick={() => handleDeleteUser(u.id)}
                      data-testid={`delete-user-${u.id}`}
                    >
                      <Trash2 className="h-5 w-5" />
                    </Button>
                  )}
                </div>
                
                <div className="mt-3 pt-3 border-t text-sm text-slate-500">
                  Joined: {formatDate(u.created_at)}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Add User Modal */}
      <Dialog open={showModal} onOpenChange={setShowModal}>
        <DialogContent className="max-w-md mx-4">
          <DialogHeader>
            <DialogTitle>Add Shopkeeper</DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Full Name *</Label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="John Doe"
                data-testid="user-name-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Phone Number *</Label>
              <Input
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                placeholder="0712 345 678"
                data-testid="user-phone-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label>PIN * (4-6 digits)</Label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
                <Input
                  type="password"
                  value={formData.pin}
                  onChange={(e) => setFormData({ ...formData, pin: e.target.value.replace(/\D/g, '').slice(0, 6) })}
                  placeholder="****"
                  className="pl-10"
                  maxLength={6}
                  data-testid="user-pin-input"
                />
              </div>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowModal(false)}>
              Cancel
            </Button>
            <Button 
              className="bg-[#007BFF]"
              onClick={handleAddUser}
              disabled={saving}
              data-testid="save-user-btn"
            >
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
              Add Shopkeeper
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
