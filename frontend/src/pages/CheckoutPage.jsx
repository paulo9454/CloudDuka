import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeft, CreditCard, MessageCircle } from 'lucide-react';
import { toast } from 'sonner';
import { ANALYTICS_EVENTS, trackEvent } from '../lib/analytics';
import useCart from '../hooks/useCart';
import useCheckout from '../hooks/useCheckout';

const currency = (amount) => `KES ${Number(amount || 0).toLocaleString()}`;

export default function CheckoutPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const completedRef = useRef(false);
  const whatsappTimerRef = useRef(null);
  const [retrying, setRetrying] = useState(false);
  const [isOpeningWhatsApp, setIsOpeningWhatsApp] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState('paystack');
  const {
    items,
    total_amount,
    isFetchingCart,
    initialized,
    isCheckingOut,
    fetchCart,
    clearCartLocal,
  } = useCart();
  const { checkout, error } = useCheckout();

  const whatsappPhone = items[0]?.shop_phone || items[0]?.shop?.phone || '';

  const whatsappUrl = useMemo(() => {
    if (!whatsappPhone || items.length === 0) {
      return '';
    }

    const lines = items.map((item, index) => `${index + 1}. ${item.product_name || item.name || 'Item'} x${item.quantity} - ${currency(item.total ?? (Number(item.quantity || 0) * Number(item.unit_price || item.price || 0)))}`);
    const message = [
      'Hello, I want to place an order:',
      '',
      ...lines,
      '',
      `Total: ${currency(total_amount)}`,
      '',
      'Name:',
      'Location:',
    ].join('\n');

    return `https://wa.me/${String(whatsappPhone).replace(/[^\d]/g, '')}?text=${encodeURIComponent(message)}`;
  }, [items, total_amount, whatsappPhone]);

  useEffect(() => {
    if (!initialized) {
      fetchCart();
    }
  }, [fetchCart, initialized]);

  useEffect(() => () => {
    if (whatsappTimerRef.current) {
      window.clearTimeout(whatsappTimerRef.current);
      whatsappTimerRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (initialized && !isFetchingCart && items.length === 0) {
      navigate('/cart', { replace: true });
    }
  }, [initialized, isFetchingCart, items.length, navigate]);

  useEffect(() => () => {
    if (!completedRef.current) {
      trackEvent('checkout_abandoned');
    }
  }, []);

  const runCheckout = async () => {
    if (isCheckingOut || retrying) {
      return;
    }

    try {
      const response = await checkout(paymentMethod);
      clearCartLocal();
      completedRef.current = true;

      if (response?.payment?.status === 'pending') {
        navigate('/order-success', {
          state: {
            orderId: response.order_id,
            paymentStatus: response.payment?.status,
            totalAmount: total_amount,
            from: location.pathname,
          },
          replace: true,
        });
        return;
      }

      navigate('/order-success', {
        state: {
          orderId: response.order_id,
          paymentStatus: response?.payment?.status || 'success',
          totalAmount: total_amount,
          from: location.pathname,
        },
        replace: true,
      });
    } catch (checkoutError) {
      trackEvent(ANALYTICS_EVENTS.CHECKOUT_FAILED, {
        message: checkoutError?.message || 'Checkout failed',
      });
      toast.error('Payment failed. Please try again.');
    }
  };

  const handleCheckout = () => {
    runCheckout();
  };

  const handleRetry = async () => {
    if (retrying || isCheckingOut) {
      return;
    }

    setRetrying(true);
    trackEvent(ANALYTICS_EVENTS.RETRY_CLICKED, { source: 'checkout_error' });
    try {
      await runCheckout();
    } finally {
      setRetrying(false);
    }
  };

  const openWhatsApp = () => {
    if (!whatsappUrl || isCheckingOut || isOpeningWhatsApp || retrying) {
      return;
    }

    setIsOpeningWhatsApp(true);
    trackEvent(ANALYTICS_EVENTS.WHATSAPP_CLICKED, {
      source: 'checkout',
      items_count: items.length,
      total_amount,
    });
    window.open(whatsappUrl, '_blank', 'noopener,noreferrer');

    if (whatsappTimerRef.current) {
      window.clearTimeout(whatsappTimerRef.current);
    }
    whatsappTimerRef.current = window.setTimeout(() => {
      setIsOpeningWhatsApp(false);
      whatsappTimerRef.current = null;
    }, 800);
  };

  return (
    <div className="min-h-screen bg-slate-50 pb-32">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-3 sm:px-6">
          <button
            type="button"
            disabled={isCheckingOut || retrying}
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={() => navigate('/cart')}
            aria-label="Back to cart"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-lg font-semibold text-slate-900">Checkout</h1>
        </div>
      </header>

      <main className={`mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-4 transition-opacity sm:px-6 sm:py-6 ${(isCheckingOut || retrying) ? 'pointer-events-none opacity-70' : 'opacity-100'}`}>
        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-900">Order summary</h2>
          <div className="mt-3 space-y-2">
            {items.map((item) => (
              <div key={item.item_id || item.id} className="flex items-center justify-between text-sm">
                <span className="truncate pr-3 text-slate-700">{item.product_name || item.name || 'Product'} × {item.quantity}</span>
                <span className="font-medium text-slate-900">{currency(item.total)}</span>
              </div>
            ))}
          </div>

          <div className="mt-4 border-t border-slate-100 pt-3">
            <div className="flex items-center justify-between text-lg font-bold text-slate-900">
              <span>Total</span>
              <span>{currency(total_amount)}</span>
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-900">Payment method</h2>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {[
              { value: 'paystack', label: 'Paystack' },
              { value: 'mpesa', label: 'M-Pesa' },
              { value: 'cash', label: 'Cash' },
              { value: 'credit', label: 'Credit' },
            ].map((method) => (
              <button
                key={method.value}
                type="button"
                onClick={() => setPaymentMethod(method.value)}
                className={`rounded-lg border px-3 py-2 text-sm ${paymentMethod === method.value ? 'border-[#007BFF] bg-blue-50 text-[#007BFF]' : 'border-slate-200 bg-white text-slate-700'}`}
                disabled={isCheckingOut || retrying}
              >
                <span className="inline-flex items-center gap-2">
                  <CreditCard className="h-4 w-4" />
                  {method.label}
                </span>
              </button>
            ))}
          </div>
          {error && (
            <div className="mt-3 rounded-lg border border-red-100 bg-red-50 p-3 text-sm text-red-700">
              <p>Payment failed. Please try again.</p>
              <button
                type="button"
                className="mt-2 font-semibold underline disabled:cursor-not-allowed disabled:opacity-60"
                onClick={handleRetry}
                disabled={isCheckingOut || retrying}
              >
                {retrying ? 'Retrying...' : 'Retry payment'}
              </button>
            </div>
          )}
        </section>
      </main>

      <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-slate-200 bg-white/95 p-3 pb-[calc(env(safe-area-inset-bottom,0px)+0.75rem)] backdrop-blur md:hidden">
        <div className="mx-auto max-w-3xl space-y-2">
          {whatsappUrl && (
            <button
              type="button"
              className="h-11 w-full rounded-xl border border-[#25D366] bg-white text-sm font-semibold text-[#25D366] disabled:cursor-not-allowed disabled:opacity-60"
              onClick={openWhatsApp}
              disabled={isCheckingOut || retrying || isOpeningWhatsApp}
            >
              <span className="inline-flex items-center gap-2">
                <MessageCircle className="h-4 w-4" />
                {isOpeningWhatsApp ? 'Opening WhatsApp...' : 'Order via WhatsApp'}
              </span>
            </button>
          )}
          <button
            type="button"
            className="h-12 w-full rounded-xl bg-[#007BFF] text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
            onClick={handleCheckout}
            disabled={isCheckingOut || retrying || items.length === 0}
          >
            {retrying ? 'Retrying payment...' : (isCheckingOut ? 'Processing payment...' : `Pay Now • ${currency(total_amount)}`)}
          </button>
        </div>
      </div>
    </div>
  );
}
