import React, { useState, useEffect } from 'react';
import { ArrowRight, Flame, Sparkles } from 'lucide-react';
import { Category, Product } from '../types';
import { CategoryChips } from '../components/CategoryChips';
import { ProductCard } from '../components/ProductCard';

interface HomePageProps {
  products: Product[];
  categories: Category[];
  selectedCategoryId: number | null;
  onSelectCategory: (id: number | null) => void;
  onSelectProduct: (product: Product) => void;
  onGoToCatalog: () => void;
}

export const HomePage: React.FC<HomePageProps> = ({
  products,
  categories,
  selectedCategoryId,
  onSelectCategory,
  onSelectProduct,
  onGoToCatalog,
}) => {
  const [wishlist, setWishlist] = useState<number[]>(() => {
    try {
      const saved = localStorage.getItem('bek_wishlist');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const handleToggleWishlist = (id: number) => {
    setWishlist((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
      try {
        localStorage.setItem('bek_wishlist', JSON.stringify(next));
      } catch {}
      return next;
    });
  };

  const filteredProducts = selectedCategoryId
    ? products.filter((p) => p.category_id === selectedCategoryId)
    : products;

  const hitProducts = products.filter((p) => p.is_hit);
  const newProducts = products.filter((p) => p.is_new);

  // Banner hero image from first available product or stylish fallback
  const heroImg =
    products.find((p) => p.photos && p.photos.length > 0)?.photos[0] ||
    'https://images.unsplash.com/photo-1556905055-8f358a7a47b2?w=800&q=80';

  return (
    <div className="pb-28 pt-3 px-4 max-w-lg mx-auto space-y-6">
      {/* Streetwear Hero Collection Banner */}
      <div className="relative rounded-3xl overflow-hidden bg-gradient-to-br from-gray-900 via-gray-800 to-gray-950 text-white p-5 shadow-sm border border-gray-800">
        <div className="relative z-10 flex items-center justify-between gap-3">
          <div className="space-y-2 max-w-[210px] sm:max-w-[240px]">
            <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/20 border border-emerald-400/40 text-emerald-300 text-[10px] font-extrabold tracking-wider uppercase">
              <Sparkles size={11} className="text-emerald-400" />
              Yangi Mavsum • 2026
            </div>
            <h2 className="text-lg sm:text-xl font-extrabold tracking-tight leading-snug">
              Streetwear &amp; Casual <br />
              <span className="text-emerald-400">Erkaklar Kolleksiyasi</span>
            </h2>
            <p className="text-[11px] text-gray-300 leading-relaxed font-normal">
              Pinduoduodan sifatli buyurtma. O'zbekiston bo'ylab tezkor yetkazamiz.
            </p>
            <div className="pt-1.5">
              <button
                onClick={onGoToCatalog}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-gray-950 text-xs font-black tracking-wide active:scale-95 transition-all shadow"
              >
                Katalogni ko'rish
                <ArrowRight size={13} />
              </button>
            </div>
          </div>

          {/* Right Product Image Cutout */}
          <div className="w-24 h-28 sm:w-28 sm:h-32 rounded-2xl overflow-hidden shrink-0 shadow-md border border-white/10 bg-gray-800">
            <img
              src={heroImg}
              alt="BEK STYLE kolleksiyasi"
              className="w-full h-full object-cover"
            />
          </div>
        </div>

        {/* Ambient Glow */}
        <div className="absolute -right-8 -bottom-8 w-40 h-40 bg-emerald-500/10 rounded-full blur-2xl pointer-events-none"></div>
      </div>

      {/* Horizontal Category Chips */}
      <div>
        <div className="flex items-center justify-between mb-2 px-0.5">
          <h3 className="text-xs font-extrabold uppercase tracking-wider text-gray-900">
            Kategoriyalar
          </h3>
          <button
            onClick={onGoToCatalog}
            className="text-[11px] font-bold text-emerald-600 hover:text-emerald-700"
          >
            Barchasi →
          </button>
        </div>
        <CategoryChips
          categories={categories}
          selectedCategoryId={selectedCategoryId}
          onSelectCategory={onSelectCategory}
        />
      </div>

      {/* When a specific category is chosen, display that category's items */}
      {selectedCategoryId !== null ? (
        <div>
          <div className="flex items-center justify-between mb-3 px-0.5">
            <h3 className="text-sm font-bold text-gray-900">
              {categories.find((c) => c.id === selectedCategoryId)?.name || 'Mahsulotlar'}
            </h3>
            <span className="text-xs font-semibold text-gray-400">
              {filteredProducts.length} ta mahsulot
            </span>
          </div>

          {filteredProducts.length > 0 ? (
            <div className="grid grid-cols-2 gap-3">
              {filteredProducts.map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  isWishlisted={wishlist.includes(product.id)}
                  onToggleWishlist={handleToggleWishlist}
                  onSelect={onSelectProduct}
                />
              ))}
            </div>
          ) : (
            <div className="bg-white rounded-2xl border border-gray-200/80 p-8 text-center text-gray-500 text-xs">
              Bu kategoriyada hozircha mahsulot yo'q.
            </div>
          )}
        </div>
      ) : (
        <>
          {/* Xit Modellar Section */}
          {hitProducts.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-3 px-0.5">
                <div className="flex items-center gap-1.5">
                  <Flame size={16} className="text-amber-500 fill-amber-500" />
                  <h3 className="text-sm font-extrabold text-gray-900">
                    XIT MODELLAR
                  </h3>
                </div>
                <button
                  onClick={onGoToCatalog}
                  className="text-xs font-bold text-emerald-600 hover:text-emerald-700"
                >
                  Barchasi →
                </button>
              </div>

              <div className="grid grid-cols-2 gap-3">
                {hitProducts.slice(0, 4).map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    isWishlisted={wishlist.includes(product.id)}
                    onToggleWishlist={handleToggleWishlist}
                    onSelect={onSelectProduct}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Yangi Kelganlar Section */}
          <div>
            <div className="flex items-center justify-between mb-3 px-0.5">
              <div className="flex items-center gap-1.5">
                <Sparkles size={16} className="text-emerald-500" />
                <h3 className="text-sm font-extrabold text-gray-900">
                  YANGI KELGANLAR
                </h3>
              </div>
              <button
                onClick={onGoToCatalog}
                className="text-xs font-bold text-emerald-600 hover:text-emerald-700"
              >
                Barchasi →
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {newProducts.map((product) => (
                <ProductCard
                  key={product.id}
                  product={product}
                  isWishlisted={wishlist.includes(product.id)}
                  onToggleWishlist={handleToggleWishlist}
                  onSelect={onSelectProduct}
                />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
