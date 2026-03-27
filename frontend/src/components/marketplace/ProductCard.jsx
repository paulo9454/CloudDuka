import React, { memo } from 'react';
import { trackEvent } from '../../lib/analytics';

const noop = () => {};

function ProductCard({
  product,
  onAddToCart = noop,
  onClick = noop,
  onProductClick = noop,
  isAdding = false,
}) {
  const imageUrl = product?.image_url ?? null;
  const stockCount = Number(product?.stock_quantity ?? product?.stock ?? 0);
  const showLowStock = Number.isFinite(stockCount) && stockCount > 0 && stockCount < 5;

  const handleAddToCart = () => {
    if (!product?.id || !product?.shop_id || isAdding) {
      return;
    }
    onAddToCart(product);
  };

  const handleProductClick = () => {
    trackEvent('product_view', {
      product_id: product?.id,
      shop_id: product?.shop_id,
    });
    onClick(product);
    onProductClick(product);
  };

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <button
        type="button"
        onClick={handleProductClick}
        className="w-full text-left"
        aria-label={`Open ${product?.name || 'product'} details`}
      >
        <div className="mb-3 aspect-square w-full overflow-hidden rounded-lg bg-slate-100">
          {imageUrl ? (
            <img
              src={imageUrl}
              alt={product?.name || 'Product image'}
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-slate-400">No image</div>
          )}
        </div>
        <h3 className="line-clamp-2 text-sm font-semibold text-slate-900">{product?.name || 'Unnamed product'}</h3>
        <p className="mt-1 text-sm font-bold text-[#007BFF]">KES {Number(product?.price || 0).toLocaleString()}</p>
        <p className="mt-1 text-xs text-slate-500">Shop: {product?.shop_id || 'unknown'}</p>
        {showLowStock && (
          <p className="mt-1 text-xs font-semibold text-[#FF8C00]">Only {stockCount} left</p>
        )}
      </button>
      <button
        type="button"
        onClick={handleAddToCart}
        disabled={isAdding}
        className="mt-3 w-full rounded-lg bg-[#007BFF] px-3 py-2 text-sm font-medium text-white transition hover:bg-[#0069D9] disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isAdding ? 'Adding...' : 'Add to Cart'}
      </button>
    </article>
  );
}

export default memo(ProductCard);
