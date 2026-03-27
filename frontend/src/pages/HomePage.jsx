import React, { lazy, Suspense, useMemo, useState } from 'react';
import Header from '../components/marketplace/Header';
import SearchBar from '../components/marketplace/SearchBar';
import CategoryList from '../components/marketplace/CategoryList';
import ProductCard from '../components/marketplace/ProductCard';
import useHomeData from '../hooks/useHomeData';

const StoreSection = lazy(() => import('../components/marketplace/StoreSection'));
const BottomNav = lazy(() => import('../components/marketplace/BottomNav'));

export default function HomePage() {
  const [searchValue, setSearchValue] = useState('');
  const [cartItems, setCartItems] = useState([]);
  const { loading, error, home, categories, products } = useHomeData();

  const filteredProducts = useMemo(() => {
    const term = searchValue.trim().toLowerCase();
    if (!term) {
      return products;
    }
    return products.filter((product) =>
      `${product.name || ''} ${product.description || ''}`.toLowerCase().includes(term),
    );
  }, [products, searchValue]);

  const handleAddToCart = (product) => {
    setCartItems((current) => [...current, { product_id: product.id, shop_id: product.shop_id }]);
  };

  return (
    <div className="min-h-screen bg-slate-50 pb-20" data-testid="marketplace-homepage">
      <Header cartCount={cartItems.length} />

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
              {[...Array(6)].map((_, index) => (
                <div key={index} className="skeleton h-36 rounded-xl" />
              ))}
            </div>
          </section>
        )}

        {error && !loading && (
          <section className="rounded-xl border border-red-100 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </section>
        )}

        {!loading && !error && (
          <>
            <section className="space-y-3">
              <h2 className="text-lg font-semibold text-slate-900">Browse categories</h2>
              <CategoryList categories={categories} />
            </section>

            <Suspense fallback={<div className="skeleton h-40 rounded-xl" />}>
              <StoreSection title="Featured stores" stores={home?.featured_stores || []} />
            </Suspense>

            <Suspense fallback={<div className="skeleton h-40 rounded-xl" />}>
              <StoreSection title="Popular stores" stores={home?.popular_stores || []} />
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
    </div>
  );
}
