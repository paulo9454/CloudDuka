import React, { memo } from 'react';

function CategoryList({ categories = [] }) {
  const safeCategories = Array.isArray(categories)
    ? categories.filter((category) => category && category.id)
    : [];

  if (safeCategories.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-200 bg-white p-4 text-sm text-slate-500">
        Categories will appear here soon.
      </div>
    );
  }

  return (
    <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <div className="flex min-w-max gap-2 pb-1">
        {safeCategories.map((category) => (
          <button
            key={category.id}
            type="button"
            className="whitespace-nowrap rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 shadow-sm transition hover:border-[#007BFF]/30 hover:text-[#007BFF]"
          >
            {category.name ?? 'Other'}
          </button>
        ))}
      </div>
    </div>
  );
}

export default memo(CategoryList);
