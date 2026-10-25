import React from 'react';
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
  const filteredProducts = selectedCategoryId
    ? products.filter((p) => p.category_id === selectedCategoryId)
    : products;

  const hitProducts = products.filter((p) => p.is_hit).slice(0, 4);

  return (
    <div className="pb-24 pt-2 px-4 max-w-lg mx-auto space-y-5 animate-fadeIn">
      {/* Streetwear Hero Collection Banner */}
      <div className="relative rounded-2xl overflow-hidden bg-gradient-to-br from-[#1A1D20] via-[#16181B] to-[#111315] border border-[#26292E] p-5 shadow-lg">
        <div className="relative z-10 space-y-2">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#C7F464]/10 border border-[#C7F464]/30 text-[#C7F464] text-[10px] font-black tracking-wider uppercase">
            <Sparkles size={12} />
            Yangi Mavsum // 2026
          </div>
          <h2 className="text-xl font-black uppercase tracking-tight text-[#F5F2E9] leading-tight">
            Streetwear &amp; Casual <br />
            <span className="text-[#C7F464]">Erkaklar Kolleksiyasi</span>
          </h2>
          <p className="text-xs text-[#8E95A0] leading-relaxed max-w-[260px]">
            Pinduoduodan sifatli buyurtma asosida. O'zbekiston bo'ylab tezkor yetkazib beramiz.
          </p>
          <div className="pt-2">
            <button
              onClick={onGoToCatalog}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#C7F464] text-[#111315] text-xs font-black uppercase tracking-wider active:scale-95 transition-all shadow-md hover:bg-[#b5e350]"
            >
              Katalogni ko'rish
              <ArrowRight size={14} />
            </button>
          </div>
        </div>

        {/* Decorative corner element */}
        <div className="absolute right-0 bottom-0 top-0 w-32 bg-gradient-to-l from-[#C7F464]/5 to-transparent pointer-events-none"></div>
      </div>

      {/* Categories chips horizontal scroll */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-black uppercase tracking-wider text-[#8E95A0]">
            Kategoriyalar
          </h3>
        </div>
        <CategoryChips
          categories={categories}
          selectedCategoryId={selectedCategoryId}
          onSelectCategory={onSelectCategory}
        />
      </div>

      {/* Hit Products Section (if any and no category filter) */}
      {!selectedCategoryId && hitProducts.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              <Flame size={16} className="text-[#C7F464]" />
              <h3 className="text-sm font-black uppercase tracking-wider text-[#F5F2E9]">
                Xit Modellar
              </h3>
            </div>
            <button
              onClick={onGoToCatalog}
              className="text-[11px] font-bold text-[#C7F464] hover:underline"
            >
              Barchasi &rarr;
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {hitProducts.map((prod) => (
              <ProductCard
                key={prod.id}
                product={prod}
                onSelect={onSelectProduct}
              />
            ))}
          </div>
        </div>
      )}

      {/* All / Filtered Products Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-black uppercase tracking-wider text-[#F5F2E9]">
            {selectedCategoryId
              ? categories.find((c) => c.id === selectedCategoryId)?.name || 'Mahsulotlar'
              : 'Barcha Kiyimlar'}
          </h3>
          <span className="text-[11px] font-medium text-[#8E95A0]">
            {filteredProducts.length} ta mahsulot
          </span>
        </div>

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
          <div className="text-center py-10 bg-[#1A1D20] border border-[#26292E] rounded-2xl p-6">
            <p className="text-sm text-[#8E95A0]">Bu toifada hali mahsulotlar yo'q</p>
          </div>
        )}
      </div>
    </div>
  );
};
