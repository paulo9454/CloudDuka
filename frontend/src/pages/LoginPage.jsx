import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../lib/store';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { toast } from 'sonner';
import { Loader2, Phone, Lock, User, Store } from 'lucide-react';

const LOGO_URL = 'https://customer-assets.emergentagent.com/job_983fa6fb-7b7a-442c-bfdf-c5926d9538b8/artifacts/uzuoo21v_CloudDuka%20Logo.jpeg';

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, register, isAuthenticated, isLoading } = useAuthStore();
  const [activeTab, setActiveTab] = useState('login');
  
  // Login form
  const [loginPhone, setLoginPhone] = useState('');
  const [loginPin, setLoginPin] = useState('');
  
  // Register form
  const [regPhone, setRegPhone] = useState('');
  const [regPin, setRegPin] = useState('');
  const [regName, setRegName] = useState('');
  const [regShopName, setRegShopName] = useState('');

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/dashboard');
    }
  }, [isAuthenticated, navigate]);

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!loginPhone || !loginPin) {
      toast.error('Please enter phone and PIN');
      return;
    }
    try {
      await login(loginPhone, loginPin);
      toast.success('Welcome back!');
      navigate('/dashboard');
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    if (!regPhone || !regPin || !regName) {
      toast.error('Please fill all required fields');
      return;
    }
    if (regPin.length < 4) {
      toast.error('PIN must be at least 4 digits');
      return;
    }
    try {
      await register({
        phone: regPhone,
        pin: regPin,
        name: regName,
        shop_name: regShopName || `${regName}'s Shop`,
        role: 'owner',
      });
      toast.success('Registration successful! Welcome to CloudDuka');
      navigate('/dashboard');
    } catch (error) {
      toast.error(error.message);
    }
  };

  const formatPhoneInput = (value) => {
    // Remove non-digits
    const digits = value.replace(/\D/g, '');
    // Format as Kenyan phone
    if (digits.startsWith('254')) {
      return digits.slice(0, 12);
    } else if (digits.startsWith('0')) {
      return digits.slice(0, 10);
    } else if (digits.startsWith('7') || digits.startsWith('1')) {
      return digits.slice(0, 9);
    }
    return digits.slice(0, 12);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo and Header */}
        <div className="text-center mb-8">
          <img 
            src={LOGO_URL} 
            alt="CloudDuka" 
            className="w-24 h-24 mx-auto mb-4 rounded-2xl shadow-lg"
            data-testid="login-logo"
          />
          <h1 className="text-2xl font-bold text-slate-900" style={{ fontFamily: 'Outfit, sans-serif' }}>
            CloudDuka
          </h1>
          <p className="text-slate-600 mt-1">Your Retail POS in the Cloud</p>
        </div>

        {/* Auth Card */}
        <Card className="shadow-xl border-0">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="w-full grid grid-cols-2 mb-4">
              <TabsTrigger value="login" data-testid="login-tab">Sign In</TabsTrigger>
              <TabsTrigger value="register" data-testid="register-tab">Register</TabsTrigger>
            </TabsList>

            <TabsContent value="login">
              <CardHeader className="pb-4">
                <CardTitle className="text-xl">Welcome Back</CardTitle>
                <CardDescription>Enter your phone and PIN to continue</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleLogin} className="space-y-5">
                  <div className="space-y-2">
                    <Label htmlFor="login-phone">Phone Number</Label>
                    <div className="relative">
                      <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
                      <Input
                        id="login-phone"
                        type="tel"
                        placeholder="0712 345 678"
                        value={loginPhone}
                        onChange={(e) => setLoginPhone(formatPhoneInput(e.target.value))}
                        className="pl-10 h-12"
                        data-testid="login-phone-input"
                      />
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="login-pin">PIN</Label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
                      <Input
                        id="login-pin"
                        type="password"
                        placeholder="****"
                        value={loginPin}
                        onChange={(e) => setLoginPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
                        className="pl-10 h-12"
                        maxLength={6}
                        data-testid="login-pin-input"
                      />
                    </div>
                  </div>

                  <Button 
                    type="submit" 
                    className="w-full h-12 bg-[#007BFF] hover:bg-[#0069D9] text-white rounded-full font-medium"
                    disabled={isLoading}
                    data-testid="login-submit-btn"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Signing in...
                      </>
                    ) : (
                      'Sign In'
                    )}
                  </Button>
                </form>
              </CardContent>
            </TabsContent>

            <TabsContent value="register">
              <CardHeader className="pb-4">
                <CardTitle className="text-xl">Create Account</CardTitle>
                <CardDescription>Start your 14-day free trial</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleRegister} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="reg-name">Your Name *</Label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
                      <Input
                        id="reg-name"
                        type="text"
                        placeholder="John Doe"
                        value={regName}
                        onChange={(e) => setRegName(e.target.value)}
                        className="pl-10 h-12"
                        data-testid="register-name-input"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="reg-shop">Shop Name</Label>
                    <div className="relative">
                      <Store className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
                      <Input
                        id="reg-shop"
                        type="text"
                        placeholder="My Retail Shop"
                        value={regShopName}
                        onChange={(e) => setRegShopName(e.target.value)}
                        className="pl-10 h-12"
                        data-testid="register-shop-input"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="reg-phone">Phone Number *</Label>
                    <div className="relative">
                      <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
                      <Input
                        id="reg-phone"
                        type="tel"
                        placeholder="0712 345 678"
                        value={regPhone}
                        onChange={(e) => setRegPhone(formatPhoneInput(e.target.value))}
                        className="pl-10 h-12"
                        data-testid="register-phone-input"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="reg-pin">Create PIN * (4-6 digits)</Label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
                      <Input
                        id="reg-pin"
                        type="password"
                        placeholder="****"
                        value={regPin}
                        onChange={(e) => setRegPin(e.target.value.replace(/\D/g, '').slice(0, 6))}
                        className="pl-10 h-12"
                        maxLength={6}
                        data-testid="register-pin-input"
                      />
                    </div>
                  </div>

                  <Button 
                    type="submit" 
                    className="w-full h-12 bg-[#FF8C00] hover:bg-[#E07B00] text-white rounded-full font-medium"
                    disabled={isLoading}
                    data-testid="register-submit-btn"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Creating account...
                      </>
                    ) : (
                      'Start Free Trial'
                    )}
                  </Button>
                </form>
              </CardContent>
            </TabsContent>
          </Tabs>
        </Card>

        {/* Footer */}
        <div className="text-center mt-6 text-sm text-slate-500">
          <p>Pricing: KES 300/month or KES 3,000/year</p>
          <p className="mt-1">By Mosetech Solution</p>
        </div>
      </div>
    </div>
  );
}
