import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, MessageCircle, Minus, Plus, ShoppingCart, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { ANALYTICS_EVENTS, trackEvent } from '../lib/analytics';
import useCart from '../hooks/useCart';

const currency = (amount) => `KES ${Number(amount || 0).toLocaleString()}`;

export default function CartPage() {
  const navigate = useNavigate();
  const [navigating, setNavigating] = useState(false);
  const [isOpeningWhatsApp, setIsOpeningWhatsApp] = useState(false);
  const whatsappTimerRef = useRef(null);
  const checkoutStartedRef = useRef(false);
  const viewedRef = useRef(false);
  const {
    items,
    isFetchingCart,
    isCheckingOut,
    error,
    total_amount,
    loadingMap,
    initialized,
    fetchCart,
    updateQuantity,
    removeItem,
  } = useCart();

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
    if (!viewedRef.current && initialized) {
      viewedRef.current = true;
      trackEvent('view_cart', {
        items_count: items.reduce((sum, item) => sum + Number(item.quantity || 0), 0),
      });
    }
  }, [initialized, items]);

  useEffect(() => () => {
    if (!checkoutStartedRef.current) {
      trackEvent('cart_abandoned');
    }
  }, []);

  const handleIncrease = async (item) => {
    const itemId = String(item.item_id || item.id);
    if (loadingMap[itemId]?.updating || loadingMap[itemId]?.removing) {
      return;
    }

    try {
      await updateQuantity(item.item_id || item.id, Number(item.quantity || 1) + 1);
    } catch (updateError) {
      toast.error(updateError.message || 'Unable to update quantity');
    }
  };

  const handleDecrease = async (item) => {
    const itemId = String(item.item_id || item.id);
    if (loadingMap[itemId]?.updating || loadingMap[itemId]?.removing) {
      return;
    }

    try {
      await updateQuantity(item.item_id || item.id, Number(item.quantity || 1) - 1);
    } catch (updateError) {
      toast.error(updateError.message || 'Unable to update quantity');
    }
  };

  const handleRemove = async (item) => {
    const itemId = String(item.item_id || item.id);
    if (loadingMap[itemId]?.removing || loadingMap[itemId]?.updating) {
      return;
    }

    try {
      await removeItem(item.item_id || item.id);
      toast.success('Item removed');
    } catch (removeError) {
      toast.error(removeError.message || 'Unable to remove item');
    }
  };

  const handleProceedToCheckout = () => {
    if (isFetchingCart || isCheckingOut || navigating) {
      return;
    }

    checkoutStartedRef.current = true;
    trackEvent('checkout_started', {
      items_count: items.reduce((sum, item) => sum + Number(item.quantity || 0), 0),
      total_amount: Number(total_amount || 0),
    });

    setNavigating(true);
    navigate('/checkout');
  };

  const subtotal = Number(total_amount || 0);
  const whatsappPhone = items[0]?.shop_phone || items[0]?.shop?.phone || '';
  const whatsappMessage = [
    'Hello, I want to place an order:',
    '',
    ...items.map((item, index) => `${index + 1}. ${item.product_name || item.name || 'Item'} x${item.quantity} - ${currency(item.total ?? (Number(item.quantity || 0) * Number(item.unit_price || item.price || 0)))}`),
    '',
    `Total: ${currency(subtotal)}`,
    '',
    'Name:',
    'Location:',
  ].join('\n');

  const whatsappUrl = whatsappPhone && items.length > 0
    ? `https://wa.me/${String(whatsappPhone).replace(/[^\d]/g, '')}?text=${encodeURIComponent(whatsappMessage)}`
    : '';

  const handleOpenWhatsApp = () => {
    if (!whatsappUrl || isOpeningWhatsApp || isCheckingOut || navigating) {
      return;
    }

    setIsOpeningWhatsApp(true);
    trackEvent(ANALYTICS_EVENTS.WHATSAPP_CLICKED, {
      source: 'cart',
      items_count: items.length,
      total_amount: subtotal,
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
    <div className="min-h-screen bg-slate-50 pb-28">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-3 sm:px-6">
          <button
            type="button"
            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100"
            onClick={() => navigate('/marketplace')}
            aria-label="Back to marketplace"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-lg font-semibold text-slate-900">Your cart</h1>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-4 sm:px-6 sm:py-6">
        {isFetchingCart && (
          <div className="space-y-3">
            {['cart-skel-1', 'cart-skel-2', 'cart-skel-3'].map((key) => (
              <div key={key} className="skeleton h-24 rounded-xl" />
            ))}
          </div>
        )}

        {!isFetchingCart && error && (
          <div className="rounded-xl border border-red-100 bg-red-50 p-4 text-sm text-red-700">
            <p>{error}</p>
            <button
              type="button"
              className="mt-2 text-sm font-semibold text-red-700 underline"
              onClick={fetchCart}
            >
              Retry
            </button>
          </div>
        )}

        {!isFetchingCart && !error && items.length === 0 && (
          <section className="rounded-2xl border border-dashed border-slate-200 bg-white p-8 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-500">
              <ShoppingCart className="h-6 w-6" />
            </div>
            <h2 className="text-base font-semibold text-slate-900">Your cart is empty</h2>
            <p className="mt-1 text-sm text-slate-500">Add products from the marketplace to continue.</p>
            <button
              type="button"
              className="mt-4 rounded-lg bg-[#007BFF] px-4 py-2 text-sm font-medium text-white"
              onClick={() => navigate('/marketplace')}
            >
              Start shopping
            </button>
          </section>
        )}

        {!isFetchingCart && items.length > 0 && (
          <>
            <section className="space-y-3">
              {items.map((item) => {
                const itemId = String(item.item_id || item.id);
                const isUpdating = Boolean(loadingMap[itemId]?.updating);
                const isRemoving = Boolean(loadingMap[itemId]?.removing);
                const isBusy = isUpdating || isRemoving;

                return (
                  <article key={itemId} className={`rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition ${isRemoving ? 'opacity-60' : 'opacity-100'}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="truncate text-sm font-semibold text-slate-900">{item.product_name || item.name || 'Product'}</h3>
                        <p className="mt-1 text-sm text-[#007BFF]">{currency(item.unit_price || item.price)}</p>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleRemove(item)}
                        disabled={isBusy}
                        className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                        aria-label="Remove item"
                      >
                        {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                      </button>
                    </div>

                    <div className="mt-3 flex items-center justify-between">
                      <div className="inline-flex items-center gap-1 rounded-lg border border-slate-200 p-1">
                        <button
                          type="button"
                          onClick={() => handleDecrease(item)}
                          disabled={isBusy}
                          className="rounded-md p-2 text-slate-600 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                          aria-label="Decrease quantity"
                        >
                          {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Minus className="h-4 w-4" />}
                        </button>
                        <span className="min-w-[2rem] text-center text-sm font-semibold text-slate-900">{item.quantity}</span>
                        <button
                          type="button"
                          onClick={() => handleIncrease(item)}
                          disabled={isBusy}
                          className="rounded-md p-2 text-slate-600 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
                          aria-label="Increase quantity"
                        >
                          {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                        </button>
                      </div>

                      <p className="text-sm font-semibold text-slate-900">{currency(item.total)}</p>
                    </div>
                  </article>
                );
              })}
            </section>

            <section className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between text-sm text-slate-600">
                <span>Subtotal</span>
                <span>{currency(subtotal)}</span>
              </div>
              <div className="mt-2 flex items-center justify-between text-base font-semibold text-slate-900">
                <span>Total</span>
                <span>{currency(subtotal)}</span>
              </div>
            </section>
          </>
        )}
      </main>

      {items.length > 0 && (
        <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-slate-200 bg-white/95 p-3 pb-[calc(env(safe-area-inset-bottom,0px)+0.75rem)] backdrop-blur md:hidden">
          <div className="mx-auto max-w-3xl space-y-2">
            {whatsappUrl && (
              <button
                type="button"
                className="h-11 w-full rounded-xl border border-[#25D366] bg-white text-sm font-semibold text-[#25D366] disabled:cursor-not-allowed disabled:opacity-60"
                onClick={handleOpenWhatsApp}
                disabled={isFetchingCart || navigating || isCheckingOut || isOpeningWhatsApp}
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
              onClick={handleProceedToCheckout}
              disabled={isFetchingCart || navigating || isCheckingOut || items.length === 0}
            >
              {navigating ? 'Opening checkout...' : `Proceed to Checkout • ${currency(subtotal)}`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
