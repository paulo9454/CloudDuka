import React, { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { CheckCircle2 } from 'lucide-react';
import { trackEvent } from '../lib/analytics';

export default function OrderSuccess() {
  const navigate = useNavigate();
  const location = useLocation();
  const orderId = location.state?.orderId || 'N/A';
  const totalAmount = Number(location.state?.totalAmount || 0);

  useEffect(() => {
    trackEvent('order_success', {
      order_id: orderId,
      total_amount: totalAmount,
    });
  }, [orderId, totalAmount]);

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10">
      <div className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
          <CheckCircle2 className="h-8 w-8" />
        </div>
        <h1 className="text-xl font-bold text-slate-900">Order placed successfully</h1>
        <p className="mt-2 text-sm text-slate-500">Your order is confirmed and being prepared.</p>

        <div className="mt-4 rounded-lg bg-slate-50 p-3 text-left text-sm">
          <p className="text-slate-500">Order ID</p>
          <p className="mt-1 break-all font-semibold text-slate-900">{orderId}</p>
          <p className="mt-3 text-slate-500">Total Amount</p>
          <p className="mt-1 font-bold text-slate-900">KES {totalAmount.toLocaleString()}</p>
        </div>

        <button
          type="button"
          className="mt-6 h-11 w-full rounded-xl bg-[#007BFF] text-sm font-semibold text-white"
          onClick={() => navigate('/marketplace', { replace: true })}
        >
          Continue Shopping
        </button>
      </div>
    </div>
  );
}
