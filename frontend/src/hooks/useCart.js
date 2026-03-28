import { create } from 'zustand';
import { api, useAuthStore } from '../lib/store';

const API_BASE = `${process.env.REACT_APP_BACKEND_URL || ''}/api`;

const normalizeCart = (payload) => {
  const items = Array.isArray(payload?.items)
    ? payload.items
    : Array.isArray(payload?.cart_items)
      ? payload.cart_items
      : Array.isArray(payload)
        ? payload
        : [];

  const normalizedItems = items
    .filter((item) => item && (item.id || item.item_id))
    .map((item) => ({
      ...item,
      id: item.id || item.item_id,
      item_id: item.item_id || item.id,
      product_id: item.product_id || item.product?.id,
      shop_id: item.shop_id || item.shop?.id,
      quantity: Number(item.quantity || 1),
      unit_price: Number(item.unit_price ?? item.price ?? 0),
      total: Number(item.total ?? (Number(item.quantity || 1) * Number(item.unit_price ?? item.price ?? 0))),
    }));

  const inferredShopId = payload?.shop_id || normalizedItems[0]?.shop_id || null;
  const inferredTotal = Number(
    payload?.total_amount
      ?? payload?.subtotal
      ?? normalizedItems.reduce((sum, item) => sum + Number(item.total || 0), 0),
  );

  return {
    items: normalizedItems,
    shop_id: inferredShopId,
    total_amount: inferredTotal,
  };
};

const withItemLoading = (loadingMap, itemId, patch) => ({
  ...loadingMap,
  [itemId]: {
    updating: false,
    removing: false,
    ...(loadingMap[itemId] || {}),
    ...patch,
  },
});

const useCartStore = create((set, get) => ({
  items: [],
  isFetchingCart: false,
  error: null,
  total_amount: 0,
  shop_id: null,
  loadingMap: {},
  isCheckingOut: false,
  initialized: false,

  fetchCart: async () => {
    set({ isFetchingCart: true, error: null });
    try {
      const payload = await api.get('/customer/cart');
      const cart = normalizeCart(payload);
      set({ ...cart, isFetchingCart: false, initialized: true });
      return cart;
    } catch (error) {
      set({ isFetchingCart: false, error: error.message || 'Unable to load cart', initialized: true });
      return { items: [], total_amount: 0, shop_id: null };
    }
  },

  addToCart: async (product_id, shop_id, quantity = 1, options = {}) => {
    if (!product_id || !shop_id || Number(quantity) <= 0) {
      throw new Error('Invalid cart payload');
    }

    const { items, shop_id: existingShopId } = get();
    if (items.length > 0 && existingShopId && existingShopId !== shop_id && !options.forceReplace) {
      return { conflict: true, cancelled: true };
    }

    if (options.forceReplace) {
      await get().clearCart();
    }

    set({ error: null });
    try {
      await api.post('/customer/cart', {
        product_id,
        shop_id,
        quantity: Number(quantity),
      });
      const cart = await get().fetchCart();
      return { conflict: false, cart };
    } catch (error) {
      set({ error: error.message || 'Unable to add item to cart' });
      throw error;
    }
  },

  updateQuantity: async (item_id, quantity) => {
    if (!item_id) {
      throw new Error('Missing cart item id');
    }

    const key = String(item_id);
    if (get().loadingMap[key]?.updating || get().loadingMap[key]?.removing) {
      return;
    }

    if (Number(quantity) <= 0) {
      return get().removeItem(item_id);
    }

    set((state) => ({ loadingMap: withItemLoading(state.loadingMap, key, { updating: true }) }));
    try {
      await api.put(`/customer/cart/${item_id}`, { quantity: Number(quantity) });
      await get().fetchCart();
    } catch (error) {
      set({ error: error.message || 'Unable to update cart item' });
      throw error;
    } finally {
      set((state) => ({ loadingMap: withItemLoading(state.loadingMap, key, { updating: false }) }));
    }
  },

  removeItem: async (item_id) => {
    if (!item_id) {
      throw new Error('Missing cart item id');
    }

    const key = String(item_id);
    if (get().loadingMap[key]?.removing || get().loadingMap[key]?.updating) {
      return;
    }

    set((state) => ({ loadingMap: withItemLoading(state.loadingMap, key, { removing: true }) }));
    try {
      await api.delete(`/customer/cart/${item_id}`);
      await get().fetchCart();
    } catch (error) {
      set({ error: error.message || 'Unable to remove cart item' });
      throw error;
    } finally {
      set((state) => ({ loadingMap: withItemLoading(state.loadingMap, key, { removing: false }) }));
    }
  },

  clearCart: async () => {
    const currentItems = [...get().items];
    if (currentItems.length === 0) {
      set({ items: [], total_amount: 0, shop_id: null, isFetchingCart: false, error: null });
      return;
    }

    set({ isFetchingCart: true, error: null });
    try {
      await Promise.allSettled(
        currentItems.map((item) => api.delete(`/customer/cart/${item.item_id || item.id}`)),
      );
      set({ items: [], total_amount: 0, shop_id: null, isFetchingCart: false, error: null, loadingMap: {} });
    } catch (error) {
      set({ isFetchingCart: false, error: error.message || 'Unable to clear cart' });
      throw error;
    }
  },

  clearCartLocal: () => set({ items: [], total_amount: 0, shop_id: null, error: null, loadingMap: {} }),

  setCheckingOut: (value) => set({ isCheckingOut: Boolean(value) }),

  getItemCount: () => get().items.reduce((sum, item) => sum + Number(item.quantity || 0), 0),
}));

export default function useCart() {
  return useCartStore();
}

export const useCartCount = () => useCartStore((state) => state.items.reduce((sum, item) => sum + Number(item.quantity || 0), 0));

export const setCheckingOutState = (value) => {
  useCartStore.setState({ isCheckingOut: Boolean(value) });
};

export const getCartMetrics = () => {
  const state = useCartStore.getState();
  return {
    items_count: state.items.reduce((sum, item) => sum + Number(item.quantity || 0), 0),
    total_amount: Number(state.total_amount || 0),
  };
};

export const checkoutRequest = async ({ idempotencyKey, paymentMethod }) => {
  const headers = {
    ...useAuthStore.getState().getAuthHeaders(),
    'Content-Type': 'application/json',
    'Idempotency-Key': idempotencyKey,
  };

  const res = await fetch(`${API_BASE}/customer/checkout`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ payment_method: paymentMethod }),
  });

  const data = await res.json().catch(() => ({ detail: 'Checkout failed' }));
  if (!res.ok) {
    throw new Error(data.detail || 'Checkout failed');
  }

  return data;
};
