import React, { useState } from 'react';
import { Trash2, Plus, Minus, ArrowRight, CheckCircle2, ShoppingBag, ShieldCheck } from 'lucide-react';
import { CartSummary, Order } from '../types';
import { haptic } from '../utils/telegram';

interface BagPageProps {
  cart: CartSummary;
  onUpdateQty: (itemId: number, qty: number) => Promise<void>;
  onRemoveItem: (itemId: number) => Promise<void>;
  onClearCart: () => Promise<void>;
  onSubmitOrder: (orderData: {
    customer_name: string;
    phone: string;
    city: string;
    address: string;
  }) => Promise<Order>;
  onGoToCatalog: () => void;
  defaultUserName?: string;
}

const REGIONS = [
  'Toshkent shahri',
  'Toshkent viloyati',
  'Samarqand',
  'Farg\'ona',
  'Andijon',
  'Namangan',
  'Buxoro',
  'Qashqadaryo',
  'Surxondaryo',
  'Xorazm',
  'Navoiy',
  'Jizzax',
  'Sirdaryo',
  'Qoraqalpog\'iston',
];

export const BagPage: React.FC<BagPageProps> = ({
  cart,
  onUpdateQty,
  onRemoveItem,
  onSubmitOrder,
  onGoToCatalog,
  defaultUserName = '',
}) => {
  const [showCheckout, setShowCheckout] = useState(false);
  const [customerName, setCustomerName] = useState(defaultUserName);
  const [phone, setPhone] = useState('+998');
  const [city, setCity] = useState(REGIONS[0]);
  const [address, setAddress] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createdOrder, setCreatedOrder] = useState<Order | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  const handlePhoneChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let val = e.target.value;
    if (!val.startsWith('+998')) {
      val = '+998';
    }
    setPhone(val);
  };

  const handleConfirmOrder = async (e: React.FormEvent) => {
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
      setErrorMsg("Yetkazib berish manzilini kiriting (ko'cha, uy)");
      return;
    }

    setIsSubmitting(true);
    haptic.impact('heavy');

    try {
      const order = await onSubmitOrder({
        customer_name: customerName,
        phone,
        city,
        address,
      });
      haptic.notification('success');
      setCreatedOrder(order);
    } catch (err: any) {
      setErrorMsg(err.message || 'Buyurtma berishda xatolik yuz berdi');
      haptic.notification('error');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Order Success Screen
  if (createdOrder) {
    return (
      <div className="min-h-[80vh] flex flex-col items-center justify-center p-6 text-center max-w-md mx-auto space-y-4 animate-scaleIn">
        <div className="w-16 h-16 rounded-full bg-[#C7F464]/20 text-[#C7F464] flex items-center justify-center">
          <CheckCircle2 size={36} />
        </div>

        <h2 className="text-xl font-black text-[#F5F2E9] uppercase tracking-tight">
          Buyurtmangiz qabul qilindi!
        </h2>

        <p className="text-xs text-[#8E95A0] leading-relaxed">
          Buyurtma raqami: <strong className="text-[#C7F464]">#{createdOrder.id}</strong>.
          Admin tez orada buyurtmani tasdiqlash va to'lov rekvizitlari bo'yicha siz bilan bog'lanadi.
        </p>

        <div className="w-full bg-[#1A1D20] border border-[#26292E] rounded-2xl p-4 text-left text-xs space-y-2 mt-4">
          <div className="flex justify-between text-[#8E95A0]">
            <span>Mijoz:</span>
            <span className="text-[#F5F2E9] font-bold">{createdOrder.customer_name}</span>
          </div>
          <div className="flex justify-between text-[#8E95A0]">
            <span>Telefon:</span>
            <span className="text-[#F5F2E9] font-bold">{createdOrder.phone}</span>
          </div>
          <div className="flex justify-between text-[#8E95A0]">
            <span>Manzil:</span>
            <span className="text-[#F5F2E9] font-bold">{createdOrder.address}</span>
          </div>
          <div className="flex justify-between text-[#8E95A0] pt-2 border-t border-[#26292E]">
            <span>Jami summa:</span>
            <span className="text-[#C7F464] font-black">{createdOrder.formatted_total}</span>
          </div>
        </div>

        <button
          onClick={() => {
            setCreatedOrder(null);
            setShowCheckout(false);
            onGoToCatalog();
          }}
          className="w-full py-3.5 px-6 rounded-2xl bg-[#C7F464] text-[#111315] font-black text-xs uppercase tracking-wider mt-4 shadow-lg active:scale-95"
        >
          Do'konga qaytish
        </button>
      </div>
    );
  }

  // Empty Cart Screen
  if (!cart.items || cart.items.length === 0) {
    return (
      <div className="min-h-[75vh] flex flex-col items-center justify-center p-6 text-center max-w-sm mx-auto space-y-4 animate-fadeIn">
        <div className="w-20 h-20 rounded-full bg-[#1A1D20] border border-[#26292E] text-[#8E95A0] flex items-center justify-center text-3xl">
          <ShoppingBag size={32} />
        </div>
        <h2 className="text-base font-black text-[#F5F2E9] uppercase">
          Savatingiz hozircha bo'sh
        </h2>
        <p className="text-xs text-[#8E95A0] leading-relaxed">
          Katalogdan o'zingizga yoqqan zamonaviy kiyimlarni tanlang va buyurtma bering.
        </p>
        <button
          onClick={onGoToCatalog}
          className="px-6 py-3 rounded-2xl bg-[#C7F464] text-[#111315] font-black text-xs uppercase tracking-wider active:scale-95 transition-all shadow-md"
        >
          Katalogga o'tish
        </button>
      </div>
    );
  }

  return (
    <div className="pb-32 pt-2 px-4 max-w-lg mx-auto space-y-5 animate-fadeIn">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-base font-black uppercase tracking-wider text-[#F5F2E9]">
          Savat ({cart.total_items} ta kiyim)
        </h2>
      </div>

      {/* Cart Items List */}
      <div className="space-y-3">
        {cart.items.map((item) => (
          <div
            key={item.id}
            className="bg-[#1A1D20] border border-[#26292E] rounded-2xl p-3 flex gap-3 items-center"
          >
            {/* Photo */}
            <div className="w-20 h-24 rounded-xl bg-[#111315] overflow-hidden shrink-0 relative">
              {item.product_photo ? (
                <img
                  src={item.product_photo}
                  alt={item.product_title}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-xs text-[#8E95A0]">
                  ⚡
                </div>
              )}
            </div>

            {/* Details */}
            <div className="flex-1 min-w-0 flex flex-col justify-between h-full py-0.5">
              <div>
                <h4 className="text-xs font-bold text-[#F5F2E9] line-clamp-1">
                  {item.product_title}
                </h4>
                <div className="flex items-center gap-2 mt-1 text-[11px] text-[#8E95A0]">
                  {item.size && (
                    <span className="bg-[#111315] px-2 py-0.5 rounded border border-[#26292E] font-semibold text-[#F5F2E9]">
                      {item.size}
                    </span>
                  )}
                  {item.color && (
                    <span className="bg-[#111315] px-2 py-0.5 rounded border border-[#26292E] font-semibold text-[#F5F2E9]">
                      {item.color}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-between mt-3 pt-1 border-t border-[#26292E]/50">
                <span className="text-xs font-black text-[#C7F464]">
                  {item.formatted_item_total}
                </span>

                {/* Qty controls */}
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1.5 bg-[#111315] border border-[#26292E] rounded-lg px-1.5 py-0.5">
                    <button
                      onClick={() => {
                        haptic.selection();
                        if (item.qty <= 1) {
                          onRemoveItem(item.id);
                        } else {
                          onUpdateQty(item.id, item.qty - 1);
                        }
                      }}
                      className="w-5 h-5 flex items-center justify-center text-[#8E95A0] hover:text-[#F5F2E9]"
                    >
                      <Minus size={12} />
                    </button>
                    <span className="text-xs font-bold text-[#F5F2E9] min-w-[16px] text-center">
                      {item.qty}
                    </span>
                    <button
                      onClick={() => {
                        haptic.selection();
                        onUpdateQty(item.id, item.qty + 1);
                      }}
                      className="w-5 h-5 flex items-center justify-center text-[#8E95A0] hover:text-[#F5F2E9]"
                    >
                      <Plus size={12} />
                    </button>
                  </div>

                  <button
                    onClick={() => {
                      haptic.impact('light');
                      onRemoveItem(item.id);
                    }}
                    className="p-1 text-[#8E95A0] hover:text-red-400"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Checkout Form Modal / Slide */}
      {showCheckout ? (
        <form onSubmit={handleConfirmOrder} className="bg-[#1A1D20] border border-[#26292E] rounded-2xl p-4 space-y-4 animate-scaleIn">
          <div className="flex items-center justify-between pb-2 border-b border-[#26292E]">
            <h3 className="text-xs font-black uppercase tracking-wider text-[#F5F2E9]">
              Yetkazib berish ma'lumotlari
            </h3>
            <button
              type="button"
              onClick={() => setShowCheckout(false)}
              className="text-[11px] font-bold text-[#8E95A0] hover:text-[#F5F2E9]"
            >
              Orqaga
            </button>
          </div>

          {errorMsg && (
            <div className="p-2.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-bold">
              {errorMsg}
            </div>
          )}

          <div>
            <label className="text-[11px] font-bold text-[#8E95A0] uppercase block mb-1">
              Ism va Familiya
            </label>
            <input
              type="text"
              required
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              placeholder="Otabek Ismoiljonov"
              className="w-full px-3.5 py-2.5 rounded-xl bg-[#111315] border border-[#26292E] text-xs text-[#F5F2E9] focus:outline-none focus:border-[#C7F464]"
            />
          </div>

          <div>
            <label className="text-[11px] font-bold text-[#8E95A0] uppercase block mb-1">
              Telefon raqami
            </label>
            <input
              type="tel"
              required
              value={phone}
              onChange={handlePhoneChange}
              placeholder="+998901234567"
              className="w-full px-3.5 py-2.5 rounded-xl bg-[#111315] border border-[#26292E] text-xs text-[#F5F2E9] focus:outline-none focus:border-[#C7F464]"
            />
          </div>

          <div>
            <label className="text-[11px] font-bold text-[#8E95A0] uppercase block mb-1">
              Shahar / Viloyat
            </label>
            <select
              value={city}
              onChange={(e) => setCity(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-[#111315] border border-[#26292E] text-xs text-[#F5F2E9] focus:outline-none focus:border-[#C7F464]"
            >
              {REGIONS.map((r) => (
                <option key={r} value={r} className="bg-[#111315] text-[#F5F2E9]">
                  {r}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="text-[11px] font-bold text-[#8E95A0] uppercase block mb-1">
              Yetkazish manzili (ko'cha, uy raqami, mo'ljal)
            </label>
            <textarea
              required
              rows={2}
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="Chilonzor 9-mavze, 14-uy, 22-xonadon"
              className="w-full px-3.5 py-2 rounded-xl bg-[#111315] border border-[#26292E] text-xs text-[#F5F2E9] focus:outline-none focus:border-[#C7F464]"
            />
          </div>

          {/* Order Summary */}
          <div className="pt-2 border-t border-[#26292E] space-y-1.5 text-xs text-[#8E95A0]">
            <div className="flex justify-between">
              <span>Mahsulotlar:</span>
              <span className="text-[#F5F2E9] font-bold">{cart.total_items} ta</span>
            </div>
            <div className="flex justify-between text-sm pt-1 border-t border-[#26292E]">
              <span className="font-bold text-[#F5F2E9]">Jami to'lov:</span>
              <span className="font-black text-[#C7F464]">{cart.formatted_grand_total}</span>
            </div>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-3.5 px-6 rounded-2xl bg-[#C7F464] text-[#111315] font-black text-xs uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg disabled:opacity-50 active:scale-95 transition-all"
          >
            <ShieldCheck size={16} />
            {isSubmitting ? "Yuborilmoqda..." : "Buyurtmani tasdiqlash"}
          </button>
        </form>
      ) : (
        /* Order Summary Card & Checkout Trigger */
        <div className="bg-[#1A1D20] border border-[#26292E] rounded-2xl p-4 space-y-3">
          <div className="space-y-1.5 text-xs text-[#8E95A0]">
            <div className="flex justify-between">
              <span>Mahsulotlar soni:</span>
              <span className="text-[#F5F2E9] font-bold">{cart.total_items} ta</span>
            </div>
            <div className="flex justify-between text-sm pt-2 border-t border-[#26292E]">
              <span className="font-bold text-[#F5F2E9]">Jami summa:</span>
              <span className="font-black text-[#C7F464]">{cart.formatted_grand_total}</span>
            </div>
          </div>

          <button
            onClick={() => {
              haptic.impact('medium');
              setShowCheckout(true);
            }}
            className="w-full py-3.5 px-6 rounded-2xl bg-[#C7F464] text-[#111315] font-black text-xs uppercase tracking-wider flex items-center justify-center gap-2 shadow-lg active:scale-98 transition-all hover:bg-[#b5e350]"
          >
            Buyurtma berish
            <ArrowRight size={15} />
          </button>
        </div>
      )}
    </div>
  );
};
