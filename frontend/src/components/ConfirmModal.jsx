import React from 'react';

export default function ConfirmModal({
  open = false,
  title = 'Confirm action',
  message = '',
  onConfirm,
  onCancel,
}) {
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center" role="dialog" aria-modal="true" aria-labelledby="confirm-modal-title">
      <div className="w-full max-w-md rounded-2xl bg-white p-5 shadow-xl">
        <h2 id="confirm-modal-title" className="text-base font-semibold text-slate-900">{title}</h2>
        <p className="mt-2 text-sm text-slate-600">{message}</p>

        <div className="mt-5 grid grid-cols-2 gap-2">
          <button
            type="button"
            className="h-11 rounded-xl border border-slate-200 text-sm font-medium text-slate-700"
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            type="button"
            className="h-11 rounded-xl bg-[#007BFF] text-sm font-semibold text-white"
            onClick={onConfirm}
          >
            Start New Cart
          </button>
        </div>
      </div>
    </div>
  );
}
