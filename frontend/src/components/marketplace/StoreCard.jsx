import React, { memo } from 'react';
import { ChevronRight, Store } from 'lucide-react';

function StoreCard({ store }) {
  return (
    <button
      type="button"
      className="card-interactive w-full rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm"
    >
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-[#007BFF]/10 text-[#007BFF]">
        <Store className="h-5 w-5" />
      </div>
      <h3 className="line-clamp-1 text-sm font-semibold text-slate-900">{store.name}</h3>
      <div className="mt-1 flex items-center justify-between">
        <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
          {store.category || 'other'}
        </span>
        <ChevronRight className="h-4 w-4 text-slate-400" />
      </div>
    </button>
  );
}

export default memo(StoreCard);
