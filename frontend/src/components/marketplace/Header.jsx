import React, { memo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShoppingCart, Cloud } from 'lucide-react';

function Header({ cartCount = 0 }) {
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-40 border-b border-slate-100 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/90">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-2">
          <div className="rounded-xl bg-[#007BFF]/10 p-2 text-[#007BFF]">
            <Cloud className="h-5 w-5" />
          </div>
          <div>
            <p className="text-lg font-bold leading-none text-slate-900">CloudDuka</p>
            <p className="text-xs text-slate-500">Marketplace</p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => navigate('/cart')}
          className="relative rounded-full bg-slate-100 p-2.5 text-slate-700 transition hover:bg-slate-200"
          aria-label="Open cart"
        >
          <ShoppingCart className="h-5 w-5" />
          {cartCount > 0 && (
            <span className="absolute -right-1 -top-1 inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-[#FF8C00] px-1 text-[10px] font-bold text-white">
              {cartCount}
            </span>
          )}
        </button>
      </div>
    </header>
  );
}

export default memo(Header);
