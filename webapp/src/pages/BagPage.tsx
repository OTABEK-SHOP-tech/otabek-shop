import React, { useEffect, useState } from 'react';
import { Trash2, Plus, Minus, Send, Copy, Check, ShoppingBag, ArrowRight, Truck, Coins, Sparkles, ShieldCheck } from 'lucide-react';
import { CartSummary, Order, ShopSettings, UserCashback } from '../types';
import { formatPrice, getMediaUrl } from '../utils/format';
import { getTelegramWebApp, haptic, openTelegramLink, playBoutiqueSound } from '../utils/telegram';
import { triggerPetalBurst } from '../components/PetalBurst';
import { EmptyState } from '../components/EmptyState';
import { Translations } from '../i18n';

interface BagPageProps {
  cart: CartSummary | null;
  settings: ShopSettings;
  onUpdateQty: (itemId: number, newQty: number) => void;
  onRemoveItem: (itemId: number) => void;
  onClearCart: () => void;
  onOrderSuccess: (order: Order) => void;
  onContinueShopping: () => void;
  t: Translations;
  initData: string;
}

export const BagPage: React.FC<BagPageProps> = ({
  cart,
  settings,
  onUpdateQty,
  onRemoveItem,
  onClearCart,
  onOrderSuccess,
  onContinueShopping,
  t,
  initData,
}) => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [completedOrder, setCompletedOrder] = useState<Order | null>(null);
  const [copied, setCopied] = useState(false);

  // Cashback state (#24)
  const [cashbackInfo, setCashbackInfo] = useState<UserCashback | null>(null);
  const [useCashback, setUseCashback] = useState(false);

  const items = cart?.items || [];
  const hasItems = items.length > 0;

  // Load cashback info from backend
  useEffect(() => {
    if (!initData) return;
    fetch('/api/orders/me/cashback', {
      headers: {
        'X-Telegram-Init-Data': initData,
      },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: UserCashback | null) => {
        if (data) setCashbackInfo(data);
      })
      .catch(() => {});
  }, [initData]);

  // Max cashback allowed is 20% of subtotal
  const rawSubtotal = cart?.subtotal || 0;
  const maxAllowedCashback = Math.min(
    cashbackInfo?.cashback_balance || 0,
    Math.floor(rawSubtotal * 0.2)
  );

  const cashbackDiscount = useCashback ? maxAllowedCashback : 0;
  const finalPayableTotal = Math.max(0, (cart?.grand_total || 0) - cashbackDiscount);

  // Handle Telegram MainButton
  useEffect(() => {
    const tg = getTelegramWebApp();
    if (!tg?.MainButton) return;

    if (hasItems && !completedOrder) {
      const btnText = cashbackDiscount > 0
        ? `${t.checkoutButton} (-${formatPrice(cashbackDiscount)})`
        : t.checkoutButton;
      tg.MainButton.setText(btnText);
      tg.MainButton.show();
      tg.MainButton.enable();

      const handleMainButtonClick = () => {
        handleCheckout();
      };

      tg.MainButton.onClick(handleMainButtonClick);
      return () => {
        tg.MainButton.offClick(handleMainButtonClick);
        tg.MainButton.hide();
      };
    } else {
      tg.MainButton.hide();
    }
  }, [hasItems, completedOrder, t.checkoutButton, cashbackDiscount]);

  const handleCheckout = async () => {
    if (!hasItems || isSubmitting) return;

    setIsSubmitting(true);
    const tg = getTelegramWebApp();
    tg?.MainButton?.showProgress();
    haptic.impact('heavy');

    try {
      const resp = await fetch('/api/orders', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Telegram-Init-Data': initData,
        },
        body: JSON.stringify({
          use_cashback: useCashback ? maxAllowedCashback : 0,
        }),
      });

      if (!resp.ok) {
        throw new Error('Order creation failed');
      }

      const orderData: Order = await resp.json();
      setCompletedOrder(orderData);
      triggerPetalBurst(0.5, 0.4);
      playBoutiqueSound('success');
      haptic.notification('success');
      onOrderSuccess(orderData);
    } catch (err) {
      console.error(err);
      haptic.notification('error');
      alert("Buyurtma berishda xatolik yuz berdi. Iltimos, qayta urinib ko'ring.");
    } finally {
      setIsSubmitting(false);
      tg?.MainButton?.hideProgress();
      tg?.MainButton?.hide();
    }
  };

  const handleCopyCodeBlock = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    haptic.notification('success');
    playBoutiqueSound('tap');
    setTimeout(() => setCopied(false), 2500);
  };

  // SUCCESS VIEW AFTER CHECKOUT
  if (completedOrder) {
    const rawContact = settings.contact_username || '+998939029799';
    const contact = rawContact.replace('@', '');
    const contactLink = rawContact.startsWith('+') || /^\d+$/.test(rawContact)
      ? `https://t.me/+${contact.replace('+', '')}`
      : `https://t.me/${contact}`;

    const copyableSummary =
      `🌙 Moonlight Chinese Shop — Buyurtma #${completedOrder.id}\n` +
      `Mijoz: ${completedOrder.customer_name}\n\n` +
      completedOrder.items_snapshot
        .map(
          (it, i) =>
            `${i + 1}. ${it.title} ${it.size ? `(${it.size})` : ''} ${it.color ? `(${it.color})` : ''} — ${it.qty} dona (${formatPrice(it.price * it.qty)})`
        )
        .join('\n') +
      `\n\nJami: ${formatPrice(completedOrder.total)}\n` +
      (completedOrder.cashback_used && completedOrder.cashback_used > 0
        ? `💰 Keshbek ishlatildi: -${formatPrice(completedOrder.cashback_used)}\n`
        : '') +
      (completedOrder.estimated_cargo > 0
        ? `📦 Taxminiy kargo: ${formatPrice(completedOrder.estimated_cargo)}\n`
        : '') +
      `📍 Kargo bosqichi: ${completedOrder.formatted_cargo_stage || "Xitoy omborida"}`;

    const stages = [
      { key: 'china_warehouse', label: 'Xitoy omborida', emoji: '🏬' },
      { key: 'in_transit_border', label: 'Chegaradan o\'tmoqda', emoji: '🚚' },
      { key: 'customs_clearance', label: 'Bojxona', emoji: '📋' },
      { key: 'tashkent_hub', label: 'Toshkent xabida', emoji: '🏢' },
      { key: 'delivering', label: 'Yetkazilmoqda', emoji: '🎁' },
    ];

    const currentStageIdx = stages.findIndex((s) => s.key === completedOrder.cargo_stage) >= 0
      ? stages.findIndex((s) => s.key === completedOrder.cargo_stage)
      : 0;

    return (
      <div className="p-4 pb-28 max-w-md mx-auto text-center animate-scale-in">
        <div className="w-20 h-20 mx-auto my-3 rounded-full bg-sakura-blush dark:bg-sakura-darkcardsoft flex items-center justify-center text-4xl shadow-sakura">
          🌸
        </div>
        <h2 className="text-xl font-extrabold text-sakura-darkrose dark:text-sakura-pink">
          {t.orderSuccessTitle}
        </h2>
        <p className="text-xs text-sakura-plum/80 dark:text-sakura-blush/80 mt-1.5 px-4">
          {t.orderSuccessSubtitle}
        </p>

        {/* 5-Stage Live Cargo Radar (#26) */}
        <div className="mt-4 p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/30 shadow-sakura-sm text-left">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-sakura-rose flex items-center gap-1.5">
              <Truck className="w-4 h-4" />
              <span>Jonli Kargo Radari (#26)</span>
            </span>
            <span className="text-[11px] font-extrabold text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/60 px-2.5 py-0.5 rounded-full border border-amber-300 dark:border-amber-700">
              {completedOrder.formatted_cargo_stage || "Xitoy omborida"}
            </span>
          </div>

          <div className="relative flex items-center justify-between mt-4 px-2">
            <div className="absolute left-4 right-4 top-1/2 -translate-y-1/2 h-1 bg-sakura-pink/30 z-0" />
            <div
              className="absolute left-4 top-1/2 -translate-y-1/2 h-1 bg-sakura-rose transition-all duration-500 z-0"
              style={{ width: `${(currentStageIdx / (stages.length - 1)) * 85}%` }}
            />
            {stages.map((st, idx) => {
              const isPastOrCurrent = idx <= currentStageIdx;
              return (
                <div key={st.key} className="relative z-10 flex flex-col items-center">
                  <div
                    className={`w-7 h-7 rounded-full flex items-center justify-center text-xs transition-all ${
                      isPastOrCurrent
                        ? 'bg-sakura-rose text-white shadow-sakura scale-110'
                        : 'bg-white dark:bg-sakura-darkcard border-2 border-sakura-pink/40 text-gray-400'
                    }`}
                  >
                    {st.emoji}
                  </div>
                  <span className="text-[9px] font-bold text-sakura-plum/80 dark:text-sakura-blush/80 mt-1 max-w-[50px] text-center leading-tight">
                    {st.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Copyable Summary Card */}
        <div className="mt-4 p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/30 shadow-sakura-sm text-left">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold text-sakura-rose">
              Buyurtma #{completedOrder.id}
            </span>
            <button
              onClick={() => handleCopyCodeBlock(copyableSummary)}
              className="flex items-center gap-1 px-3 py-1 rounded-xl bg-sakura-blush dark:bg-sakura-darkcardsoft text-sakura-rose font-bold text-xs shadow-xs active:scale-95 transition-transform"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? t.copied : t.copySummary}</span>
            </button>
          </div>

          <pre className="p-3 rounded-2xl bg-sakura-cream dark:bg-sakura-darkbg text-[11px] font-mono text-sakura-plum dark:text-sakura-blush overflow-x-auto whitespace-pre-wrap leading-relaxed select-all">
            {copyableSummary}
          </pre>
        </div>

        {/* Message Admin Button */}
        <div className="mt-4 flex flex-col gap-2.5">
          <button
            onClick={() => {
              const sep = contactLink.includes('?') ? '&' : '?';
              const url = `${contactLink}${sep}text=${encodeURIComponent(copyableSummary)}`;
              openTelegramLink(url);
            }}
            className="w-full py-3.5 px-4 rounded-2xl bg-gradient-to-r from-sakura-rose to-sakura-darkrose text-white font-black text-sm flex items-center justify-center gap-2 shadow-sakura active:scale-95 transition-transform"
          >
            <Send className="w-4 h-4" />
            <span>{t.messageAdminButton}</span>
          </button>

          <button
            onClick={onContinueShopping}
            className="w-full py-3 px-4 rounded-2xl bg-white/80 dark:bg-sakura-darkcard/80 text-sakura-plum dark:text-white font-bold text-xs flex items-center justify-center gap-1.5 border border-sakura-pink/30 active:scale-95 transition-transform"
          >
            <span>{t.continueShopping}</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  }

  // EMPTY BAG VIEW
  if (!hasItems) {
    return (
      <div className="p-4 pb-28 max-w-md mx-auto">
        <EmptyState
          title={t.emptyBag}
          subtitle={t.emptyBagSubtitle}
          actionButton={{
            text: t.continueShopping,
            onClick: onContinueShopping,
          }}
        />
      </div>
    );
  }

  return (
    <div className="p-4 pb-32 max-w-md mx-auto animate-fade-in">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg sm:text-xl font-extrabold text-sakura-plum dark:text-white">
          {t.bag} ({cart?.total_items || 0})
        </h2>
        <button
          onClick={onClearCart}
          className="text-xs font-bold text-rose-500 hover:text-rose-600 active:scale-95 transition-transform"
        >
          Tozalash
        </button>
      </div>

      {/* Cart Items List */}
      <div className="space-y-2.5">
        {items.map((item) => (
          <div
            key={item.id}
            className="flex items-center gap-3 p-3 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-sakura-xs"
          >
            {/* Thumbnail */}
            <div className="w-16 h-16 rounded-2xl overflow-hidden shrink-0 bg-sakura-blush">
              <img
                src={getMediaUrl(item.product_photo)}
                alt={item.product_title}
                className="w-full h-full object-cover"
              />
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <h4 className="text-xs sm:text-sm font-bold text-sakura-plum dark:text-white line-clamp-1">
                {item.product_title}
              </h4>
              <div className="flex items-center gap-2 text-[11px] text-sakura-plum/70 dark:text-sakura-blush/70 mt-0.5">
                {item.size && <span>O'lcham: {item.size}</span>}
                {item.color && <span>Rang: {item.color}</span>}
              </div>
              <span className="text-xs font-black text-sakura-rose dark:text-sakura-pink block mt-1">
                {formatPrice(item.item_total)}
              </span>
            </div>

            {/* Qty +/- Controls */}
            <div className="flex items-center gap-1.5 bg-sakura-cream dark:bg-sakura-darkcardsoft p-1 rounded-2xl border border-sakura-pink/30">
              <button
                onClick={() => {
                  haptic.selection();
                  playBoutiqueSound('tap');
                  if (item.qty > 1) {
                    onUpdateQty(item.id, item.qty - 1);
                  } else {
                    onRemoveItem(item.id);
                  }
                }}
                className="p-1 rounded-xl hover:bg-sakura-pink/20 active:scale-90"
              >
                {item.qty === 1 ? <Trash2 className="w-3.5 h-3.5 text-rose-500" /> : <Minus className="w-3.5 h-3.5" />}
              </button>

              <span className="text-xs font-extrabold w-5 text-center">{item.qty}</span>

              <button
                onClick={() => {
                  haptic.selection();
                  playBoutiqueSound('tap');
                  onUpdateQty(item.id, item.qty + 1);
                }}
                className="p-1 rounded-xl hover:bg-sakura-pink/20 active:scale-90"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* 2% Cashback System Integration (#24) */}
      {cashbackInfo && cashbackInfo.cashback_balance > 0 && maxAllowedCashback > 0 && (
        <div className="mt-4 p-3.5 rounded-3xl bg-gradient-to-r from-amber-50 to-pink-50 dark:from-amber-950/40 dark:to-pink-950/40 border border-amber-200/80 dark:border-amber-800/60 shadow-sakura-xs">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Coins className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0" />
              <div>
                <span className="text-xs font-bold text-amber-900 dark:text-amber-200 block">
                  Keshbek balansi: {cashbackInfo.formatted_cashback_balance}
                </span>
                <span className="text-[10px] text-amber-800/70 dark:text-amber-300/70">
                  Ushbu buyurtmada 20% gacha (-{formatPrice(maxAllowedCashback)}) ishlatish
                </span>
              </div>
            </div>

            <button
              onClick={() => {
                haptic.impact('medium');
                playBoutiqueSound('chime');
                setUseCashback(!useCashback);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-extrabold transition-all active:scale-95 ${
                useCashback
                  ? 'bg-amber-600 text-white shadow-xs'
                  : 'bg-white dark:bg-sakura-darkcard text-amber-800 dark:text-amber-200 border border-amber-300'
              }`}
            >
              {useCashback ? '✓ Qo\'llandi' : 'Qo\'llash'}
            </button>
          </div>
        </div>
      )}

      {/* Cart Summary Card */}
      <div className="mt-4 p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/30 shadow-sakura-sm">
        <div className="flex justify-between text-xs py-1">
          <span className="text-sakura-plum/70 dark:text-sakura-blush/70">{t.subtotal}:</span>
          <span className="font-extrabold">{cart?.formatted_subtotal}</span>
        </div>
        {cart?.estimated_cargo ? (
          <div className="flex justify-between text-xs py-1">
            <span className="text-sakura-plum/70 dark:text-sakura-blush/70">{t.estimatedCargo}:</span>
            <span className="font-extrabold">{cart?.formatted_estimated_cargo}</span>
          </div>
        ) : null}
        {useCashback && maxAllowedCashback > 0 && (
          <div className="flex justify-between text-xs py-1 text-emerald-600 dark:text-emerald-400 font-bold">
            <span>Keshbek chegirmasi (20%):</span>
            <span>-{formatPrice(maxAllowedCashback)}</span>
          </div>
        )}
        <div className="my-2 border-t border-sakura-pink/20" />
        <div className="flex justify-between text-sm sm:text-base py-1">
          <span className="font-black text-sakura-plum dark:text-white">{t.grandTotal}:</span>
          <span className="font-black text-sakura-rose dark:text-sakura-pink">
            {formatPrice(finalPayableTotal)}
          </span>
        </div>
        <p className="text-[10px] text-sakura-plum/60 dark:text-sakura-blush/60 mt-1 italic text-center">
          * {settings.payment_terms || "100% oldindan to'lov"} sharti bilan | +2% keshbek qaytadi ✨
        </p>
      </div>

      {/* Fallback In-Page Checkout Button */}
      <div className="mt-4">
        <button
          onClick={handleCheckout}
          disabled={isSubmitting}
          className="w-full py-4 px-4 rounded-3xl bg-gradient-to-r from-sakura-pink via-sakura-rose to-sakura-darkrose text-white font-black text-sm sm:text-base flex items-center justify-center gap-2 shadow-sakura hover:opacity-95 active:scale-95 transition-all"
        >
          <ShoppingBag className="w-5 h-5" />
          <span>{isSubmitting ? "Buyurtma yuborilmoqda..." : t.checkoutButton}</span>
        </button>
      </div>
    </div>
  );
};
