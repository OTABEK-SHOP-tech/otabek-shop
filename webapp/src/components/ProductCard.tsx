import React from 'react';
import { Plus } from 'lucide-react';
import { Product } from '../types';
import { haptic } from '../utils/telegram';

interface ProductCardProps {
  product: Product;
  onSelect: (product: Product) => void;
  onQuickAdd?: (product: Product, e: React.MouseEvent) => void;
}

export const ProductCard: React.FC<ProductCardProps> = ({
  product,
  onSelect,
  onQuickAdd,
}) => {
  const photo = product.photos && product.photos.length > 0 ? product.photos[0] : '';

  return (
    <div
      onClick={() => {
        haptic.selection();
        onSelect(product);
      }}
      className="group bg-[#1A1D20] border border-[#26292E] rounded-2xl overflow-hidden flex flex-col cursor-pointer active:scale-[0.98] transition-all hover:border-[#C7F464]/40"
    >
      {/* Photo Container */}
      <div className="relative aspect-[4/5] bg-[#111315] overflow-hidden">
        {photo ? (
          <img
            src={photo}
            alt={product.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center p-4 text-center">
            <span className="text-2xl mb-1">⚡</span>
            <span className="text-[11px] font-bold text-[#8E95A0] uppercase">BEK STYLE</span>
          </div>
        )}

        {/* Badges */}
        <div className="absolute top-2 left-2 flex flex-col gap-1 items-start">
          {product.discount_percent && product.discount_percent > 0 ? (
            <span className="bg-[#C7F464] text-[#111315] text-[10px] font-black px-2 py-0.5 rounded-md uppercase tracking-wider shadow">
              -{product.discount_percent}%
            </span>
          ) : null}
          {product.is_new ? (
            <span className="bg-[#111315]/80 backdrop-blur-sm border border-[#26292E] text-[#F5F2E9] text-[10px] font-bold px-2 py-0.5 rounded-md uppercase tracking-wider">
              Yangi
            </span>
          ) : null}
        </div>

        {/* Quick Add Button */}
        {onQuickAdd && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              haptic.impact('medium');
              onQuickAdd(product, e);
            }}
            aria-label="Savatga qo'shish"
            className="absolute bottom-2 right-2 w-8 h-8 rounded-full bg-[#111315]/90 border border-[#26292E] flex items-center justify-center text-[#C7F464] active:scale-90 hover:bg-[#C7F464] hover:text-[#111315] transition-all shadow"
          >
            <Plus size={16} strokeWidth={2.5} />
          </button>
        )}
      </div>

      {/* Info */}
      <div className="p-3 flex-1 flex flex-col justify-between">
        <div>
          <h3 className="text-xs font-bold text-[#F5F2E9] line-clamp-2 leading-snug">
            {product.title}
          </h3>
        </div>

        <div className="mt-2.5 pt-1.5 border-t border-[#26292E]/60 flex items-baseline justify-between gap-1 flex-wrap">
          <div>
            <div className="text-[13px] font-black text-[#C7F464]">
              {product.formatted_price}
            </div>
            {product.formatted_old_price ? (
              <div className="text-[10px] text-[#8E95A0] line-through">
                {product.formatted_old_price}
              </div>
            ) : null}
          </div>

          {product.sizes && product.sizes.length > 0 ? (
            <div className="text-[9px] font-semibold text-[#8E95A0] uppercase tracking-wider">
              {product.sizes.slice(0, 2).join(', ')}{product.sizes.length > 2 ? '+' : ''}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};
