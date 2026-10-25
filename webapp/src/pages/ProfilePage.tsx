import React, { useState } from 'react';
import { User, Wallet, Clock, MessageCircle, ExternalLink, AlertCircle, ShoppingBag, X } from 'lucide-react';
import { Order, ShopSettings, UserProfile } from '../types';
import { haptic, openTelegramLink } from '../utils/telegram';

interface ProfilePageProps {
  user: UserProfile | null;
  orders: Order[];
  settings: ShopSettings | null;
  onRefreshOrders: () => void;
  onGoToCatalog: () => void;
}

export const ProfilePage: React.FC<ProfilePageProps> = ({
  user,
  orders,
  settings,
  onGoToCatalog,
}) => {
  const [showTopUpModal, setShowTopUpModal] = useState(false);

  const contactUser = settings?.contact_username || 'bekstyle_admin';

  const getStatusBadge = (status: string, label: string) => {
    switch (status) {
      case 'paid':
        return (
          <span className="bg-blue-500/10 border border-blue-500/30 text-blue-400 text-[10px] font-bold px-2 py-0.5 rounded-full">
            {label || "To'landi"}
          </span>
        );
      case 'in_transit':
        return (
          <span className="bg-purple-500/10 border border-purple-500/30 text-purple-400 text-[10px] font-bold px-2 py-0.5 rounded-full">
            {label || "Yo'lda"}
          </span>
        );
      case 'delivered':
        return (
          <span className="bg-[#C7F464]/10 border border-[#C7F464]/30 text-[#C7F464] text-[10px] font-bold px-2 py-0.5 rounded-full">
            {label || 'Yetkazildi'}
          </span>
        );
      case 'cancelled':
        return (
          <span className="bg-red-500/10 border border-red-500/30 text-red-400 text-[10px] font-bold px-2 py-0.5 rounded-full">
            {label || 'Bekor qilindi'}
          </span>
        );
      default:
        return (
          <span className="bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 text-[10px] font-bold px-2 py-0.5 rounded-full">
            {label || 'Kutilmoqda'}
          </span>
        );
    }
  };

  return (
    <div className="pb-28 pt-2 px-4 max-w-lg mx-auto space-y-5 animate-fadeIn">
      {/* User Header Card */}
      <div className="bg-[#1A1D20] border border-[#26292E] rounded-2xl p-4 flex items-center gap-3.5">
        <div className="w-14 h-14 rounded-2xl bg-[#C7F464] text-[#111315] font-black text-xl flex items-center justify-center shrink-0">
          {user?.name ? user.name[0].toUpperCase() : 'B'}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-black text-[#F5F2E9] truncate">
              {user?.name || 'Mijoz'}
            </h2>
            {user?.is_admin && (
              <span className="bg-[#C7F464]/20 text-[#C7F464] text-[9px] font-black uppercase px-2 py-0.5 rounded">
                Admin
              </span>
            )}
          </div>
          <p className="text-xs text-[#8E95A0] truncate">
            {user?.username ? `@${user.username}` : `ID: ${user?.telegram_id || ''}`}
          </p>
        </div>
      </div>

      {/* Balance & Wallet Card */}
      <div className="bg-gradient-to-br from-[#1A1D20] to-[#14171A] border border-[#26292E] rounded-2xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-bold text-[#8E95A0] uppercase tracking-wider">
            <Wallet size={15} className="text-[#C7F464]" />
            Shaxsiy balans
          </div>
          <span className="text-[10px] text-[#8E95A0]">Hamyon</span>
        </div>

        <div className="text-2xl font-black text-[#F5F2E9]">
          {user?.formatted_balance || "0 so'm"}
        </div>

        <button
          onClick={() => {
            haptic.impact('medium');
            setShowTopUpModal(true);
          }}
          className="w-full py-2.5 px-4 rounded-xl bg-[#C7F464] text-[#111315] font-black text-xs uppercase tracking-wider active:scale-98 transition-all hover:bg-[#b5e350] shadow"
        >
          Hisobni to'ldirish
        </button>
      </div>

      {/* Orders History Section */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock size={16} className="text-[#C7F464]" />
            <h3 className="text-sm font-black uppercase tracking-wider text-[#F5F2E9]">
              Buyurtmalar tarixi
            </h3>
          </div>
          <span className="text-xs text-[#8E95A0]">{orders.length} ta buyurtma</span>
        </div>

        {orders.length > 0 ? (
          <div className="space-y-2.5">
            {orders.map((ord) => (
              <div
                key={ord.id}
                className="bg-[#1A1D20] border border-[#26292E] rounded-2xl p-3.5 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-black text-[#F5F2E9]">
                    Buyurtma #{ord.id}
                  </span>
                  {getStatusBadge(ord.status, ord.status_label)}
                </div>

                <div className="text-xs text-[#8E95A0] space-y-1">
                  <p>
                    {new Date(ord.created_at).toLocaleDateString('uz-UZ', {
                      day: '2-digit',
                      month: 'long',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </p>
                  <p className="text-[#F5F2E9] font-medium">
                    {ord.items && ord.items.length > 0
                      ? ord.items.map((i) => `${i.title} (${i.qty}x)`).join(', ')
                      : 'Kiyim buyurtmasi'}
                  </p>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-[#26292E]/60 text-xs">
                  <span className="text-[#8E95A0]">Jami to'lov:</span>
                  <span className="font-black text-[#C7F464]">{ord.formatted_total}</span>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 bg-[#1A1D20] border border-[#26292E] rounded-2xl p-5 space-y-2">
            <ShoppingBag size={24} className="mx-auto text-[#8E95A0]" />
            <p className="text-xs text-[#8E95A0]">Sizda hali buyurtmalar yo'q</p>
            <button
              onClick={onGoToCatalog}
              className="text-xs font-bold text-[#C7F464] hover:underline"
            >
              Katalogdan xarid qilish &rarr;
            </button>
          </div>
        )}
      </div>

      {/* Support & Contact Card */}
      <div className="bg-[#1A1D20] border border-[#26292E] rounded-2xl p-4 space-y-2">
        <h4 className="text-xs font-black uppercase tracking-wider text-[#F5F2E9] flex items-center gap-1.5">
          <MessageCircle size={15} className="text-[#C7F464]" />
          Do'kon bilan bog'lanish
        </h4>
        <p className="text-xs text-[#8E95A0] leading-relaxed">
          Savollaringiz yoki o'lcham tanlash bo'yicha yordam kerak bo'lsa, adminga yozishingiz mumkin.
        </p>
        <button
          onClick={() => openTelegramLink(`https://t.me/${contactUser}`)}
          className="w-full mt-2 py-2.5 px-4 rounded-xl bg-[#111315] border border-[#26292E] text-xs font-bold text-[#F5F2E9] flex items-center justify-center gap-2 hover:border-[#C7F464]/40"
        >
          <span>Admin bilan yozishish (@{contactUser})</span>
          <ExternalLink size={13} />
        </button>
      </div>

      {/* Top-up Modal (Honest, Real message - no fake payments) */}
      {showTopUpModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#1A1D20] border border-[#26292E] rounded-2xl max-w-sm w-full p-5 space-y-4 animate-scaleIn relative">
            <button
              onClick={() => setShowTopUpModal(false)}
              className="absolute top-3.5 right-3.5 text-[#8E95A0] hover:text-[#F5F2E9]"
            >
              <X size={18} />
            </button>

            <div className="w-12 h-12 rounded-full bg-yellow-500/10 text-yellow-400 flex items-center justify-center">
              <AlertCircle size={24} />
            </div>

            <div className="space-y-1.5">
              <h3 className="text-sm font-black uppercase text-[#F5F2E9]">
                Hisobni to'ldirish
              </h3>
              <p className="text-xs text-[#8E95A0] leading-relaxed">
                Avtomatik to'lov tizimlari (Payme / Click) tez orada ulanadi. Hozirda hisobingizni to'ldirish yoki buyurtma to'lovini amalga oshirish uchun admin bilan bog'laning.
              </p>
            </div>

            <div className="space-y-2 pt-2">
              <button
                onClick={() => {
                  setShowTopUpModal(false);
                  openTelegramLink(`https://t.me/${contactUser}`);
                }}
                className="w-full py-3 rounded-xl bg-[#C7F464] text-[#111315] font-black text-xs uppercase tracking-wider flex items-center justify-center gap-2 shadow"
              >
                <span>Admin bilan bog'lanish</span>
                <ExternalLink size={14} />
              </button>

              <button
                onClick={() => setShowTopUpModal(false)}
                className="w-full py-2.5 rounded-xl bg-[#111315] border border-[#26292E] text-xs font-bold text-[#8E95A0]"
              >
                Yopish
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
