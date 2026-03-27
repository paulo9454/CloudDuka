import React, { memo } from 'react';
import StoreCard from './StoreCard';

function StoreSection({ title, stores = [], loading = false }) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        <button type="button" className="text-sm font-medium text-[#007BFF]">See all</button>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {[...Array(4)].map((_, index) => (
            <div key={index} className="skeleton h-32 rounded-xl" />
          ))}
        </div>
      ) : stores.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 bg-white p-4 text-sm text-slate-500">
          No stores available right now.
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {stores.map((store) => (
            <StoreCard key={store.id} store={store} />
          ))}
        </div>
      )}
    </section>
  );
}

export default memo(StoreSection);
