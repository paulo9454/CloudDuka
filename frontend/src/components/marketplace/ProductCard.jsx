import React, { memo } from 'react';

function ProductCard({ product, onAddToCart }) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
      <div className="mb-3 aspect-square w-full overflow-hidden rounded-lg bg-slate-100">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt={product.name}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-slate-400">No image</div>
        )}
      </div>
      <h3 className="line-clamp-2 text-sm font-semibold text-slate-900">{product.name}</h3>
      <p className="mt-1 text-sm font-bold text-[#007BFF]">KES {Number(product.price || 0).toLocaleString()}</p>
      <p className="mt-1 text-xs text-slate-500">Shop: {product.shop_id || 'unknown'}</p>
      <button
        type="button"
        onClick={() => onAddToCart(product)}
        className="mt-3 w-full rounded-lg bg-[#007BFF] px-3 py-2 text-sm font-medium text-white transition hover:bg-[#0069D9]"
      >
        Add to Cart
      </button>
    </article>
  );
}

export default memo(ProductCard);
