import React, { memo } from 'react';
import { Search } from 'lucide-react';

function SearchBar({ value, onChange }) {
  return (
    <div className="relative">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
      <input
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="Search stores or products"
        className="h-11 w-full rounded-xl border border-slate-200 bg-white pl-10 pr-3 text-sm text-slate-800 shadow-sm outline-none transition focus:border-[#007BFF] focus:ring-2 focus:ring-[#007BFF]/20"
        aria-label="Search products and stores"
      />
    </div>
  );
}

export default memo(SearchBar);
