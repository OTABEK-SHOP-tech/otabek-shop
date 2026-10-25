import React, { useState } from 'react';
import {
  User,
  Clock,
  MessageCircle,
  ExternalLink,
  ShoppingBag,
  MapPin,
  CreditCard,
  AlertCircle,
  UploadCloud,
  CheckCircle2,
  ShieldCheck,
} from 'lucide-react';
import { Order, ShopSettings, UserProfile } from '../types';
import { haptic, openTelegramLink } from '../utils/telegram';

interface ProfilePageProps {
  user: UserProfile | null;
  orders: Order[];
  settings: ShopSettings | null;
  onRefreshOrders?: () => void;
  onGoToCatalog: () => void;
  onPayForOrder?: (order: Order) => void;
}

export const ProfilePage: React.FC<ProfilePageProps> = ({
  user,
  orders,
  settings,
  onGoToCatalog,
  onPayForOrder,
}) => {
  const contactUser = settings?.contact_username || 'bekstyle_admin';

  // Saved address from localStorage or user profile
  const savedCustomer = (() => {
    try {
      const s = localStorage.getItem('bek_saved_customer');
      if (s) return JSON.parse(s);
    } catch {}
    return {
      name: user?.name || '',
      phone: user?.phone || '',
      city: user?.saved_city || '',
      address: user?.saved_address || '',
    };
  })();

  const getStatusBadge = (status: string, label: string) => {
    switch (status) {
      case 'pending_payment':
        return (
          <span className="bg-amber-50 text-amber-700 border border-amber-200 text-[10px] font-bold px-2 py-0.5 rounded-full">
            ⏳ To'lov kutilmoqda
          </span>
        );
      case 'payment_review':
        return (
          <span className="bg-blue-50 text-blue-700 border border-blue-200 text-[10px] font-bold px-2 py-0.5 rounded-full">
            🔍 To'lov tekshirilmoqda
          </span>
        );
      case 'paid':
        return (
          <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-bold px-2 py-0.5 rounded-full">
            💳 To'landi
          </span>
        );
      case 'payment_rejected':
        return (
          <span className="bg-rose-50 text-rose-700 border border-rose-200 text-[10px] font-bold px-2 py-0.5 rounded-full">
            ❌ To'lov rad etildi
          </span>
        );
      case 'ordered':
        return (
          <span className="bg-indigo-50 text-indigo-700 border border-indigo-200 text-[10px] font-bold px-2 py-0.5 rounded-full">
            🛒 Pinduoduoga berildi
          </span>
        );
      case 'shipping':
        return (
          <span className="bg-purple-50 text-purple-700 border border-purple-200 text-[10px] font-bold px-2 py-0.5 rounded-full">
            🚚 Yo'lda
          </span>
        );
      case 'arrived':
        return (
          <span className="bg-teal-50 text-teal-700 border border-teal-200 text-[10px] font-bold px-2 py-0.5 rounded-full">
            📍 Yetib keldi
          </span>
        );
      case 'done':
        return (
          <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-bold px-2 py-0.5 rounded-full">
            🏁 Topshirildi
          </span>
        );
      case 'cancelled':
        return (
          <span className="bg-gray-100 text-gray-600 border border-gray-200 text-[10px] font-bold px-2 py-0.5 rounded-full">
            ❌ Bekor qilindi
          </span>
        );
      default:
        return (
          <span className="bg-gray-100 text-gray-700 border border-gray-200 text-[10px] font-bold px-2 py-0.5 rounded-full">
            {label || status}
          </span>
        );
    }
  };

  return (
    <div className="pb-32 pt-3 px-4 max-w-lg mx-auto space-y-4 animate-fadeIn">
      {/* User Profile Header Card */}
      <div className="bg-white border border-gray-200/80 rounded-2xl p-4 flex items-center gap-3.5 shadow-xs">
        <div className="w-13 h-13 rounded-2xl bg-gray-900 text-white font-black text-xl flex items-center justify-center shrink-0 shadow-xs">
          {user?.name ? user.name[0].toUpperCase() : 'B'}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-extrabold text-gray-900 truncate">
              {user?.name || 'Mijoz'}
            </h2>
            {user?.is_admin && (
              <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 text-[10px] font-bold px-2 py-0.2 rounded-full">
                Admin
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 truncate mt-0.5">
            {user?.username ? `@${user.username}` : `Telegram ID: ${user?.telegram_id || ''}`}
          </p>
        </div>
      </div>

      {/* Saved Delivery Info Card */}
      {savedCustomer.address && (
        <div className="bg-white border border-gray-200/80 rounded-2xl p-4 shadow-xs space-y-2">
          <div className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-gray-700">
            <MapPin size={15} className="text-emerald-600" />
            <span>Saqlangan yetkazish manzili</span>
          </div>
          <div className="text-xs text-gray-600 space-y-1 bg-gray-50 p-3 rounded-xl border border-gray-100">
            <p className="font-bold text-gray-900">{savedCustomer.name} ({savedCustomer.phone})</p>
            <p>{savedCustomer.city}, {savedCustomer.address}</p>
          </div>
        </div>
      )}

      {/* Orders History Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between px-0.5">
          <div className="flex items-center gap-2">
            <Clock size={16} className="text-emerald-600" />
            <h3 className="text-xs font-extrabold uppercase tracking-wider text-gray-900">
              Buyurtmalar tarixi
            </h3>
          </div>
          <span className="text-xs text-gray-500 font-semibold">{orders.length} ta buyurtma</span>
        </div>

        {orders.length > 0 ? (
          <div className="space-y-3">
            {orders.map((ord) => (
              <div
                key={ord.id}
                className="bg-white border border-gray-200/80 rounded-2xl p-4 space-y-3 shadow-xs"
              >
                {/* Header row */}
                <div className="flex items-center justify-between">
                  <span className="text-xs font-extrabold text-gray-900">
                    Buyurtma #{ord.id}
                  </span>
                  {getStatusBadge(ord.status, ord.status_label)}
                </div>

                {/* Items snapshot */}
                <div className="text-xs text-gray-600 space-y-1.5 bg-gray-50 p-3 rounded-xl border border-gray-100">
                  <p className="text-[11px] text-gray-400">
                    {new Date(ord.created_at).toLocaleDateString('uz-UZ', {
                      day: '2-digit',
                      month: 'long',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </p>
                  <div className="space-y-1">
                    {ord.items && ord.items.length > 0
                      ? ord.items.map((it: any, idx: number) => (
                          <div key={idx} className="flex justify-between items-center text-xs">
                            <span className="font-semibold text-gray-900 line-clamp-1">
                              {it.title} {it.size ? `(${it.size})` : ''} {it.color ? `(${it.color})` : ''}
                            </span>
                            <span className="text-gray-500 shrink-0 ml-2">
                              {it.qty} × {it.price?.toLocaleString()} so'm
                            </span>
                          </div>
                        ))
                      : 'Kiyim buyurtmasi'}
                  </div>
                </div>

                {/* Rejection notice if payment was rejected */}
                {ord.status === 'payment_rejected' && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 space-y-1">
                    <p className="font-bold flex items-center gap-1.5">
                      <AlertCircle size={14} />
                      To'lov cheki tasdiqlanmadi:
                    </p>
                    <p className="text-[11px] text-rose-700">
                      {ord.reject_reason || 'To\'lov hisobga tushmadi yoki chek noto\'g\'ri.'}
                    </p>
                  </div>
                )}

                {/* Payment & Cargo Info */}
                <div className="pt-2 border-t border-gray-100 text-xs space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-500">Hozir to'lanadigan summa:</span>
                    <span className="font-extrabold text-gray-900 text-sm">
                      {ord.formatted_total}
                    </span>
                  </div>

                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-gray-500">Cargo to'lovi:</span>
                    <span className="text-amber-800 font-medium">
                      {ord.cargo_price
                        ? `${ord.cargo_price.toLocaleString()} so'm (${ord.cargo_status || 'to\'lov kutilmoqda'})`
                        : 'Tortilgandan keyin alohida hisoblanadi'}
                    </span>
                  </div>

                  {ord.receipt_url && (
                    <div className="text-[11px] text-emerald-700 font-medium flex items-center gap-1 pt-1">
                      <CheckCircle2 size={13} className="text-emerald-600" />
                      <span>To'lov cheki biriktirilgan</span>
                    </div>
                  )}
                </div>

                {/* Action button if payment pending or rejected */}
                {(ord.status === 'pending_payment' || ord.status === 'payment_rejected') && onPayForOrder && (
                  <button
                    onClick={() => {
                      haptic.impact('medium');
                      onPayForOrder(ord);
                    }}
                    className="w-full py-2.5 px-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs uppercase tracking-wider flex items-center justify-center gap-1.5 active:scale-95 transition-all shadow-xs"
                  >
                    <UploadCloud size={14} />
                    <span>
                      {ord.status === 'payment_rejected' ? 'Yangi chek yuklash' : 'To\'lov qilish va chek yuklash'}
                    </span>
                  </button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 bg-white border border-gray-200/80 rounded-2xl p-5 space-y-2 shadow-xs">
            <ShoppingBag size={24} className="mx-auto text-gray-400" />
            <p className="text-xs text-gray-500">Sizda hali buyurtmalar yo'q</p>
            <button
              onClick={onGoToCatalog}
              className="text-xs font-bold text-emerald-600 hover:underline"
            >
              Katalogdan xarid qilish &rarr;
            </button>
          </div>
        )}
      </div>

      {/* Support & Contact Card */}
      <div className="bg-white border border-gray-200/80 rounded-2xl p-4 space-y-2 shadow-xs">
        <h4 className="text-xs font-extrabold uppercase tracking-wider text-gray-900 flex items-center gap-1.5">
          <MessageCircle size={15} className="text-emerald-600" />
          <span>Do'kon bilan bog'lanish</span>
        </h4>
        <p className="text-xs text-gray-500 leading-relaxed">
          Savollaringiz yoki o'lcham tanlash bo'yicha yordam kerak bo'lsa, adminga yozishingiz mumkin.
        </p>
        <button
          onClick={() => openTelegramLink(`https://t.me/${contactUser}`)}
          className="w-full mt-2 py-2.5 px-4 rounded-xl bg-gray-50 border border-gray-200 text-xs font-bold text-gray-900 flex items-center justify-center gap-2 hover:bg-gray-100 active:scale-95 transition-all"
        >
          <span>Admin bilan yozishish (@{contactUser})</span>
          <ExternalLink size={13} className="text-gray-400" />
        </button>
      </div>

      {/* Admin Panel Link (Cleanly separated, only visible for Admin) */}
      {user?.is_admin && (
        <div className="bg-gray-900 text-white rounded-2xl p-4 shadow-sm space-y-2">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-emerald-400">
            <ShieldCheck size={16} />
            <span>Admin boshqaruvi</span>
          </div>
          <p className="text-xs text-gray-300">
            Mahsulotlar qo'shish, tushgan cheklarni tasdiqlash va bot sozlamalari Telegram bot orqali amalga oshiriladi.
          </p>
          <button
            onClick={() => openTelegramLink(`https://t.me/bek_styleee_bot?start=admin`)}
            className="w-full py-2.5 px-4 rounded-xl bg-emerald-500 text-gray-950 font-extrabold text-xs uppercase tracking-wider flex items-center justify-center gap-2 active:scale-95 transition-all"
          >
            <span>Botda Admin panelni ochish</span>
            <ExternalLink size={13} />
          </button>
        </div>
      )}
    </div>
  );
};
