import React, { useState, useEffect } from 'react';
import { ArrowLeft, Check, Minus, Plus, ShoppingBag, Truck } from 'lucide-react';
import { Product } from '../types';
import { haptic, setBackButton } from '../utils/telegram';

interface ProductDetailPageProps {
  product: Product;
  onClose: () => void;
  onAddToCart: (product: Product, size: string | null, color: string | null, qty: number) => Promise<void>;
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

  useEffect(() => {
    setBackButton(true, onClose);
    window.scrollTo({ top: 0, behavior: 'instant' });
    return () => {
      setBackButton(false);
    };
  }, [onClose]);

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
    <div className="min-h-screen bg-[#111315] text-[#F5F2E9] pb-32 animate-fadeIn">
      {/* Top Floating Nav */}
      <div className="sticky top-0 z-30 bg-[#111315]/80 backdrop-blur-md px-4 py-3 flex items-center justify-between border-b border-[#26292E]">
        <button
          onClick={onClose}
          className="w-9 h-9 rounded-full bg-[#1A1D20] border border-[#26292E] flex items-center justify-center text-[#F5F2E9] active:scale-90 transition-transform"
        >
          <ArrowLeft size={18} />
        </button>

        <span className="text-xs font-black uppercase tracking-wider text-[#8E95A0]">
          {product.category_name || 'BEK STYLE'}
        </span>

        <div className="w-9" />
      </div>

      <div className="max-w-lg mx-auto">
        {/* Main Photo & Slider */}
        <div className="relative aspect-[4/5] bg-[#1A1D20] overflow-hidden">
          {photos[selectedPhotoIndex] ? (
            <img
              src={photos[selectedPhotoIndex]}
              alt={product.title}
              className="w-full h-full object-cover transition-all duration-300"
            />
          ) : (
            <div className="w-full h-full flex flex-col items-center justify-center text-[#8E95A0]">
              <span className="text-4xl mb-2">⚡</span>
              <span className="text-xs font-bold uppercase">BEK STYLE</span>
            </div>
          )}

          {/* Badges */}
          <div className="absolute top-3 left-3 flex flex-col gap-1.5">
            {product.discount_percent && product.discount_percent > 0 && (
              <span className="bg-[#C7F464] text-[#111315] text-xs font-black px-2.5 py-1 rounded-lg uppercase tracking-wider shadow">
                -{product.discount_percent}%
              </span>
            )}
            {product.is_new && (
              <span className="bg-[#111315]/80 backdrop-blur-sm border border-[#26292E] text-[#F5F2E9] text-xs font-bold px-2.5 py-1 rounded-lg uppercase tracking-wider">
                Yangi Model
              </span>
            )}
          </div>

          {/* Carousel Thumbnail Dots / Preview */}
          {photos.length > 1 && (
            <div className="absolute bottom-3 left-0 right-0 flex justify-center gap-2 px-4">
              {photos.map((_, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    haptic.selection();
                    setSelectedPhotoIndex(idx);
                  }}
                  className={`h-2 rounded-full transition-all ${
                    selectedPhotoIndex === idx
                      ? 'w-6 bg-[#C7F464]'
                      : 'w-2 bg-[#F5F2E9]/40'
                  }`}
                />
              ))}
            </div>
          )}
        </div>

        {/* Info & Options */}
        <div className="p-4 space-y-5">
          {/* Title & Price */}
          <div>
            <h1 className="text-lg font-black text-[#F5F2E9] leading-snug">
              {product.title}
            </h1>
            <div className="mt-2 flex items-baseline gap-2.5">
              <span className="text-2xl font-black text-[#C7F464]">
                {product.formatted_price}
              </span>
              {product.formatted_old_price && (
                <span className="text-sm text-[#8E95A0] line-through">
                  {product.formatted_old_price}
                </span>
              )}
            </div>
          </div>

          {/* Color Selection */}
          {product.colors && product.colors.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-[#8E95A0] uppercase tracking-wider">
                  Rang: <span className="text-[#F5F2E9]">{selectedColor}</span>
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
                          ? 'bg-[#C7F464]/10 border-[#C7F464] text-[#C7F464] shadow-sm'
                          : 'bg-[#1A1D20] border-[#26292E] text-[#8E95A0] hover:text-[#F5F2E9]'
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
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-[#8E95A0] uppercase tracking-wider">
                  O'lcham: <span className="text-[#F5F2E9]">{selectedSize}</span>
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
                      className={`min-w-[44px] px-3.5 py-2 rounded-xl text-xs font-black transition-all border text-center ${
                        isSelected
                          ? 'bg-[#C7F464] border-[#C7F464] text-[#111315] shadow-md scale-105'
                          : 'bg-[#1A1D20] border-[#26292E] text-[#F5F2E9] hover:border-[#C7F464]/40'
                      }`}
                    >
                      {size}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Quantity selector */}
          <div className="flex items-center justify-between py-2 border-t border-b border-[#26292E]">
            <span className="text-xs font-bold text-[#8E95A0] uppercase tracking-wider">
              Miqdor
            </span>
            <div className="flex items-center gap-3 bg-[#1A1D20] border border-[#26292E] rounded-xl px-2 py-1">
              <button
                onClick={() => {
                  haptic.selection();
                  setQuantity((q) => Math.max(1, q - 1));
                }}
                disabled={quantity <= 1}
                className="w-7 h-7 rounded-lg bg-[#111315] flex items-center justify-center text-[#F5F2E9] disabled:opacity-30 active:scale-95"
              >
                <Minus size={14} />
              </button>
              <span className="text-sm font-black text-[#F5F2E9] w-6 text-center">
                {quantity}
              </span>
              <button
                onClick={() => {
                  haptic.selection();
                  setQuantity((q) => Math.min(10, q + 1));
                }}
                disabled={quantity >= 10}
                className="w-7 h-7 rounded-lg bg-[#111315] flex items-center justify-center text-[#F5F2E9] disabled:opacity-30 active:scale-95"
              >
                <Plus size={14} />
              </button>
            </div>
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <h3 className="text-xs font-bold text-[#8E95A0] uppercase tracking-wider">
              Tavsif
            </h3>
            <p className="text-xs text-[#8E95A0] leading-relaxed whitespace-pre-line">
              {product.description || "Pinduoduodan buyurtma asosida olib kelinadigan sifatli yigitlar kiyimi."}
            </p>
          </div>

          {/* Delivery Note */}
          <div className="flex items-start gap-3 bg-[#1A1D20] border border-[#26292E] rounded-2xl p-3.5 text-xs text-[#8E95A0]">
            <Truck size={18} className="text-[#C7F464] shrink-0 mt-0.5" />
            <div>
              <span className="font-bold text-[#F5F2E9] block mb-0.5">Tezkor yetkazib berish</span>
              O'zbekiston bo'ylab 10-18 kun ichida yetkaziladi. To'lov qabul qilingandan keyin buyurtma jarayoni boshlanadi.
            </div>
          </div>
        </div>
      </div>

      {/* Sticky Bottom Add to Cart Bar */}
      <div className="fixed bottom-0 left-0 right-0 z-40 bg-[#111315]/95 backdrop-blur-md border-t border-[#26292E] p-4 pb-safe">
        <div className="max-w-lg mx-auto flex items-center gap-3">
          <button
            onClick={handleAdd}
            disabled={isAddingToCart}
            className={`flex-1 py-3.5 px-6 rounded-2xl font-black text-xs uppercase tracking-wider flex items-center justify-center gap-2 transition-all shadow-lg active:scale-98 ${
              addedSuccess
                ? 'bg-emerald-500 text-white'
                : 'bg-[#C7F464] text-[#111315] hover:bg-[#b5e350]'
            }`}
          >
            {addedSuccess ? (
              <>
                <Check size={16} strokeWidth={3} />
                Savatga qo'shildi!
              </>
            ) : (
              <>
                <ShoppingBag size={16} strokeWidth={2.5} />
                Savatga qo'shish • {formattedTotal}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
