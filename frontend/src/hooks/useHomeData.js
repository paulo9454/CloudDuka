import { useEffect, useRef, useState } from 'react';

const API_BASE = `${process.env.REACT_APP_BACKEND_URL || ''}/api`;

async function fetchJson(path, signal) {
  const response = await fetch(`${API_BASE}${path}`, { signal });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error((payload && payload.detail) || 'Some sections may be unavailable');
  }
  return payload;
}

export default function useHomeData() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [home, setHome] = useState(null);
  const [categories, setCategories] = useState([]);
  const [products, setProducts] = useState([]);
  const [version] = useState(0);
  const requestIdRef = useRef(0);

  useEffect(() => {
    const requestId = ++requestIdRef.current;
    const controller = new AbortController();

    const loadHome = async () => {
      try {
        setLoading(true);
        setError('');

        const [homeResult, categoryResult, productsResult] = await Promise.allSettled([
          fetchJson('/public/home', controller.signal),
          fetchJson('/public/categories', controller.signal),
          fetchJson('/public/products?limit=12', controller.signal),
        ]);

        if (requestId !== requestIdRef.current) {
          return;
        }

        const homePayload = homeResult.status === 'fulfilled' && homeResult.value
          ? homeResult.value
          : {};

        const categoryPayload = categoryResult.status === 'fulfilled'
          ? categoryResult.value
          : [];

        const productsPayload = productsResult.status === 'fulfilled'
          ? productsResult.value
          : [];

        setHome(homePayload);
        setCategories(
          Array.isArray(categoryPayload) && categoryPayload.length > 0
            ? categoryPayload
            : (homePayload?.categories || []),
        );
        setProducts(Array.isArray(productsPayload) ? productsPayload : []);

        if (homeResult.status === 'rejected') {
          setError('Some sections may be unavailable');
        }
      } catch (loadError) {
        if (loadError?.name === 'AbortError' || requestId !== requestIdRef.current) {
          return;
        }
        setError(loadError.message || 'Some sections may be unavailable');
      } finally {
        if (requestId === requestIdRef.current) {
          setLoading(false);
        }
      }
    };

    loadHome();

    return () => {
      controller.abort();
    };
  }, [version]);

  return {
    loading,
    error,
    home,
    categories,
    products,
  };
}
