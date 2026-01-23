import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const API_URL = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Auth Store
export const useAuthStore = create(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (phone, pin) => {
        set({ isLoading: true, error: null });
        try {
          const res = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone, pin }),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || 'Login failed');
          set({ token: data.token, user: data.user, isAuthenticated: true, isLoading: false });
          return data;
        } catch (error) {
          set({ error: error.message, isLoading: false });
          throw error;
        }
      },

      register: async (userData) => {
        set({ isLoading: true, error: null });
        try {
          const res = await fetch(`${API_URL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData),
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || 'Registration failed');
          set({ token: data.token, user: data.user, isAuthenticated: true, isLoading: false });
          return data;
        } catch (error) {
          set({ error: error.message, isLoading: false });
          throw error;
        }
      },

      logout: () => {
        set({ token: null, user: null, isAuthenticated: false });
        useCartStore.getState().clearCart();
      },

      getAuthHeaders: () => {
        const token = get().token;
        return token ? { Authorization: `Bearer ${token}` } : {};
      },
    }),
    { name: 'cloudduka-auth' }
  )
);

// Cart Store
export const useCartStore = create(
  persist(
    (set, get) => ({
      items: [],
      
      addItem: (product) => {
        const items = get().items;
        const existing = items.find((i) => i.product_id === product.id);
        if (existing) {
          set({
            items: items.map((i) =>
              i.product_id === product.id
                ? { ...i, quantity: i.quantity + 1, total: (i.quantity + 1) * i.unit_price }
                : i
            ),
          });
        } else {
          set({
            items: [
              ...items,
              {
                product_id: product.id,
                product_name: product.name,
                quantity: 1,
                unit_price: product.unit_price,
                total: product.unit_price,
                stock_quantity: product.stock_quantity,
              },
            ],
          });
        }
      },

      updateQuantity: (productId, quantity) => {
        if (quantity <= 0) {
          get().removeItem(productId);
          return;
        }
        set({
          items: get().items.map((i) =>
            i.product_id === productId
              ? { ...i, quantity, total: quantity * i.unit_price }
              : i
          ),
        });
      },

      removeItem: (productId) => {
        set({ items: get().items.filter((i) => i.product_id !== productId) });
      },

      clearCart: () => set({ items: [] }),

      getTotal: () => get().items.reduce((sum, i) => sum + i.total, 0),

      getItemCount: () => get().items.reduce((sum, i) => sum + i.quantity, 0),
    }),
    { name: 'cloudduka-cart' }
  )
);

// Offline Store
export const useOfflineStore = create(
  persist(
    (set, get) => ({
      isOnline: navigator.onLine,
      pendingSales: [],
      lastSync: null,

      setOnlineStatus: (status) => set({ isOnline: status }),

      addPendingSale: (sale) => {
        set({ pendingSales: [...get().pendingSales, { ...sale, pending_id: Date.now() }] });
      },

      removePendingSale: (pendingId) => {
        set({ pendingSales: get().pendingSales.filter((s) => s.pending_id !== pendingId) });
      },

      syncPendingSales: async () => {
        const { pendingSales } = get();
        const headers = useAuthStore.getState().getAuthHeaders();
        
        for (const sale of pendingSales) {
          try {
            const res = await fetch(`${API_URL}/sales`, {
              method: 'POST',
              headers: { ...headers, 'Content-Type': 'application/json' },
              body: JSON.stringify(sale),
            });
            if (res.ok) {
              get().removePendingSale(sale.pending_id);
            }
          } catch (error) {
            console.error('Sync failed for sale:', sale.pending_id);
          }
        }
        set({ lastSync: new Date().toISOString() });
      },
    }),
    { name: 'cloudduka-offline' }
  )
);

// API Helper
export const api = {
  get: async (endpoint) => {
    const headers = useAuthStore.getState().getAuthHeaders();
    const res = await fetch(`${API_URL}${endpoint}`, { headers });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || 'Request failed');
    }
    return res.json();
  },

  post: async (endpoint, data) => {
    const headers = useAuthStore.getState().getAuthHeaders();
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || 'Request failed');
    }
    return res.json();
  },

  put: async (endpoint, data) => {
    const headers = useAuthStore.getState().getAuthHeaders();
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: 'PUT',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || 'Request failed');
    }
    return res.json();
  },

  delete: async (endpoint) => {
    const headers = useAuthStore.getState().getAuthHeaders();
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: 'DELETE',
      headers,
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || 'Request failed');
    }
    return res.json();
  },
};

// Format currency
export const formatCurrency = (amount) => {
  return new Intl.NumberFormat('en-KE', {
    style: 'currency',
    currency: 'KES',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
};

// Format date
export const formatDate = (dateString) => {
  return new Date(dateString).toLocaleDateString('en-KE', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
};

// Format time
export const formatTime = (dateString) => {
  return new Date(dateString).toLocaleTimeString('en-KE', {
    hour: '2-digit',
    minute: '2-digit',
  });
};

// Format datetime
export const formatDateTime = (dateString) => {
  return `${formatDate(dateString)} ${formatTime(dateString)}`;
};
