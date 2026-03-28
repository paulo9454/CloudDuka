import { useEffect, useRef, useState } from 'react';
import { trackEvent } from '../lib/analytics';
import { checkoutRequest, getCartMetrics, setCheckingOutState } from './useCart';

const CHECKOUT_IN_PROGRESS_KEY = 'checkout_in_progress';

const makeIdempotencyKey = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `checkout-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

export default function useCheckout() {
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const inFlightKeyRef = useRef(null);

  useEffect(() => {
    const inProgress = sessionStorage.getItem(CHECKOUT_IN_PROGRESS_KEY) === 'true';
    if (!inProgress) {
      return undefined;
    }

    setCheckingOutState(true);
    const timer = window.setTimeout(() => {
      setCheckingOutState(false);
      sessionStorage.removeItem(CHECKOUT_IN_PROGRESS_KEY);
    }, 1200);

    return () => {
      window.clearTimeout(timer);
    };
  }, []);

  const checkout = async (paymentMethod = 'paystack') => {
    if (inFlightKeyRef.current) {
      return result;
    }

    const idempotencyKey = makeIdempotencyKey();
    inFlightKeyRef.current = idempotencyKey;

    const metrics = getCartMetrics();
    trackEvent('checkout_attempt', {
      items_count: metrics.items_count,
      total_amount: metrics.total_amount,
    });

    sessionStorage.setItem(CHECKOUT_IN_PROGRESS_KEY, 'true');
    setCheckingOutState(true);
    setError('');

    try {
      const response = await checkoutRequest({ idempotencyKey, paymentMethod });
      setResult(response);
      sessionStorage.removeItem(CHECKOUT_IN_PROGRESS_KEY);
      return response;
    } catch (checkoutError) {
      sessionStorage.removeItem(CHECKOUT_IN_PROGRESS_KEY);
      setError(checkoutError.message || 'Checkout failed');
      throw checkoutError;
    } finally {
      inFlightKeyRef.current = null;
      setCheckingOutState(false);
      sessionStorage.removeItem(CHECKOUT_IN_PROGRESS_KEY);
    }
  };

  return {
    checkout,
    error,
    result,
  };
}
