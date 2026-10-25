import React, { useState, useMemo } from 'react';
import { Search, SlidersHorizontal, X, RotateCcw } from 'lucide-react';
import { Category, Product } from '../types';
import { ProductCard } from '../components/ProductCard';
import { CategoryChips } from '../components/CategoryChips';

interface CatalogPageProps {
  products: Product[];
  categories: Category[];
  selectedCategoryId: number | null;
  onSelectCategory: (id: number | null) => void;
  onSelectProduct: (product: Product) => void;
  initialSearch?: string;
}

const AVAILABLE_SIZES = ['S', 'M', 'L', 'XL', 'XXL', '30', '32', '34', '36', 'Standart'];

export const CatalogPage: React.FC<CatalogPageProps> = ({
  products,
  categories,
  selectedCategoryId,
  onSelectCategory,
  onSelectProduct,
  initialSearch = '',
}) => {
  const [search, setSearch] = useState(initialSearch);
  const [selectedSize, setSelectedSize] = useState<string | null>(null);
  const [sortOption, setSortOption] = useState<'newest' | 'price_asc' | 'price_desc'>('newest');
  const [showFilters, setShowFilters] = useState(false);

  const resetFilters = () => {
    setSearch('');
    setSelectedSize(null);
    onSelectCategory(null);
    setSortOption('newest');
  };

  const hasActiveFilters = Boolean(
    search || selectedSize || selectedCategoryId !== null || sortOption !== 'newest'
  );

  const filteredProducts = useMemo(() => {
    let list = [...products];

    if (selectedCategoryId) {
      list = list.filter((p) => p.category_id === selectedCategoryId);
    }

    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (p) => p.title.toLowerCase().includes(q) || p.description.toLowerCase().includes(q)
      );
    }

    if (selectedSize) {
      list = list.filter((p) =>
        (p.sizes || []).some((s) => s.toUpperCase() === selectedSize.toUpperCase())
      );
    }

    if (sortOption === 'price_asc') {
      list.sort((a, b) => a.price - b.price);
    } else if (sortOption === 'price_desc') {
      list.sort((a, b) => b.price - a.price);
    } else {
      list.sort((a, b) => b.id - a.id);
    }

    return list;
  }, [products, selectedCategoryId, search, selectedSize, sortOption]);

  return (
    <div className="pb-28 pt-3 px-4 max-w-lg mx-auto space-y-4">
      {/* Search Input Bar & Filter Toggle */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Kiyim nomi yoki model qidiring..."
            className="w-full pl-9 pr-8 py-2.5 rounded-xl bg-white border border-gray-200/90 text-xs text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-500 transition-all shadow-xs"
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
            >
              <X size={15} />
            </button>
          )}
        </div>

        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`px-3 py-2.5 rounded-xl border flex items-center justify-center transition-all shadow-xs ${
            showFilters || selectedSize || sortOption !== 'newest'
              ? 'bg-emerald-600 text-white border-emerald-600'
              : 'bg-white text-gray-700 border-gray-200/90 hover:bg-gray-50'
          }`}
          title="Filtrlar"
        >
          <SlidersHorizontal size={16} />
        </button>
      </div>

      {/* Category Chips */}
      <CategoryChips
        categories={categories}
        selectedCategoryId={selectedCategoryId}
        onSelectCategory={onSelectCategory}
      />

      {/* Expandable Filter / Sort Section */}
      {showFilters && (
        <div className="bg-white border border-gray-200/90 rounded-2xl p-4 space-y-3.5 shadow-sm">
          <div className="flex items-center justify-between pb-2 border-b border-gray-100">
            <span className="text-xs font-bold text-gray-900 uppercase">
              Filtrlar va saralash
            </span>
            {hasActiveFilters && (
              <button
                onClick={resetFilters}
                className="text-[11px] font-bold text-emerald-600 flex items-center gap-1 hover:underline"
              >
                <RotateCcw size={12} />
                Tozalash
              </button>
            )}
          </div>

          {/* Sort selection */}
          <div>
            <label className="text-[11px] font-bold text-gray-500 uppercase block mb-1.5">
              Narx bo'yicha saralash
            </label>
            <div className="grid grid-cols-3 gap-1.5">
              {[
                { id: 'newest', label: 'Eng yangi' },
                { id: 'price_asc', label: 'Arzonroq' },
                { id: 'price_desc', label: 'Qimmatroq' },
              ].map((opt) => (
                <button
                  key={opt.id}
                  onClick={() => setSortOption(opt.id as any)}
                  className={`py-1.5 px-2 rounded-lg text-xs font-bold transition-all text-center ${
                    sortOption === opt.id
                      ? 'bg-gray-900 text-white shadow-xs'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Size selection */}
          <div>
            <label className="text-[11px] font-bold text-gray-500 uppercase block mb-1.5">
              O'lcham bo'yicha
            </label>
            <div className="flex items-center gap-1.5 flex-wrap">
              {AVAILABLE_SIZES.map((sz) => (
                <button
                  key={sz}
                  onClick={() => setSelectedSize(selectedSize === sz ? null : sz)}
                  className={`min-w-[36px] py-1 px-2.5 rounded-lg text-xs font-bold transition-all ${
                    selectedSize === sz
                      ? 'bg-emerald-600 text-white shadow-xs'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {sz}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Results Count & Reset */}
      <div className="flex items-center justify-between text-xs text-gray-500 px-0.5">
        <span>Topildi: {filteredProducts.length} ta kiyim</span>
        {hasActiveFilters && (
          <button onClick={resetFilters} className="text-emerald-600 font-bold hover:underline">
            Filtrlarni tozalash
          </button>
        )}
      </div>

      {/* Product Grid */}
      {filteredProducts.length > 0 ? (
        <div className="grid grid-cols-2 gap-3">
          {filteredProducts.map((prod) => (
            <ProductCard
              key={prod.id}
              product={prod}
              onSelect={onSelectProduct}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-12 bg-white border border-gray-200/80 rounded-2xl p-6 space-y-3 shadow-xs">
          <div className="w-12 h-12 rounded-full bg-gray-100 text-gray-400 flex items-center justify-center mx-auto text-xl">
            🔍
          </div>
          <h4 className="text-sm font-bold text-gray-900">
            Afsuski, mahsulot topilmadi
          </h4>
          <p className="text-xs text-gray-500 max-w-xs mx-auto">
            Boshqa so'z bilan qidirib ko'ring yoki filtrlarni tozalang.
          </p>
          <button
            onClick={resetFilters}
            className="px-4 py-2 rounded-xl bg-gray-900 text-white text-xs font-bold shadow-xs active:scale-95 transition-all"
          >
            Filtrlarni tozalash
          </button>
        </div>
      )}
    </div>
  );
};
