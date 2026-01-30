import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore, api, formatDate } from '../lib/store';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../components/ui/dialog';
import { Separator } from '../components/ui/separator';
import { toast } from 'sonner';
import { 
  User, 
  Store, 
  LogOut, 
  ChevronRight,
  Crown,
  Calendar,
  Phone,
  Save,
  Loader2,
  Check,
  AlertTriangle
} from 'lucide-react';

export default function SettingsPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const isOwner = user?.role === 'owner';
  
  const [shop, setShop] = useState(null);
  const [loading, setLoading] = useState(true);
  
  // Edit shop modal
  const [showEditShop, setShowEditShop] = useState(false);
  const [shopForm, setShopForm] = useState({ name: '', phone: '', address: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOwner) {
      loadShop();
    } else {
      setLoading(false);
    }
  }, [isOwner]);

  const loadShop = async () => {
    try {
      const data = await api.get('/shop');
      setShop(data);
      setShopForm({
        name: data.name || '',
        phone: data.phone || '',
        address: data.address || '',
      });
    } catch (error) {
      console.error('Failed to load shop');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveShop = async () => {
    if (!shopForm.name) {
      toast.error('Shop name is required');
      return;
    }

    setSaving(true);
    try {
      await api.put('/shop', shopForm);
      toast.success('Shop updated');
      setShowEditShop(false);
      loadShop();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/');
    toast.success('Logged out');
  };

  const getSubscriptionStatus = () => {
    if (!user?.trial_ends_at) return { status: 'active', label: 'Active', color: 'green' };
    
    const trialEnd = new Date(user.trial_ends_at);
    const now = new Date();
    const daysLeft = Math.ceil((trialEnd - now) / (1000 * 60 * 60 * 24));
    
    if (daysLeft <= 0) {
      return { status: 'expired', label: 'Trial Expired', color: 'red' };
    } else if (daysLeft <= 3) {
      return { status: 'expiring', label: `${daysLeft} days left`, color: 'amber' };
    }
    return { status: 'trial', label: `Trial: ${daysLeft} days left`, color: 'blue' };
  };

  const subscription = getSubscriptionStatus();

  return (
    <div className="p-4 space-y-4" data-testid="settings-page">
      {/* Header */}
      <h1 className="text-2xl font-bold" style={{ fontFamily: 'Outfit, sans-serif' }}>
        Settings
      </h1>

      {/* User Profile Card */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-4">
            <div className={`p-4 rounded-full ${isOwner ? 'bg-blue-100' : 'bg-slate-100'}`}>
              <User className={`h-8 w-8 ${isOwner ? 'text-blue-600' : 'text-slate-600'}`} />
            </div>
            <div className="flex-1">
              <h2 className="text-lg font-semibold flex items-center gap-2">
                {user?.name}
                {isOwner && <Crown className="h-4 w-4 text-amber-500" />}
              </h2>
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Phone className="h-4 w-4" />
                {user?.phone}
              </div>
              <span className={`inline-block mt-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                isOwner ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-700'
              }`}>
                {isOwner ? 'Owner' : 'Shopkeeper'}
              </span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Subscription Status */}
      <Card className={`border-${subscription.color}-200 bg-${subscription.color}-50/50`}>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-slate-500">Subscription</p>
              <p className={`font-semibold text-${subscription.color}-700`}>
                {subscription.label}
              </p>
              {user?.trial_ends_at && (
                <p className="text-xs text-slate-500 mt-1">
                  Ends: {formatDate(user.trial_ends_at)}
                </p>
              )}
            </div>
            {subscription.status === 'expired' && (
              <AlertTriangle className="h-6 w-6 text-red-500" />
            )}
          </div>
          
          {subscription.status !== 'active' && (
            <div className="mt-4 p-3 bg-white rounded-lg">
              <p className="text-sm font-medium mb-2">Upgrade Options:</p>
              <div className="grid grid-cols-2 gap-2">
                <div className="p-2 border rounded-lg text-center">
                  <p className="text-sm font-bold text-[#007BFF]">KES 300</p>
                  <p className="text-xs text-slate-500">Monthly</p>
                </div>
                <div className="p-2 border rounded-lg text-center bg-[#007BFF]/5 border-[#007BFF]">
                  <p className="text-sm font-bold text-[#007BFF]">KES 3,000</p>
                  <p className="text-xs text-slate-500">Yearly (Save 17%)</p>
                </div>
              </div>
              <Button className="w-full mt-3 bg-[#007BFF]" data-testid="upgrade-btn">
                Upgrade Now
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Shop Settings (Owner only) */}
      {isOwner && shop && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Store className="h-5 w-5" />
              Shop Details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex justify-between items-center py-2">
              <span className="text-slate-500">Name</span>
              <span className="font-medium">{shop.name}</span>
            </div>
            <Separator />
            <div className="flex justify-between items-center py-2">
              <span className="text-slate-500">Phone</span>
              <span className="font-medium">{shop.phone || 'Not set'}</span>
            </div>
            <Separator />
            <div className="flex justify-between items-center py-2">
              <span className="text-slate-500">Address</span>
              <span className="font-medium text-right max-w-[60%]">{shop.address || 'Not set'}</span>
            </div>
            
            <Button 
              variant="outline" 
              className="w-full mt-2"
              onClick={() => setShowEditShop(true)}
              data-testid="edit-shop-btn"
            >
              Edit Shop Details
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Quick Links */}
      <Card>
        <CardContent className="p-0">
          {isOwner && (
            <button 
              className="w-full flex items-center justify-between p-4 hover:bg-slate-50 transition-colors"
              onClick={() => navigate('/users')}
              data-testid="manage-users-link"
            >
              <span className="font-medium">Manage Users</span>
              <ChevronRight className="h-5 w-5 text-slate-400" />
            </button>
          )}
          <Separator />
          <button 
            className="w-full flex items-center justify-between p-4 hover:bg-slate-50 transition-colors"
            onClick={() => navigate('/reports')}
            data-testid="view-reports-link"
          >
            <span className="font-medium">View Reports</span>
            <ChevronRight className="h-5 w-5 text-slate-400" />
          </button>
        </CardContent>
      </Card>

      {/* App Info */}
      <Card>
        <CardContent className="p-4 text-center">
          <img 
            src="https://customer-assets.emergentagent.com/job_983fa6fb-7b7a-442c-bfdf-c5926d9538b8/artifacts/uzuoo21v_CloudDuka%20Logo.jpeg"
            alt="CloudDuka"
            className="w-16 h-16 mx-auto rounded-xl mb-3"
          />
          <h3 className="font-bold text-lg text-[#007BFF]">CloudDuka</h3>
          <p className="text-sm text-slate-500">Your Retail POS in the Cloud</p>
          <p className="text-xs text-slate-400 mt-2">Version 1.0.0</p>
          <p className="text-xs text-slate-400">By Mosetech Solution</p>
        </CardContent>
      </Card>

      {/* Logout Button */}
      <Button 
        variant="outline"
        className="w-full h-12 text-red-600 border-red-200 hover:bg-red-50"
        onClick={handleLogout}
        data-testid="logout-btn"
      >
        <LogOut className="mr-2 h-5 w-5" />
        Log Out
      </Button>

      {/* Edit Shop Modal */}
      <Dialog open={showEditShop} onOpenChange={setShowEditShop}>
        <DialogContent className="max-w-md mx-4">
          <DialogHeader>
            <DialogTitle>Edit Shop Details</DialogTitle>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Shop Name *</Label>
              <Input
                value={shopForm.name}
                onChange={(e) => setShopForm({ ...shopForm, name: e.target.value })}
                placeholder="My Retail Shop"
                data-testid="shop-name-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Phone Number</Label>
              <Input
                type="tel"
                value={shopForm.phone}
                onChange={(e) => setShopForm({ ...shopForm, phone: e.target.value })}
                placeholder="0712 345 678"
                data-testid="shop-phone-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Address</Label>
              <Input
                value={shopForm.address}
                onChange={(e) => setShopForm({ ...shopForm, address: e.target.value })}
                placeholder="123 Main Street, Nairobi"
                data-testid="shop-address-input"
              />
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowEditShop(false)}>
              Cancel
            </Button>
            <Button 
              className="bg-[#007BFF]"
              onClick={handleSaveShop}
              disabled={saving}
              data-testid="save-shop-btn"
            >
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Check className="mr-2 h-4 w-4" />}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
