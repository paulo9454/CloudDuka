import { useEffect, useState } from 'react';

const API_BASE = `${process.env.REACT_APP_BACKEND_URL || ''}/api`;

async function fetchJson(path) {
  const response = await fetch(`${API_BASE}${path}`);
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error((payload && payload.detail) || 'Failed to load marketplace data');
  }
  return payload;
}

export default function useHomeData() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [home, setHome] = useState(null);
  const [categories, setCategories] = useState([]);
  const [products, setProducts] = useState([]);

  useEffect(() => {
    let mounted = true;

    const loadHome = async () => {
      try {
        setLoading(true);
        setError('');
        const [homePayload, categoryPayload, productsPayload] = await Promise.all([
          fetchJson('/public/home'),
          fetchJson('/public/categories').catch(() => []),
          fetchJson('/public/products?limit=12').catch(() => []),
        ]);

        if (!mounted) {
          return;
        }

        setHome(homePayload || {
          categories: [],
          featured_stores: [],
          popular_stores: [],
          new_stores: [],
        });
        setCategories(
          Array.isArray(categoryPayload) && categoryPayload.length > 0
            ? categoryPayload
            : (homePayload?.categories || []),
        );
        setProducts(Array.isArray(productsPayload) ? productsPayload : []);
      } catch (loadError) {
        if (!mounted) {
          return;
        }
        setError(loadError.message || 'Unable to load marketplace right now');
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    loadHome();

    return () => {
      mounted = false;
    };
  }, []);

  return {
    loading,
    error,
    home,
    categories,
    products,
  };
}
