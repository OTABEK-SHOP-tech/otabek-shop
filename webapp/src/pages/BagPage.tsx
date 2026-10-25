import React, { useState, useEffect } from 'react';
import {
  Trash2,
  Plus,
  Minus,
  ArrowRight,
  CheckCircle2,
  ShoppingBag,
  CreditCard,
  Copy,
  Check,
  UploadCloud,
  FileText,
  AlertCircle,
  Info,
  Clock,
  ArrowLeft,
} from 'lucide-react';
import { CartSummary, Order, ShopSettings } from '../types';
import { haptic } from '../utils/telegram';

interface BagPageProps {
  cart: CartSummary;
  onUpdateQty: (itemId: number, qty: number) => Promise<void>;
  onRemoveItem: (itemId: number) => Promise<void>;
  onClearCart?: () => Promise<void>;
  onSubmitOrder: (orderData: {
    customer_name: string;
    phone: string;
    city: string;
    address: string;
  }) => Promise<Order>;
  onGoToCatalog: () => void;
  onGoToProfile?: () => void;
  defaultUserName?: string;
  settings?: ShopSettings | null;
  activePaymentOrder?: Order | null;
  onClearActivePaymentOrder?: () => void;
}

const REGIONS = [
  'Toshkent shahri',
  'Toshkent viloyati',
  'Samarqand',
  "Farg'ona",
  'Andijon',
  'Namangan',
  'Buxoro',
  'Qashqadaryo',
  'Surxondaryo',
  'Xorazm',
  'Navoiy',
  'Jizzax',
  'Sirdaryo',
  "Qoraqalpog'iston",
];

export const BagPage: React.FC<BagPageProps> = ({
  cart,
  onUpdateQty,
  onRemoveItem,
  onClearCart,
  onSubmitOrder,
  onGoToCatalog,
  onGoToProfile,
  defaultUserName = '',
  settings,
  activePaymentOrder = null,
  onClearActivePaymentOrder,
}) => {
  // Saved user delivery details from localStorage
  const [customerName, setCustomerName] = useState(() => {
    try {
      const saved = localStorage.getItem('bek_saved_customer');
      if (saved) return JSON.parse(saved).name || defaultUserName;
    } catch {}
    return defaultUserName;
  });

  const [phone, setPhone] = useState(() => {
    try {
      const saved = localStorage.getItem('bek_saved_customer');
      if (saved) return JSON.parse(saved).phone || '+998';
    } catch {}
    return '+998';
  });

  const [city, setCity] = useState(() => {
    try {
      const saved = localStorage.getItem('bek_saved_customer');
      if (saved) return JSON.parse(saved).city || REGIONS[0];
    } catch {}
    return REGIONS[0];
  });

  const [address, setAddress] = useState(() => {
    try {
      const saved = localStorage.getItem('bek_saved_customer');
      if (saved) return JSON.parse(saved).address || '';
    } catch {}
    return '';
  });

  // Steps: 'cart' | 'checkout_form' | 'payment_card' | 'receipt_submitted'
  const [step, setStep] = useState<'cart' | 'checkout_form' | 'payment_card' | 'receipt_submitted'>('cart');
  const [currentOrder, setCurrentOrder] = useState<Order | null>(activePaymentOrder);
  const [isSubmittingOrder, setIsSubmittingOrder] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Payment card selection
  const card1 = settings?.payment_card_1 || '4916 9903 4816 9779';
  const card2 = settings?.payment_card_2 || '9860 2301 0748 6030';
  const [selectedCard, setSelectedCard] = useState<string>(card1);
  const [copiedCard, setCopiedCard] = useState<string | null>(null);

  // Receipt Upload
  const [receiptFile, setReceiptFile] = useState<File | null>(null);
  const [receiptPreview, setReceiptPreview] = useState<string | null>(null);
  const [isUploadingReceipt, setIsUploadingReceipt] = useState(false);
  const [receiptSuccess, setReceiptSuccess] = useState(false);
  const [summaryCopied, setSummaryCopied] = useState(false);

  useEffect(() => {
    if (activePaymentOrder) {
      setCurrentOrder(activePaymentOrder);
      setStep('payment_card');
    }
  }, [activePaymentOrder]);

  const handlePhoneChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let val = e.target.value;
    if (!val.startsWith('+998')) {
      val = '+998';
    }
    setPhone(val);
  };

  const handleCopyCard = (cardNum: string) => {
    navigator.clipboard.writeText(cardNum.replace(/\s+/g, ''));
    setCopiedCard(cardNum);
    haptic.notification('success');
    setTimeout(() => setCopiedCard(null), 2000);
  };

  const handleCopySummary = (text: string) => {
    navigator.clipboard.writeText(text);
    setSummaryCopied(true);
    haptic.notification('success');
    setTimeout(() => setSummaryCopied(false), 2000);
  };

  // Step 1 -> Step 2: Checkout Form
  const handleProceedToForm = () => {
    haptic.impact('light');
    setStep('checkout_form');
  };

  // Step 2 -> Step 3: Create order on server and open payment
  const handleCreateOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');

    if (!customerName.trim()) {
      setErrorMsg('Ismingizni kiriting');
      return;
    }

    if (phone.replace(/\D/g, '').length < 12) {
      setErrorMsg("Telefon raqamingizni to'liq kiriting (+998...)");
      return;
    }

    if (!address.trim()) {
      setErrorMsg("Yetkazib berish manzilini kiriting (tuman, ko'cha, uy)");
      return;
    }

    setIsSubmittingOrder(true);
    haptic.impact('heavy');

    try {
      // Save customer info in localStorage for future
      try {
        localStorage.setItem(
          'bek_saved_customer',
          JSON.stringify({ name: customerName, phone, city, address })
        );
      } catch {}

      const order = await onSubmitOrder({
        customer_name: customerName,
        phone,
        city,
        address,
      });

      setCurrentOrder(order);
      setStep('payment_card');
      haptic.notification('success');
    } catch (err: any) {
      setErrorMsg(err.message || 'Buyurtma yaratishda xatolik yuz berdi. Qayta urinib ko‘ring.');
      haptic.notification('error');
    } finally {
      setIsSubmittingOrder(false);
    }
  };

  // File selection for receipt
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setReceiptFile(file);
    if (file.type.startsWith('image/')) {
      const url = URL.createObjectURL(file);
      setReceiptPreview(url);
    } else {
      setReceiptPreview(null);
    }
    haptic.selection();
  };

  // Step 3 -> Step 4: Upload receipt
  const handleUploadReceipt = async () => {
    if (!currentOrder || !receiptFile || isUploadingReceipt) return;

    setIsUploadingReceipt(true);
    setErrorMsg('');
    haptic.impact('heavy');

    try {
      const formData = new FormData();
      formData.append('file', receiptFile);
      formData.append('selected_card', selectedCard);

      const resp = await fetch(`/api/orders/${currentOrder.id}/receipt`, {
        method: 'POST',
        headers: {
          'X-Telegram-Init-Data': (window as any).Telegram?.WebApp?.initData || '',
        },
        body: formData,
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || 'Chekni yuklashda xatolik yuz berdi');
      }

      const updatedOrder: Order = await resp.json();
      setCurrentOrder(updatedOrder);
      setReceiptSuccess(true);
      setStep('receipt_submitted');
      haptic.notification('success');
    } catch (err: any) {
      setErrorMsg(err.message || 'Chek yuklanmadi. Qayta urinib ko‘ring.');
      haptic.notification('error');
    } finally {
      setIsUploadingReceipt(false);
    }
  };

  // STEP 4: RECEIPT SUBMITTED / PAYMENT VERIFICATION CONFIRMATION
  if (step === 'receipt_submitted' && currentOrder) {
    const summaryText =
      `⚡ BEK STYLE — Buyurtma #${currentOrder.id}\n` +
      `Mijoz: ${currentOrder.customer_name}\n` +
      `Telefon: ${currentOrder.phone}\n` +
      `Manzil: ${currentOrder.city}, ${currentOrder.address}\n\n` +
      (currentOrder.items || [])
        .map(
          (it: any, i: number) =>
            `${i + 1}. ${it.title} ${it.size ? `(${it.size})` : ''} ${it.color ? `(${it.color})` : ''} — ${it.qty} dona (${it.price?.toLocaleString()} so'm)`
        )
        .join('\n') +
      `\n\nHozir to'lanadigan summa: ${currentOrder.formatted_total}\n` +
      `Tanlangan karta: ${currentOrder.selected_card || selectedCard}\n` +
      `Holat: To'lov tekshirilmoqda 🔍\n` +
      `Cargo: Tortilgandan keyin alohida hisoblanadi 📦`;

    return (
      <div className="min-h-[80vh] flex flex-col items-center justify-center p-4 text-center max-w-md mx-auto space-y-4 animate-fadeIn pb-32">
        <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center text-3xl shadow-xs">
          <Clock size={32} />
        </div>

        <div>
          <span className="text-[11px] font-extrabold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200/80">
            To'lov tekshirilmoqda
          </span>
          <h2 className="text-xl font-extrabold text-gray-900 mt-2">
            Chekingiz yuborildi!
          </h2>
          <p className="text-xs text-gray-500 mt-1 max-w-xs mx-auto">
            Buyurtma <strong className="text-gray-900">#{currentOrder.id}</strong> uchun to'lov cheki qabul qilindi.
            Admin tushumni tekshirgach, holat "To'landi"ga o'tadi.
          </p>
        </div>

        {/* Order Details Card */}
        <div className="w-full bg-white border border-gray-200/80 rounded-2xl p-4 text-left text-xs space-y-2.5 shadow-xs">
          <div className="flex items-center justify-between pb-2 border-b border-gray-100">
            <span className="font-extrabold text-gray-900">Buyurtma #{currentOrder.id}</span>
            <button
              onClick={() => handleCopySummary(summaryText)}
              className="flex items-center gap-1 text-[11px] font-bold text-emerald-600 hover:text-emerald-700"
            >
              {summaryCopied ? <Check size={13} /> : <Copy size={13} />}
              <span>{summaryCopied ? 'Nusxalandi' : 'Ma\'lumotlarni nusxalash'}</span>
            </button>
          </div>

          <div className="flex justify-between text-gray-500">
            <span>Mijoz:</span>
            <span className="text-gray-900 font-bold">{currentOrder.customer_name}</span>
          </div>
          <div className="flex justify-between text-gray-500">
            <span>Telefon:</span>
            <span className="text-gray-900 font-bold">{currentOrder.phone}</span>
          </div>
          <div className="flex justify-between text-gray-500">
            <span>Manzil:</span>
            <span className="text-gray-900 font-bold">{currentOrder.city}, {currentOrder.address}</span>
          </div>
          <div className="flex justify-between text-gray-500">
            <span>Tanlangan karta:</span>
            <span className="text-gray-900 font-mono font-bold text-[11px]">
              {currentOrder.selected_card || selectedCard}
            </span>
          </div>
          <div className="flex justify-between text-gray-900 pt-2 border-t border-gray-100 font-bold">
            <span>Hozir to'langan:</span>
            <span className="text-emerald-600 font-extrabold text-sm">{currentOrder.formatted_total}</span>
          </div>
          <div className="p-2 rounded-xl bg-amber-50 text-amber-800 text-[11px] font-medium flex items-center gap-1.5">
            <Info size={14} className="shrink-0 text-amber-600" />
            <span>Cargo haqi tovar yetib kelgach tortilib alohida hisoblanadi.</span>
          </div>
        </div>

        <div className="w-full space-y-2 pt-2">
          {onGoToProfile && (
            <button
              onClick={() => {
                if (onClearActivePaymentOrder) onClearActivePaymentOrder();
                onGoToProfile();
              }}
              className="w-full py-3.5 px-5 rounded-2xl bg-gray-900 text-white font-extrabold text-xs uppercase tracking-wider active:scale-95 transition-all shadow-md"
            >
              Buyurtmalarim bo'limiga o'tish
            </button>
          )}

          <button
            onClick={() => {
              if (onClearActivePaymentOrder) onClearActivePaymentOrder();
              setStep('cart');
              setCurrentOrder(null);
              onGoToCatalog();
            }}
            className="w-full py-3 px-5 rounded-2xl bg-white border border-gray-200/90 text-gray-700 font-bold text-xs active:scale-95 transition-all"
          >
            Do'konda xaridni davom ettirish
          </button>
        </div>
      </div>
    );
  }

  // STEP 3: PAYMENT SCREEN & RECEIPT UPLOAD
  if (step === 'payment_card' && currentOrder) {
    return (
      <div className="pb-32 pt-3 px-4 max-w-lg mx-auto space-y-4 animate-fadeIn">
        {/* Header */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setStep('cart')}
            className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-gray-700 active:scale-95"
          >
            <ArrowLeft size={16} />
          </button>
          <h2 className="text-base font-extrabold text-gray-900">
            To'lov va Chek yuklash
          </h2>
        </div>

        {/* Amount to pay banner */}
        <div className="bg-white rounded-2xl p-4 border border-gray-200/80 shadow-xs space-y-1 text-center">
          <span className="text-xs font-semibold text-gray-500 block">
            Hozir to'lanadigan summa:
          </span>
          <span className="text-2xl font-black text-emerald-600 block">
            {currentOrder.formatted_total}
          </span>
          <span className="text-[11px] text-gray-400 block font-medium">
            Buyurtma #{currentOrder.id}
          </span>
        </div>

        {/* Cargo Warning */}
        <div className="p-3 bg-amber-50 border border-amber-200/80 rounded-xl text-xs text-amber-900 flex items-start gap-2">
          <Info size={16} className="text-amber-600 shrink-0 mt-0.5" />
          <p className="text-[11px] leading-relaxed">
            <strong>Muhim:</strong> Cargo haqi tortilgandan keyin alohida hisoblanadi. Hozir faqat kiyimlar summasini to'lang.
          </p>
        </div>

        {/* Two Payment Cards */}
        <div className="space-y-2.5">
          <label className="text-xs font-extrabold uppercase tracking-wider text-gray-700 block">
            To'lov kartasini tanlang:
          </label>

          {/* Card 1 */}
          <div
            onClick={() => setSelectedCard(card1)}
            className={`p-3.5 rounded-2xl border transition-all cursor-pointer relative ${
              selectedCard === card1
                ? 'bg-emerald-50/60 border-emerald-600 ring-2 ring-emerald-500/20'
                : 'bg-white border-gray-200/90 hover:bg-gray-50'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className={`w-8 h-8 rounded-xl flex items-center justify-center font-bold text-xs ${
                  selectedCard === card1 ? 'bg-emerald-600 text-white' : 'bg-gray-100 text-gray-700'
                }`}>
                  1
                </div>
                <div>
                  <span className="text-[11px] font-bold text-gray-500 uppercase block">1-karta</span>
                  <span className="text-sm font-mono font-extrabold text-gray-900 tracking-wider">
                    {card1}
                  </span>
                </div>
              </div>

              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleCopyCard(card1);
                }}
                className="px-2.5 py-1.5 rounded-xl bg-white border border-gray-200 text-xs font-bold text-gray-700 hover:text-emerald-600 flex items-center gap-1 shadow-xs active:scale-95"
              >
                {copiedCard === card1 ? (
                  <>
                    <Check size={13} className="text-emerald-600" />
                    <span className="text-emerald-600 text-[11px]">Nusxalandi</span>
                  </>
                ) : (
                  <>
                    <Copy size={13} />
                    <span className="text-[11px]">Nusxalash</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Card 2 */}
          <div
            onClick={() => setSelectedCard(card2)}
            className={`p-3.5 rounded-2xl border transition-all cursor-pointer relative ${
              selectedCard === card2
                ? 'bg-emerald-50/60 border-emerald-600 ring-2 ring-emerald-500/20'
                : 'bg-white border-gray-200/90 hover:bg-gray-50'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className={`w-8 h-8 rounded-xl flex items-center justify-center font-bold text-xs ${
                  selectedCard === card2 ? 'bg-emerald-600 text-white' : 'bg-gray-100 text-gray-700'
                }`}>
                  2
                </div>
                <div>
                  <span className="text-[11px] font-bold text-gray-500 uppercase block">2-karta</span>
                  <span className="text-sm font-mono font-extrabold text-gray-900 tracking-wider">
                    {card2}
                  </span>
                </div>
              </div>

              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleCopyCard(card2);
                }}
                className="px-2.5 py-1.5 rounded-xl bg-white border border-gray-200 text-xs font-bold text-gray-700 hover:text-emerald-600 flex items-center gap-1 shadow-xs active:scale-95"
              >
                {copiedCard === card2 ? (
                  <>
                    <Check size={13} className="text-emerald-600" />
                    <span className="text-emerald-600 text-[11px]">Nusxalandi</span>
                  </>
                ) : (
                  <>
                    <Copy size={13} />
                    <span className="text-[11px]">Nusxalash</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Upload Receipt Section */}
        <div className="bg-white rounded-2xl p-4 border border-gray-200/80 shadow-xs space-y-3">
          <label className="text-xs font-extrabold uppercase tracking-wider text-gray-700 block">
            To'lov chekini yuklang (Rasm yoki PDF):
          </label>

          <label className="border-2 border-dashed border-gray-200 hover:border-emerald-500 rounded-2xl p-4 flex flex-col items-center justify-center cursor-pointer transition-colors bg-gray-50 hover:bg-emerald-50/30">
            <input
              type="file"
              accept="image/*,application/pdf"
              onChange={handleFileChange}
              className="hidden"
            />
            {receiptFile ? (
              <div className="flex flex-col items-center text-center space-y-2">
                {receiptPreview ? (
                  <img
                    src={receiptPreview}
                    alt="Chek rasmi"
                    className="w-20 h-24 object-cover rounded-xl border border-gray-200 shadow-xs"
                  />
                ) : (
                  <div className="w-12 h-12 rounded-xl bg-emerald-100 text-emerald-600 flex items-center justify-center">
                    <FileText size={24} />
                  </div>
                )}
                <div>
                  <span className="text-xs font-bold text-gray-900 block truncate max-w-[200px]">
                    {receiptFile.name}
                  </span>
                  <span className="text-[10px] text-gray-400">
                    {(receiptFile.size / 1024).toFixed(1)} KB • Boshqa fayl tanlash uchun bosing
                  </span>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center text-center space-y-1.5 py-2">
                <UploadCloud size={28} className="text-gray-400" />
                <span className="text-xs font-bold text-gray-700">
                  Chek rasmi yoki PDF faylni tanlang
                </span>
                <span className="text-[10px] text-gray-400">
                  Click / Payme / Uzum ilovalaridagi to'lov cheki
                </span>
              </div>
            )}
          </label>

          {errorMsg && (
            <div className="p-3 rounded-xl bg-rose-50 text-rose-700 text-xs font-medium flex items-center gap-2">
              <AlertCircle size={15} className="shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <button
            onClick={handleUploadReceipt}
            disabled={!receiptFile || isUploadingReceipt}
            className="w-full py-3.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs uppercase tracking-wider active:scale-95 transition-all disabled:bg-gray-300 disabled:cursor-not-allowed shadow-md"
          >
            {isUploadingReceipt ? 'Chek yuborilmoqda...' : 'Chekni tasdiqlash uchun yuborish'}
          </button>
        </div>
      </div>
    );
  }

  // STEP 2: CHECKOUT FORM (DELIVERY DETAILS)
  if (step === 'checkout_form') {
    return (
      <div className="pb-32 pt-3 px-4 max-w-lg mx-auto space-y-4 animate-fadeIn">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setStep('cart')}
            className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center text-gray-700 active:scale-95"
          >
            <ArrowLeft size={16} />
          </button>
          <h2 className="text-base font-extrabold text-gray-900">
            Yetkazib berish ma'lumotlari
          </h2>
        </div>

        <form onSubmit={handleCreateOrder} className="space-y-4">
          <div className="bg-white rounded-2xl p-4 border border-gray-200/80 shadow-xs space-y-3.5">
            {/* Full Name */}
            <div>
              <label className="text-[11px] font-bold text-gray-500 uppercase block mb-1">
                Ism va familiya *
              </label>
              <input
                type="text"
                required
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                placeholder="Masalan: Otabek Xoliqov"
                className="w-full px-3.5 py-2.5 rounded-xl bg-gray-50 border border-gray-200 text-xs text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-emerald-500 focus:bg-white transition-all"
              />
            </div>

            {/* Phone Number */}
            <div>
              <label className="text-[11px] font-bold text-gray-500 uppercase block mb-1">
                Telefon raqam *
              </label>
              <input
                type="tel"
                required
                value={phone}
                onChange={handlePhoneChange}
                placeholder="+998 90 123 45 67"
                className="w-full px-3.5 py-2.5 rounded-xl bg-gray-50 border border-gray-200 text-xs text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-emerald-500 focus:bg-white transition-all font-mono"
              />
            </div>

            {/* Region / City */}
            <div>
              <label className="text-[11px] font-bold text-gray-500 uppercase block mb-1">
                Viloyat / Shahar *
              </label>
              <select
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-gray-50 border border-gray-200 text-xs text-gray-900 focus:outline-none focus:border-emerald-500 focus:bg-white transition-all"
              >
                {REGIONS.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>

            {/* Street / Address */}
            <div>
              <label className="text-[11px] font-bold text-gray-500 uppercase block mb-1">
                Aniq manzil (tuman, ko'cha, uy/kvartira) *
              </label>
              <textarea
                required
                rows={2}
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="Chilonzor tumani, 9-kvartal, 14-uy, 22-xonadon"
                className="w-full px-3.5 py-2.5 rounded-xl bg-gray-50 border border-gray-200 text-xs text-gray-900 placeholder:text-gray-400 focus:outline-none focus:border-emerald-500 focus:bg-white transition-all resize-none"
              />
            </div>
          </div>

          {/* Cargo reminder */}
          <div className="p-3 bg-amber-50 border border-amber-200/80 rounded-xl text-xs text-amber-900 flex items-start gap-2">
            <Info size={16} className="text-amber-600 shrink-0 mt-0.5" />
            <span className="text-[11px] leading-relaxed">
              Cargo haqi tortilgandan keyin alohida hisoblanadi. Keyingi bosqichda kartaga to'lov qilasiz.
            </span>
          </div>

          {errorMsg && (
            <div className="p-3 rounded-xl bg-rose-50 text-rose-700 text-xs font-medium flex items-center gap-2">
              <AlertCircle size={15} className="shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          <div className="bg-white rounded-2xl p-4 border border-gray-200/80 shadow-xs flex items-center justify-between">
            <div>
              <span className="text-[11px] text-gray-500 block">Hozir to'lanadigan:</span>
              <span className="text-base font-extrabold text-gray-900">{cart.formatted_subtotal}</span>
            </div>
            <button
              type="submit"
              disabled={isSubmittingOrder}
              className="py-3 px-5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs uppercase tracking-wider flex items-center gap-2 active:scale-95 transition-all shadow-md disabled:bg-gray-300"
            >
              <span>{isSubmittingOrder ? 'Yaratilmoqda...' : 'To\'lovga o\'tish'}</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </form>
      </div>
    );
  }

  // STEP 1: CART EMPTY STATE
  if (!cart.items || cart.items.length === 0) {
    return (
      <div className="min-h-[75vh] flex flex-col items-center justify-center p-6 text-center max-w-sm mx-auto space-y-4 animate-fadeIn pb-32">
        <div className="w-16 h-16 rounded-full bg-gray-100 text-gray-400 flex items-center justify-center text-3xl shadow-xs">
          <ShoppingBag size={28} />
        </div>
        <h2 className="text-base font-extrabold text-gray-900">
          Savatingiz hozircha bo'sh
        </h2>
        <p className="text-xs text-gray-500 leading-relaxed max-w-xs">
          Katalogdan yigitlar uchun zamonaviy streetwear kiyimlarini tanlang va savatga qo'shing.
        </p>
        <button
          onClick={onGoToCatalog}
          className="px-6 py-3 rounded-2xl bg-gray-900 text-white font-bold text-xs uppercase tracking-wider active:scale-95 transition-all shadow-md"
        >
          Katalogga o'tish
        </button>
      </div>
    );
  }

  // STEP 1: CART REVIEW
  return (
    <div className="pb-36 pt-3 px-4 max-w-lg mx-auto space-y-4 animate-fadeIn">
      {/* Title & Clear Cart */}
      <div className="flex items-center justify-between px-0.5">
        <h2 className="text-base font-extrabold text-gray-900 flex items-center gap-2">
          <span>Savat</span>
          <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200/60">
            {cart.total_items} ta kiyim
          </span>
        </h2>
        {onClearCart && (
          <button
            onClick={() => {
              haptic.impact('light');
              onClearCart();
            }}
            className="text-xs font-semibold text-gray-400 hover:text-rose-500 flex items-center gap-1 transition-colors"
          >
            <Trash2 size={13} />
            <span>Tozalash</span>
          </button>
        )}
      </div>

      {/* Cart Items List */}
      <div className="space-y-3">
        {cart.items.map((item) => (
          <div
            key={item.id}
            className="bg-white border border-gray-200/80 rounded-2xl p-3 flex gap-3 items-center shadow-xs"
          >
            {/* Thumbnail */}
            <div className="w-16 h-20 rounded-xl bg-gray-100 overflow-hidden shrink-0 relative">
              {item.product_photo ? (
                <img
                  src={item.product_photo}
                  alt={item.product_title}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-xs text-gray-400">
                  ⚡
                </div>
              )}
            </div>

            {/* Item Info */}
            <div className="flex-1 min-w-0 space-y-1">
              <h4 className="text-xs sm:text-sm font-bold text-gray-900 line-clamp-1">
                {item.product_title}
              </h4>
              <div className="flex items-center gap-1.5 flex-wrap text-[11px] text-gray-500">
                {item.color && (
                  <span className="bg-gray-100 px-1.5 py-0.5 rounded-md font-medium">
                    Rang: {item.color}
                  </span>
                )}
                {item.size && (
                  <span className="bg-gray-100 px-1.5 py-0.5 rounded-md font-medium">
                    O'lcham: {item.size}
                  </span>
                )}
              </div>
              <span className="text-xs font-extrabold text-gray-900 block">
                {item.formatted_item_total}
              </span>
            </div>

            {/* Qty Controls */}
            <div className="flex items-center gap-2 bg-gray-50 border border-gray-200/80 rounded-xl p-1 shrink-0">
              <button
                onClick={() => {
                  haptic.selection();
                  if (item.qty > 1) {
                    onUpdateQty(item.id, item.qty - 1);
                  } else {
                    onRemoveItem(item.id);
                  }
                }}
                className="w-6 h-6 rounded-lg bg-white text-gray-700 flex items-center justify-center font-bold shadow-xs active:scale-95"
              >
                <Minus size={12} />
              </button>
              <span className="text-xs font-bold text-gray-900 w-4 text-center">
                {item.qty}
              </span>
              <button
                onClick={() => {
                  haptic.selection();
                  onUpdateQty(item.id, item.qty + 1);
                }}
                className="w-6 h-6 rounded-lg bg-white text-gray-700 flex items-center justify-center font-bold shadow-xs active:scale-95"
              >
                <Plus size={12} />
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Cargo Info Note (Required: Cargo haqi tortilgandan keyin alohida hisoblanadi) */}
      <div className="bg-amber-50 border border-amber-200/80 rounded-2xl p-3.5 flex items-start gap-2.5">
        <Info size={16} className="text-amber-600 shrink-0 mt-0.5" />
        <div className="text-xs text-amber-900 space-y-0.5">
          <p className="font-bold">Yetkazish va Cargo haqida:</p>
          <p className="text-amber-800/90 leading-relaxed text-[11px]">
            Cargo haqi tortilgandan keyin alohida hisoblanadi. Tovarlar Toshkentga yetib kelgach,
            aniq vazn bo'yicha to'lov qilinadi.
          </p>
        </div>
      </div>

      {/* Order Summary & Proceed Button */}
      <div className="bg-white rounded-2xl p-4 border border-gray-200/80 shadow-xs space-y-3">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>Mahsulotlar soni:</span>
          <span className="font-bold text-gray-900">{cart.total_items} ta</span>
        </div>
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>Cargo to'lovi:</span>
          <span className="font-medium text-amber-700 italic">Tortilgach alohida</span>
        </div>
        <div className="flex items-center justify-between text-sm font-extrabold text-gray-900 pt-2 border-t border-gray-100">
          <span>Hozir to'lanadigan summa:</span>
          <span className="text-base text-emerald-600 font-black">{cart.formatted_subtotal}</span>
        </div>

        <button
          onClick={handleProceedToForm}
          className="w-full py-3.5 px-4 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs uppercase tracking-wider flex items-center justify-center gap-2 active:scale-95 transition-all shadow-md"
        >
          <span>Buyurtma berish</span>
          <ArrowRight size={15} />
        </button>
      </div>
    </div>
  );
};
