import React, { memo } from 'react';
import { Home, ShoppingCart, ReceiptText } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useCartCount } from '../../hooks/useCart';

const navItems = [
  { label: 'Home', icon: Home, path: '/marketplace' },
  { label: 'Cart', icon: ShoppingCart, path: '/cart', badge: true },
  { label: 'Orders', icon: ReceiptText, path: '/orders' },
];

function BottomNav() {
  const location = useLocation();
  const navigate = useNavigate();
  const cartCount = useCartCount();

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 border-t border-slate-200 bg-white/95 backdrop-blur md:hidden">
      <div className="mx-auto grid max-w-lg grid-cols-3 px-2 py-2">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <button
              type="button"
              key={item.label}
              onClick={() => navigate(item.path)}
              className={`relative flex flex-col items-center gap-1 rounded-lg py-2 text-xs font-medium transition ${
                isActive ? 'text-[#007BFF]' : 'text-slate-500'
              }`}
            >
              <item.icon className="h-5 w-5" />
              {item.label}
              {item.badge && cartCount > 0 && (
                <span className="absolute right-5 top-0 inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-[#FF8C00] px-1 text-[10px] font-bold text-white">
                  {cartCount > 99 ? '99+' : cartCount}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
}

export default memo(BottomNav);
