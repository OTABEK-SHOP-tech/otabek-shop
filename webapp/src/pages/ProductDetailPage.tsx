import React, { useState, useEffect } from 'react';
import { ArrowLeft, Check, Minus, Plus, ShoppingBag, Truck, Info, Heart } from 'lucide-react';
import { Product } from '../types';
import { haptic, setBackButton } from '../utils/telegram';

interface ProductDetailPageProps {
  product: Product;
  onClose: () => void;
  onAddToCart: (
    product: Product,
    size: string | null,
    color: string | null,
    qty: number
  ) => Promise<void>;
  isAddingToCart?: boolean;
}

export const ProductDetailPage: React.FC<ProductDetailPageProps> = ({
  product,
  onClose,
  onAddToCart,
  isAddingToCart = false,
}) => {
  const [selectedPhotoIndex, setSelectedPhotoIndex] = useState(0);
  const [selectedColor, setSelectedColor] = useState<string | null>(
    product.colors && product.colors.length > 0 ? product.colors[0] : null
  );
  const [selectedSize, setSelectedSize] = useState<string | null>(
    product.sizes && product.sizes.length > 0 ? product.sizes[0] : null
  );
  const [quantity, setQuantity] = useState(1);
  const [addedSuccess, setAddedSuccess] = useState(false);
  const [isWishlisted, setIsWishlisted] = useState(false);

  useEffect(() => {
    setBackButton(true, onClose);
    window.scrollTo({ top: 0, behavior: 'instant' });
    try {
      const saved = localStorage.getItem('bek_wishlist');
      if (saved) {
        const list: number[] = JSON.parse(saved);
        setIsWishlisted(list.includes(product.id));
      }
    } catch {}

    return () => {
      setBackButton(false);
    };
  }, [onClose, product.id]);

  const toggleWishlist = () => {
    haptic.impact('light');
    try {
      const saved = localStorage.getItem('bek_wishlist');
      const list: number[] = saved ? JSON.parse(saved) : [];
      const next = list.includes(product.id)
        ? list.filter((id) => id !== product.id)
        : [...list, product.id];
      localStorage.setItem('bek_wishlist', JSON.stringify(next));
      setIsWishlisted(!isWishlisted);
    } catch {}
  };

  const photos = product.photos && product.photos.length > 0 ? product.photos : [''];

  const handleAdd = async () => {
    haptic.impact('medium');
    await onAddToCart(product, selectedSize, selectedColor, quantity);
    setAddedSuccess(true);
    setTimeout(() => setAddedSuccess(false), 2000);
  };

  const currentTotal = product.price * quantity;
  const formattedTotal = `${currentTotal.toLocaleString('ru-RU')} so'm`;

  return (
    <div className="min-h-screen bg-[#F8F9FA] text-gray-900 pb-36 animate-fadeIn">
      {/* Top Floating Nav */}
      <div className="sticky top-0 z-30 bg-white/90 backdrop-blur-md px-4 py-3 flex items-center justify-between border-b border-gray-200/80 shadow-xs">
        <button
          onClick={onClose}
          aria-label="Orqaga"
          className="w-9 h-9 rounded-full bg-gray-100 flex items-center justify-center text-gray-700 active:scale-90 transition-transform"
        >
          <ArrowLeft size={18} />
        </button>

        <span className="text-xs font-extrabold uppercase tracking-wider text-gray-700">
          {product.category_name || 'BEK STYLE'}
        </span>

        <button
          onClick={toggleWishlist}
          aria-label="Sevimlilar"
          className="w-9 h-9 rounded-full bg-gray-100 flex items-center justify-center text-gray-700 active:scale-90 transition-transform"
        >
          <Heart
            size={18}
            className={isWishlisted ? 'fill-rose-500 text-rose-500' : 'text-gray-500'}
          />
        </button>
      </div>

      <div className="max-w-lg mx-auto">
        {/* Main Photo Gallery */}
        <div className="relative aspect-[4/5] bg-gray-100 overflow-hidden">
          {photos[selectedPhotoIndex] ? (
            <img
              src={photos[selectedPhotoIndex]}
              alt={product.title}
              className="w-full h-full object-cover transition-all duration-300"
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center text-gray-400">
              <span className="text-4xl mb-2">⚡</span>
              <span className="text-xs font-bold uppercase">BEK STYLE</span>
            </div>
          )}

          {/* Badges */}
          <div className="absolute top-3 left-3 flex flex-col gap-1.5 z-10">
            {product.discount_percent && product.discount_percent > 0 && (
              <span className="bg-rose-500 text-white text-xs font-black px-2.5 py-1 rounded-lg uppercase tracking-wider shadow-sm">
                -{product.discount_percent}%
              </span>
            )}
            {product.is_new && (
              <span className="bg-gray-900/85 backdrop-blur-sm text-white text-xs font-bold px-2.5 py-1 rounded-lg uppercase tracking-wider shadow-sm">
                Yangi Model
              </span>
            )}
          </div>

          {/* Carousel Dots */}
          {photos.length > 1 && (
            <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-1.5 px-4 z-10">
              {photos.map((_, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    haptic.selection();
                    setSelectedPhotoIndex(idx);
                  }}
                  className={`h-2 rounded-full transition-all ${
                    selectedPhotoIndex === idx ? 'w-6 bg-emerald-600' : 'w-2 bg-white/70'
                  }`}
                />
              ))}
            </div>
          )}
        </div>

        {/* Thumbnail Preview Bar */}
        {photos.length > 1 && (
          <div className="flex items-center gap-2 px-4 py-2.5 overflow-x-auto no-scrollbar bg-white border-b border-gray-100">
            {photos.map((p, idx) => (
              <button
                key={idx}
                onClick={() => {
                  haptic.selection();
                  setSelectedPhotoIndex(idx);
                }}
                className={`w-14 h-14 rounded-xl overflow-hidden shrink-0 border-2 transition-all ${
                  selectedPhotoIndex === idx
                    ? 'border-emerald-600 ring-2 ring-emerald-500/20'
                    : 'border-transparent opacity-70 hover:opacity-100'
                }`}
              >
                <img src={p} alt="" className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
        )}

        {/* Info & Options Container */}
        <div className="p-4 space-y-5">
          {/* Title & Price */}
          <div className="bg-white rounded-2xl p-4 border border-gray-200/80 shadow-xs space-y-2">
            <h1 className="text-base sm:text-lg font-extrabold text-gray-900 leading-snug">
              {product.title}
            </h1>
            <div className="flex items-baseline gap-2.5">
              <span className="text-2xl font-black text-gray-900">
                {product.formatted_price}
              </span>
              {product.formatted_old_price && (
                <span className="text-sm text-gray-400 line-through">
                  {product.formatted_old_price}
                </span>
              )}
            </div>
          </div>

          {/* Color Selection */}
          {product.colors && product.colors.length > 0 && (
            <div className="bg-white rounded-2xl p-4 border border-gray-200/80 shadow-xs space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                  Rang: <span className="text-gray-900 font-extrabold">{selectedColor}</span>
                </span>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                {product.colors.map((color) => {
                  const isSelected = selectedColor === color;
                  return (
                    <button
                      key={color}
                      onClick={() => {
                        haptic.selection();
                        setSelectedColor(color);
                      }}
                      className={`px-3.5 py-2 rounded-xl text-xs font-bold transition-all border ${
                        isSelected
                          ? 'bg-emerald-50 border-emerald-600 text-emerald-800 ring-1 ring-emerald-600'
                          : 'bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100'
                      }`}
                    >
                      {color}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Size Selection */}
          {product.sizes && product.sizes.length > 0 && (
            <div className="bg-white rounded-2xl p-4 border border-gray-200/80 shadow-xs space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                  O'lcham: <span className="text-gray-900 font-extrabold">{selectedSize}</span>
                </span>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                {product.sizes.map((size) => {
                  const isSelected = selectedSize === size;
                  return (
                    <button
                      key={size}
                      onClick={() => {
                        haptic.selection();
                        setSelectedSize(size);
                      }}
                      className={`min-w-[44px] px-3.5 py-2 rounded-xl text-xs font-extrabold transition-all border text-center ${
                        isSelected
                          ? 'bg-gray-900 border-gray-900 text-white shadow-xs'
                          : 'bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100'
                      }`}
                    >
                      {size}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Quantity Selector */}
          <div className="bg-white rounded-2xl p-4 border border-gray-200/80 shadow-xs flex items-center justify-between">
            <span className="text-xs font-bold text-gray-700 uppercase">Miqdor</span>
            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  if (quantity > 1) {
                    haptic.selection();
                    setQuantity(quantity - 1);
                  }
                }}
                disabled={quantity <= 1}
                className="w-8 h-8 rounded-xl bg-gray-100 text-gray-700 flex items-center justify-center font-bold active:scale-95 disabled:opacity-30"
              >
                <Minus size={15} />
              </button>
              <span className="font-extrabold text-sm text-gray-900 w-6 text-center">
                {quantity}
              </span>
              <button
                onClick={() => {
                  haptic.selection();
                  setQuantity(quantity + 1);
                }}
                className="w-8 h-8 rounded-xl bg-gray-100 text-gray-700 flex items-center justify-center font-bold active:scale-95"
              >
                <Plus size={15} />
              </button>
            </div>
          </div>

          {/* Cargo Warning Note (Required: Cargo haqi tortilgandan keyin alohida hisoblanadi) */}
          <div className="bg-amber-50 border border-amber-200/80 rounded-2xl p-3.5 flex items-start gap-2.5">
            <Info size={17} className="text-amber-600 shrink-0 mt-0.5" />
            <div className="text-xs text-amber-900 space-y-0.5">
              <p className="font-bold">Yetkazish va Cargo haqida:</p>
              <p className="text-amber-800/90 leading-relaxed text-[11px]">
                Cargo haqi tortilgandan keyin alohida hisoblanadi. Buyurtma Toshkentga yetib kelgach,
                haqiqiy vazn bo'yicha hisob-kitob qilinadi.
              </p>
            </div>
          </div>

          {/* Description */}
          {product.description && (
            <div className="bg-white rounded-2xl p-4 border border-gray-200/80 shadow-xs space-y-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500">
                Tavsif
              </h3>
              <p className="text-xs text-gray-600 leading-relaxed whitespace-pre-line">
                {product.description}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Sticky Bottom Action Bar */}
      <div className="fixed bottom-0 left-0 right-0 z-30 bg-white/95 backdrop-blur-md border-t border-gray-200/80 p-3.5 pb-safe shadow-[0_-4px_16px_rgba(0,0,0,0.06)]">
        <div className="max-w-lg mx-auto flex items-center gap-3">
          <div className="flex-1">
            <span className="text-[11px] font-semibold text-gray-500 block">
              Jami (mahsulot uchun):
            </span>
            <span className="text-base font-extrabold text-gray-900">{formattedTotal}</span>
          </div>

          <button
            onClick={handleAdd}
            disabled={isAddingToCart || !product.in_stock}
            className={`flex-1 py-3 px-5 rounded-2xl font-bold text-xs sm:text-sm flex items-center justify-center gap-2 active:scale-95 transition-all shadow-md ${
              addedSuccess
                ? 'bg-emerald-600 text-white'
                : 'bg-emerald-600 hover:bg-emerald-700 text-white disabled:bg-gray-300'
            }`}
          >
            {addedSuccess ? (
              <>
                <Check size={17} />
                <span>Qo'shildi!</span>
              </>
            ) : (
              <>
                <ShoppingBag size={17} />
                <span>Savatga qo'shish</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
