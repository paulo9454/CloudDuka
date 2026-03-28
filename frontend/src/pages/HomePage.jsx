import React, { lazy, Suspense, useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import Header from '../components/marketplace/Header';
import SearchBar from '../components/marketplace/SearchBar';
import CategoryList from '../components/marketplace/CategoryList';
import ProductCard from '../components/marketplace/ProductCard';
import ConfirmModal from '../components/ConfirmModal';
import { trackEvent } from '../lib/analytics';
import useHomeData from '../hooks/useHomeData';
import useCart from '../hooks/useCart';

const StoreSection = lazy(() => import('../components/marketplace/StoreSection'));
const BottomNav = lazy(() => import('../components/marketplace/BottomNav'));
const HOME_SKELETON_KEYS = ['home-skeleton-1', 'home-skeleton-2', 'home-skeleton-3', 'home-skeleton-4', 'home-skeleton-5', 'home-skeleton-6'];

export default function HomePage() {
  const [searchValue, setSearchValue] = useState('');
  const [addingProductId, setAddingProductId] = useState('');
  const [pendingProduct, setPendingProduct] = useState(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const { loading, error, home, categories, products } = useHomeData();
  const { items, initialized, fetchCart, addToCart } = useCart();

  useEffect(() => {
    if (!initialized) {
      fetchCart();
    }
  }, [fetchCart, initialized]);

  useEffect(() => {
    trackEvent('home_view');
  }, []);

  const cartCount = useMemo(
    () => (Array.isArray(items) ? items.reduce((sum, item) => sum + Number(item.quantity || 0), 0) : 0),
    [items],
  );

  const safeCategories = useMemo(
    () => (Array.isArray(categories) ? categories.filter((category) => category && category.id) : []),
    [categories],
  );

  const filteredProducts = useMemo(() => {
    const safeProducts = Array.isArray(products)
      ? products.filter((product) => product && product.id && product.shop_id)
      : [];

    const term = searchValue.trim().toLowerCase();
    if (!term) {
      return safeProducts;
    }

    return safeProducts.filter((product) =>
      `${product.name || ''} ${product.description ?? ''}`.toLowerCase().includes(term),
    );
  }, [products, searchValue]);

  const runAddToCart = async (product, forceReplace = false) => {
    setAddingProductId(String(product.id));
    try {
      const result = await addToCart(product.id, product.shop_id, 1, { forceReplace });

      if (result?.conflict && !forceReplace) {
        setPendingProduct(product);
        setConfirmOpen(true);
        return;
      }

      if (!result?.cancelled) {
        trackEvent('add_to_cart', {
          product_id: product.id,
          shop_id: product.shop_id,
          quantity: 1,
        });
        toast.success('Added to cart');
      }
    } catch (addError) {
      toast.error(addError.message || 'Unable to add to cart');
    } finally {
      setAddingProductId('');
    }
  };

  const handleAddToCart = async (product) => {
    if (!product?.id || !product?.shop_id) {
      return;
    }
    runAddToCart(product, false);
  };

  const handleConfirmReplace = async () => {
    if (!pendingProduct) {
      setConfirmOpen(false);
      return;
    }
    setConfirmOpen(false);
    const productToAdd = pendingProduct;
    setPendingProduct(null);
    await runAddToCart(productToAdd, true);
  };

  const handleCancelReplace = () => {
    setConfirmOpen(false);
    setPendingProduct(null);
  };

  return (
    <div className="min-h-screen bg-slate-50 pb-24" data-testid="marketplace-homepage">
      <Header cartCount={cartCount} />

      <main className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-4 sm:px-6 sm:py-6">
        <section className="space-y-4 rounded-2xl bg-gradient-to-r from-[#007BFF] to-[#4F46E5] p-4 text-white shadow-lg">
          <p className="text-sm font-medium text-white/80">CloudDuka Marketplace</p>
          <h1 className="text-2xl font-bold leading-tight">Shop from trusted local stores</h1>
          <SearchBar value={searchValue} onChange={setSearchValue} />
          <p className="text-xs text-white/80">Search is ready for debounced API integration.</p>
        </section>

        {loading && (
          <section className="space-y-3">
            <div className="skeleton h-6 w-40 rounded-lg" />
            <div className="skeleton h-20 rounded-xl" />
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {HOME_SKELETON_KEYS.map((key) => (
                <div key={key} className="skeleton h-36 rounded-xl" />
              ))}
            </div>
          </section>
        )}

        {error && !loading && (
          <section className="rounded-xl border border-red-100 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </section>
        )}

        {!loading && (
          <>
            <section className="space-y-3">
              <h2 className="text-lg font-semibold text-slate-900">Browse categories</h2>
              <CategoryList categories={safeCategories} />
            </section>

            <Suspense fallback={<div className="skeleton h-40 rounded-xl" />}>
              <StoreSection title="Featured stores" stores={home?.featured_stores || []} />
            </Suspense>

            <Suspense fallback={<div className="skeleton h-40 rounded-xl" />}>
              <StoreSection
                title="Popular stores"
                stores={(home?.popular_stores || []).map((store) => ({ ...store, is_popular: true }))}
              />
            </Suspense>

            <Suspense fallback={<div className="skeleton h-40 rounded-xl" />}>
              <StoreSection title="New stores" stores={home?.new_stores || []} />
            </Suspense>

            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-slate-900">Top products</h2>
                <span className="text-xs text-slate-500">{filteredProducts.length} items</span>
              </div>
              {filteredProducts.length === 0 ? (
                <div className="rounded-xl border border-dashed border-slate-200 bg-white p-4 text-sm text-slate-500">
                  No matching products yet.
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
                  {filteredProducts.map((product) => (
                    <ProductCard
                      key={product.id}
                      product={product}
                      onAddToCart={handleAddToCart}
                      isAdding={addingProductId === String(product.id)}
                    />
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </main>

      <Suspense fallback={null}>
        <BottomNav />
      </Suspense>

      <ConfirmModal
        open={confirmOpen}
        title="Start new cart?"
        message="This item is from a different shop. Starting a new cart will clear existing items."
        onConfirm={handleConfirmReplace}
        onCancel={handleCancelReplace}
      />
    </div>
  );
}
