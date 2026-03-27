import React, { memo } from 'react';
import { Home, Search, ShoppingCart, User } from 'lucide-react';

const navItems = [
  { label: 'Home', icon: Home, active: true },
  { label: 'Search', icon: Search },
  { label: 'Cart', icon: ShoppingCart },
  { label: 'Account', icon: User },
];

function BottomNav() {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-slate-200 bg-white/95 backdrop-blur md:hidden">
      <div className="mx-auto grid max-w-lg grid-cols-4 px-2 py-2">
        {navItems.map((item) => (
          <button
            type="button"
            key={item.label}
            className={`flex flex-col items-center gap-1 rounded-lg py-2 text-xs font-medium transition ${
              item.active ? 'text-[#007BFF]' : 'text-slate-500'
            }`}
          >
            <item.icon className="h-5 w-5" />
            {item.label}
          </button>
        ))}
      </div>
    </nav>
  );
}

export default memo(BottomNav);
