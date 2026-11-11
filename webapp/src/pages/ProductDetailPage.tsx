import React, { useState } from 'react';
import { ArrowLeft, Heart, ShoppingBag, Send, Package, Clock, Truck, CreditCard, ZoomIn, Check, Ruler, Share2, ShieldCheck, Sparkles } from 'lucide-react';
import { Product, ShopSettings } from '../types';
import { formatPrice, calculateCargo, getMediaUrl } from '../utils/format';
import { haptic, openTelegramLink, playBoutiqueSound, shareToStory } from '../utils/telegram';
import { triggerPetalBurst } from '../components/PetalBurst';
import { Translations } from '../i18n';

interface ProductDetailPageProps {
  product: Product;
  settings: ShopSettings;
  isWishlisted: boolean;
  onToggleWishlist: (productId: number) => void;
  onAddToCart: (product: Product, size?: string, color?: string) => void;
  onBack: () => void;
  t: Translations;
}

export const ProductDetailPage: React.FC<ProductDetailPageProps> = ({
  product,
  settings,
  isWishlisted,
  onToggleWishlist,
  onAddToCart,
  onBack,
  t,
}) => {
  const [activePhotoIndex, setActivePhotoIndex] = useState(0);
  const [selectedSize, setSelectedSize] = useState<string | undefined>(product.sizes?.[0]);
  const [selectedColor, setSelectedColor] = useState<string | undefined>(product.colors?.[0]);
  const [isZoomOpen, setIsZoomOpen] = useState(false);
  const [justAdded, setJustAdded] = useState(false);

  // Smart Fit Advisor (#9)
  const [isFitModalOpen, setIsFitModalOpen] = useState(false);
  const [fitHeight, setFitHeight] = useState(165);
  const [fitWeight, setFitWeight] = useState(55);

  // Story-to-Earn (#5)
  const [storyShared, setStoryShared] = useState(false);

  const photos = product.photos && product.photos.length > 0 ? product.photos : ['placeholder'];
  const cargoEstimate = calculateCargo(product.weight_grams, settings.cargo_rate || 12000);

  const calculateRecommendedSize = (h: number, w: number): string => {
    if (h < 158 && w < 48) return 'S';
    if (h < 165 && w < 56) return 'M';
    if (h < 172 && w < 65) return 'L';
    if (h < 178 && w < 74) return 'XL';
    return '2XL';
  };

  const recommendedSize = calculateRecommendedSize(fitHeight, fitWeight);

  const handleAddToCart = (e: React.MouseEvent) => {
    if (!product.in_stock) return;
    haptic.notification('success');
    playBoutiqueSound('chime');
    triggerPetalBurst(0.5, 0.7);
    onAddToCart(product, selectedSize, selectedColor);

    setJustAdded(true);
    setTimeout(() => setJustAdded(false), 2000);
  };

  const handleShareStory = () => {
    haptic.impact('medium');
    playBoutiqueSound('chime');
    const photoUrl = photos[0] ? getMediaUrl(photos[0]) : '';
    shareToStory(photoUrl, `🌙 Moonlight Chinese Shop — ${product.title} ✨ Maxsus 15% chegirma: STORY15`);
    setStoryShared(true);
    triggerPetalBurst(0.5, 0.4);
    setTimeout(() => setStoryShared(false), 4000);
  };

  const handleDirectAsk = () => {
    haptic.impact('light');
    const rawContact = settings.contact_username || '+998939029799';
    const contact = rawContact.replace('@', '');
    const contactLink = rawContact.startsWith('+') || /^\d+$/.test(rawContact)
      ? `https://t.me/+${contact.replace('+', '')}`
      : `https://t.me/${contact}`;

    const text = encodeURIComponent(
      `Assalomu alaykum! 🌙 Moonlight Chinese Shop do'konidan ushbu mahsulot haqida so'ramoqchi edim:\n\n` +
      `✨ ${product.title}\n` +
      `💰 Narxi: ${formatPrice(product.price)}\n` +
      (selectedSize ? `📏 O'lcham: ${selectedSize}\n` : '') +
      (selectedColor ? `🎨 Rang: ${selectedColor}\n` : '') +
      `\nMavjudmi? 💌`
    );
    const sep = contactLink.includes('?') ? '&' : '?';
    openTelegramLink(`${contactLink}${sep}text=${text}`);
  };

  return (
    <div className="pb-32 bg-sakura-cream dark:bg-sakura-darkbg min-h-screen">
      {/* Top Floating Back Bar */}
      <div className="sticky top-0 z-30 flex items-center justify-between p-3.5 bg-white/80 dark:bg-sakura-darkcard/80 backdrop-blur-md border-b border-sakura-pink/20">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-2xl bg-sakura-blush/60 dark:bg-sakura-darkcardsoft text-sakura-plum dark:text-sakura-pink font-bold text-xs shadow-xs active:scale-95"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Orqaga</span>
        </button>

        <span className="text-xs font-bold text-sakura-rose uppercase">
          #{product.category}
        </span>

        <div className="flex items-center gap-2">
          {/* Stories Share Button (#5) */}
          <button
            onClick={handleShareStory}
            className="p-2 rounded-2xl bg-sakura-blush/60 dark:bg-sakura-darkcardsoft text-sakura-rose shadow-xs transition-all active:scale-125"
            title="Stories ga ulashish (-15%)"
          >
            <Share2 className="w-4 h-4" />
          </button>

          {/* Wishlist */}
          <button
            onClick={() => {
              haptic.impact('medium');
              onToggleWishlist(product.id);
            }}
            className={`p-2 rounded-2xl shadow-xs transition-all active:scale-125 ${
              isWishlisted
                ? 'bg-sakura-rose text-white shadow-sakura animate-heart-pop'
                : 'bg-sakura-blush/60 dark:bg-sakura-darkcardsoft text-sakura-plum/70'
            }`}
          >
            <Heart className={`w-4 h-4 ${isWishlisted ? 'fill-white stroke-white' : ''}`} />
          </button>
        </div>
      </div>

      {/* Story-to-earn notification toast */}
      {storyShared && (
        <div className="mx-4 mt-2 p-3 rounded-2xl bg-emerald-50 dark:bg-emerald-950/80 border border-emerald-300 dark:border-emerald-700 text-emerald-800 dark:text-emerald-200 text-xs flex items-center gap-2 shadow-sm animate-fade-in">
          <Sparkles className="w-4 h-4 text-emerald-600 shrink-0" />
          <div>
            <b>Stories ga ulashildi! 🎁</b>
            <div>15% chegirma promokodingiz: <code className="font-bold underline">STORY15</code></div>
          </div>
        </div>
      )}

      {/* Main Image Gallery */}
      <div className="relative mx-4 mt-2 rounded-3xl overflow-hidden bg-sakura-blush/40 dark:bg-sakura-darkcard shadow-sakura-sm">
        <div className="w-full aspect-square relative">
          <img
            src={getMediaUrl(photos[activePhotoIndex])}
            alt={product.title}
            className="w-full h-full object-cover"
          />

          {!product.in_stock && (
            <div className="absolute inset-0 bg-sakura-darkbg/70 backdrop-blur-[2px] flex items-center justify-center">
              <span className="px-4 py-1.5 rounded-full bg-sakura-rose text-white text-sm font-extrabold shadow-md">
                ❌ {t.soldOut}
              </span>
            </div>
          )}

          {/* Zoom button */}
          <button
            onClick={() => setIsZoomOpen(true)}
            className="absolute bottom-3 right-3 p-2 rounded-full bg-white/80 dark:bg-sakura-darkcard/80 backdrop-blur-md text-sakura-plum dark:text-white shadow-sm active:scale-90"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
        </div>

        {/* Thumbnail Dots / Strips */}
        {photos.length > 1 && (
          <div className="flex gap-2 p-3 overflow-x-auto justify-center bg-white/50 dark:bg-sakura-darkcard/50 backdrop-blur-sm">
            {photos.map((p, idx) => (
              <button
                key={idx}
                onClick={() => setActivePhotoIndex(idx)}
                className={`w-12 h-12 rounded-xl overflow-hidden border-2 transition-all shrink-0 ${
                  activePhotoIndex === idx
                    ? 'border-sakura-rose scale-105 shadow-sakura-sm'
                    : 'border-transparent opacity-60'
                }`}
              >
                <img src={getMediaUrl(p)} alt="" className="w-full h-full object-cover" />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Zoom Modal */}
      {isZoomOpen && (
        <div
          onClick={() => setIsZoomOpen(false)}
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center p-4 backdrop-blur-md"
        >
          <img
            src={getMediaUrl(photos[activePhotoIndex])}
            alt={product.title}
            className="max-w-full max-h-[85vh] object-contain rounded-2xl"
          />
          <button
            onClick={() => setIsZoomOpen(false)}
            className="absolute top-4 right-4 text-white text-lg font-bold bg-white/20 p-2 rounded-full w-10 h-10 flex items-center justify-center"
          >
            ✕
          </button>
        </div>
      )}

      {/* Product Information */}
      <div className="mx-4 mt-4 p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md shadow-sakura-sm border border-sakura-pink/20">
        <h2 className="text-lg sm:text-xl font-extrabold text-sakura-plum dark:text-white leading-tight">
          {product.title}
        </h2>

        {/* Price Row */}
        <div className="mt-2.5 flex items-baseline gap-2 flex-wrap">
          <span className="text-xl sm:text-2xl font-black text-sakura-rose dark:text-sakura-pink">
            {formatPrice(product.price)}
          </span>
          {product.old_price && product.old_price > product.price && (
            <span className="text-sm text-sakura-plum/40 line-through">
              {formatPrice(product.old_price)}
            </span>
          )}
          {cargoEstimate > 0 && (
            <span className="ml-auto text-xs font-bold text-sakura-plum/70 dark:text-sakura-blush/70 bg-sakura-blush/60 dark:bg-sakura-darkcardsoft px-2.5 py-1 rounded-full">
              📦 Kargo: ~{formatPrice(cargoEstimate)}
            </span>
          )}
        </div>

        {/* Size Picker + Smart Fit Advisor (#9) */}
        {product.sizes && product.sizes.length > 0 && (
          <div className="mt-4">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-bold text-sakura-plum/80 dark:text-sakura-blush/80">
                {t.selectSize}
              </span>
              <button
                onClick={() => {
                  haptic.impact('light');
                  setIsFitModalOpen(true);
                }}
                className="flex items-center gap-1 text-[11px] font-bold text-sakura-rose hover:underline"
              >
                <Ruler className="w-3.5 h-3.5" />
                <span>O'lchamni hisoblash</span>
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {product.sizes.map((s) => (
                <button
                  key={s}
                  onClick={() => {
                    haptic.selection();
                    setSelectedSize(s);
                  }}
                  className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    selectedSize === s
                      ? 'bg-sakura-rose text-white shadow-sakura scale-105'
                      : 'bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40 text-sakura-plum dark:text-sakura-blush'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Color Picker */}
        {product.colors && product.colors.length > 0 && (
          <div className="mt-3.5">
            <span className="text-xs font-bold text-sakura-plum/80 dark:text-sakura-blush/80 block mb-1.5">
              {t.selectColor}
            </span>
            <div className="flex flex-wrap gap-2">
              {product.colors.map((c) => (
                <button
                  key={c}
                  onClick={() => {
                    haptic.selection();
                    setSelectedColor(c);
                  }}
                  className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    selectedColor === c
                      ? 'bg-sakura-rose text-white shadow-sakura scale-105'
                      : 'bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/40 text-sakura-plum dark:text-sakura-blush'
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Description */}
        {product.description && (
          <div className="mt-4 pt-3 border-t border-sakura-pink/20">
            <p className="text-xs sm:text-sm text-sakura-plum/80 dark:text-sakura-blush/80 whitespace-pre-line leading-relaxed">
              {product.description}
            </p>
          </div>
        )}

        {/* Halol & Asl Mato Sifat Kafolati (#16) */}
        <div className="mt-4 p-3 rounded-2xl bg-amber-50/80 dark:bg-amber-950/40 border border-amber-200/80 dark:border-amber-800/60 flex items-start gap-2.5">
          <ShieldCheck className="w-5 h-5 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
          <div className="text-[11px] leading-relaxed text-amber-900 dark:text-amber-200">
            <span className="font-extrabold block">✨ Halol & Asl Mato Sifat Kafolati</span>
            Barcha kiyimlar Xitoyning sertifikatlangan fabrikalaridan to'g'ridan-to'g'ri olib kelinadi. Mato sifati va o'lchami rasmga 100% mos kelishiga kafolat beramiz.
          </div>
        </div>

        {/* Compulsory Order line on every product */}
        <div className="mt-3 p-3 rounded-2xl bg-sakura-blush/70 dark:bg-sakura-darkcardsoft text-center border border-sakura-pink/40">
          <p className="text-xs sm:text-sm font-extrabold text-sakura-darkrose dark:text-sakura-pink">
            {t.orderNotice}
          </p>
        </div>
      </div>

      {/* Smart Fit Modal (#9) */}
      {isFitModalOpen && (
        <div
          onClick={() => setIsFitModalOpen(false)}
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-sm rounded-3xl bg-white dark:bg-sakura-darkcard p-5 shadow-sakura-lg border border-sakura-pink/30 space-y-4"
          >
            <div className="flex items-center justify-between border-b border-sakura-pink/20 pb-2.5">
              <div className="flex items-center gap-2">
                <Ruler className="w-5 h-5 text-sakura-rose" />
                <h3 className="font-bold text-sm text-sakura-plum dark:text-white">Smart Fit Maslahatchisi</h3>
              </div>
              <button
                onClick={() => setIsFitModalOpen(false)}
                className="text-sakura-plum/60 hover:text-sakura-rose font-bold text-sm"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-sakura-plum/70 dark:text-sakura-blush/70 leading-relaxed">
              Xitoy kiyimlari o'lchamlari Yevropa o'lchamlaridan 1 ta kichikroq bo'lishi mumkin. Bo'yingiz va vazningizni kiriting:
            </p>

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-bold text-sakura-plum dark:text-white block mb-1">
                  Bo'y: <span className="text-sakura-rose">{fitHeight} sm</span>
                </label>
                <input
                  type="range"
                  min="145"
                  max="190"
                  value={fitHeight}
                  onChange={(e) => setFitHeight(Number(e.target.value))}
                  className="w-full accent-sakura-rose"
                />
              </div>

              <div>
                <label className="font-bold text-sakura-plum dark:text-white block mb-1">
                  Vazn: <span className="text-sakura-rose">{fitWeight} kg</span>
                </label>
                <input
                  type="range"
                  min="38"
                  max="95"
                  value={fitWeight}
                  onChange={(e) => setFitWeight(Number(e.target.value))}
                  className="w-full accent-sakura-rose"
                />
              </div>
            </div>

            <div className="p-3 rounded-2xl bg-sakura-blush/80 dark:bg-sakura-darkcardsoft text-center">
              <span className="text-[11px] text-sakura-plum/70 dark:text-sakura-blush/70 block">Sizga eng mos o'lcham:</span>
              <span className="text-2xl font-black text-sakura-rose">{recommendedSize}</span>
            </div>

            <button
              onClick={() => {
                haptic.notification('success');
                setSelectedSize(recommendedSize);
                setIsFitModalOpen(false);
              }}
              className="w-full py-2.5 rounded-2xl bg-sakura-rose text-white font-bold text-xs shadow-sakura active:scale-95 transition-transform"
            >
              {recommendedSize} o'lchamini tanlash ✨
            </button>
          </div>
        </div>
      )}

      {/* Fixed Shop Terms Card (Matching Channel Terms) */}
      <div className="mx-4 mt-3 p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md shadow-sakura-sm border border-sakura-pink/20">
        <h4 className="text-xs font-extrabold text-sakura-plum dark:text-white uppercase tracking-wider mb-2.5">
          {t.deliveryTerms}
        </h4>
        <div className="grid grid-cols-2 gap-2.5 text-xs">
          <div className="flex items-center gap-2 p-2 rounded-xl bg-sakura-cream/80 dark:bg-sakura-darkcardsoft">
            <Package className="w-4 h-4 text-sakura-rose shrink-0" />
            <div>
              <span className="text-[10px] text-sakura-plum/60 block">{t.cargoRateTitle}</span>
              <span className="font-bold">{formatPrice(settings.cargo_rate || 12000)} / 100g</span>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-xl bg-sakura-cream/80 dark:bg-sakura-darkcardsoft">
            <Clock className="w-4 h-4 text-sakura-rose shrink-0" />
            <div>
              <span className="text-[10px] text-sakura-plum/60 block">{t.deliveryTimeTitle}</span>
              <span className="font-bold">{settings.delivery_days || "10–15 kun"}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-xl bg-sakura-cream/80 dark:bg-sakura-darkcardsoft">
            <Truck className="w-4 h-4 text-sakura-rose shrink-0" />
            <div>
              <span className="text-[10px] text-sakura-plum/60 block">{t.deliveryScopeTitle}</span>
              <span className="font-bold">{settings.delivery_scope || "O'zbekiston bo'ylab"}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 rounded-xl bg-sakura-cream/80 dark:bg-sakura-darkcardsoft">
            <CreditCard className="w-4 h-4 text-sakura-rose shrink-0" />
            <div>
              <span className="text-[10px] text-sakura-plum/60 block">{t.prepaymentTitle}</span>
              <span className="font-bold">{settings.payment_terms || "100% oldindan to'lov"}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Bottom Sticky Action Bar */}
      <div className="fixed bottom-0 left-0 right-0 z-40 p-3 bg-white/95 dark:bg-sakura-darkcard/95 backdrop-blur-md border-t border-sakura-pink/30 pb-safe shadow-sakura-lg">
        <div className="max-w-md mx-auto flex items-center gap-2.5">
          {/* Ask Now Button */}
          <button
            onClick={handleDirectAsk}
            className="flex-1 py-3 px-3 rounded-2xl bg-sakura-blush dark:bg-sakura-darkcardsoft text-sakura-darkrose dark:text-sakura-pink font-extrabold text-xs flex items-center justify-center gap-1.5 shadow-xs border border-sakura-pink/40 active:scale-95 transition-transform"
          >
            <Send className="w-4 h-4" />
            <span>{t.orderNow}</span>
          </button>

          {/* Add to Bag Button */}
          <button
            onClick={handleAddToCart}
            disabled={!product.in_stock}
            className={`flex-[1.5] py-3 px-4 rounded-2xl font-black text-sm flex items-center justify-center gap-2 shadow-sakura active:scale-95 transition-all text-white ${
              !product.in_stock
                ? 'bg-gray-400 cursor-not-allowed opacity-60'
                : justAdded
                ? 'bg-emerald-500 scale-98'
                : 'bg-gradient-to-r from-sakura-pink via-sakura-rose to-sakura-darkrose hover:opacity-95'
            }`}
          >
            {justAdded ? (
              <>
                <Check className="w-4 h-4" />
                <span>{t.addedToBag}</span>
              </>
            ) : (
              <>
                <ShoppingBag className="w-4 h-4" />
                <span>{product.in_stock ? t.addToBag : t.soldOut}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
