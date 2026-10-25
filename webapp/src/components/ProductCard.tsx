import React from 'react';
import { Heart, Plus } from 'lucide-react';
import { Product } from '../types';
import { haptic } from '../utils/telegram';

interface ProductCardProps {
  product: Product;
  isWishlisted?: boolean;
  onToggleWishlist?: (productId: number) => void;
  onSelect: (product: Product) => void;
  onQuickAdd?: (product: Product, e: React.MouseEvent) => void;
}

export const ProductCard: React.FC<ProductCardProps> = ({
  product,
  isWishlisted = false,
  onToggleWishlist,
  onSelect,
  onQuickAdd,
}) => {
  const photo = product.photos && product.photos.length > 0 ? product.photos[0] : '';

  const handleHeartClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    haptic.impact('light');
    if (onToggleWishlist) {
      onToggleWishlist(product.id);
    }
  };

  return (
    <div
      onClick={() => {
        haptic.selection();
        onSelect(product);
      }}
      className="group bg-white rounded-2xl border border-gray-200/80 shadow-[0_2px_8px_rgba(0,0,0,0.04)] hover:shadow-md transition-all duration-200 flex flex-col cursor-pointer active:scale-[0.98] overflow-hidden"
    >
      {/* Photo Container */}
      <div className="relative aspect-[4/5] bg-gray-100 overflow-hidden">
        {photo ? (
          <img
            src={photo}
            alt={product.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center p-4 text-center">
            <span className="text-2xl mb-1">⚡</span>
            <span className="text-[11px] font-bold text-gray-400 uppercase">BEK STYLE</span>
          </div>
        )}

        {/* Badges */}
        <div className="absolute top-2 left-2 flex flex-col gap-1 items-start z-10">
          {product.discount_percent && product.discount_percent > 0 ? (
            <span className="bg-rose-500 text-white text-[10px] font-extrabold px-1.5 py-0.5 rounded-md shadow-xs">
              -{product.discount_percent}%
            </span>
          ) : null}
          {product.is_new ? (
            <span className="bg-gray-900/85 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-md backdrop-blur-sm shadow-xs">
              Yangi
            </span>
          ) : null}
          {product.is_hit ? (
            <span className="bg-amber-500 text-white text-[10px] font-bold px-1.5 py-0.5 rounded-md shadow-xs">
              XIT
            </span>
          ) : null}
        </div>

        {/* Wishlist Heart Button */}
        <button
          onClick={handleHeartClick}
          aria-label="Sevimlilarga qo'shish"
          className="absolute top-2 right-2 w-7 h-7 rounded-full bg-white/90 backdrop-blur-sm border border-gray-200/80 flex items-center justify-center text-gray-400 hover:text-rose-500 active:scale-90 transition-all shadow-xs z-10"
        >
          <Heart
            size={14}
            className={isWishlisted ? 'fill-rose-500 text-rose-500' : 'text-gray-500'}
          />
        </button>

        {/* Quick Add Button */}
        {onQuickAdd && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              haptic.impact('medium');
              onQuickAdd(product, e);
            }}
            aria-label="Savatga tezkor qo'shish"
            className="absolute bottom-2 right-2 w-8 h-8 rounded-full bg-emerald-600 hover:bg-emerald-700 text-white flex items-center justify-center shadow-md active:scale-90 transition-all z-10"
          >
            <Plus size={16} strokeWidth={2.5} />
          </button>
        )}
      </div>

      {/* Info Container */}
      <div className="p-3 flex flex-col flex-1 justify-between gap-1.5">
        <div>
          {product.category_name && (
            <span className="text-[10px] font-semibold text-emerald-700 tracking-wider uppercase block">
              {product.category_name}
            </span>
          )}
          <h3 className="text-xs sm:text-sm font-bold text-gray-900 line-clamp-2 leading-snug">
            {product.title}
          </h3>
        </div>

        <div>
          <div className="flex items-baseline gap-1.5 flex-wrap">
            <span className="text-sm font-extrabold text-gray-900">
              {product.formatted_price}
            </span>
            {product.formatted_old_price && (
              <span className="text-[11px] text-gray-400 line-through">
                {product.formatted_old_price}
              </span>
            )}
          </div>

          {product.sizes && product.sizes.length > 0 && (
            <div className="flex items-center gap-1 mt-1">
              <span className="text-[10px] text-gray-500 font-medium">
                O'lcham: {product.sizes.slice(0, 3).join(', ')}
                {product.sizes.length > 3 ? '+' : ''}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
