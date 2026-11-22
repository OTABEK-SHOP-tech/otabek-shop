import React, { useState, useEffect } from 'react';
import { Globe, Sparkles, Send, ExternalLink, Shield, Package, Heart, Gift, Copy, Check, Share2 } from 'lucide-react';
import { ShopSettings, ReferralStats } from '../types';
import { Language, Translations } from '../i18n';
import { openTelegramLink, haptic, copyTextToClipboard } from '../utils/telegram';
import { formatPrice } from '../utils/format';

interface SettingsPageProps {
  settings: ShopSettings;
  currentLang: Language;
  onLanguageChange: (lang: Language) => void;
  petalsEnabled: boolean;
  onTogglePetals: () => void;
  reducedMotion: boolean;
  onToggleReducedMotion: () => void;
  t: Translations;
  initData?: string;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({
  settings,
  currentLang,
  onLanguageChange,
  petalsEnabled,
  onTogglePetals,
  reducedMotion,
  onToggleReducedMotion,
  t,
  initData,
}) => {
  const [referralStats, setReferralStats] = useState<ReferralStats | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);

  useEffect(() => {
    if (!initData) return;
    fetch('/api/referrals/me', {
      headers: { 'X-Telegram-Init-Data': initData },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: ReferralStats | null) => {
        if (d) setReferralStats(d);
      })
      .catch(() => {});
  }, [initData]);

  const languages: { code: Language; label: string; flag: string }[] = [
    { code: 'uz', label: "O'zbekcha", flag: '🇺🇿' },
    { code: 'ru', label: 'Русский', flag: '🇷🇺' },
    { code: 'en', label: 'English', flag: '🇬🇧' },
  ];

  return (
    <div className="pb-32 px-4 max-w-md mx-auto">
      <div className="py-3">
        <h2 className="text-lg font-black text-sakura-plum dark:text-white flex items-center gap-2">
          <span>⚙️</span>
          <span>{t.settings}</span>
        </h2>
      </div>

      {/* 20% Referral Program Card */}
      {referralStats && (
        <div className="p-4 rounded-3xl bg-gradient-to-br from-pink-50 via-rose-50 to-purple-50 dark:from-pink-950/40 dark:via-rose-950/40 dark:to-purple-950/40 border border-sakura-pink/40 shadow-sakura-sm mb-3 text-left">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Gift className="w-4 h-4 text-sakura-rose" />
              <span className="text-xs font-black text-sakura-darkrose dark:text-sakura-pink">
                20% Chegirma — Do'stlarni taklif qilish
              </span>
            </div>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-sakura-rose text-white">
              {referralStats.confirmed_count} ta do'st
            </span>
          </div>

          <p className="text-[11px] text-sakura-plum/80 dark:text-sakura-blush/80 leading-relaxed mb-3">
            Har <b>5 ta do'st</b> taklif qilganingizda, hohlagan 1 dona tovaringizga <b>20% CHEGIRMA</b> kuponini olasiz!
          </p>

          {/* Progress bar */}
          <div className="mb-3 p-2.5 rounded-2xl bg-white/80 dark:bg-sakura-darkcard/80 border border-sakura-pink/20">
            <div className="flex justify-between text-[11px] font-bold mb-1">
              <span className="text-sakura-plum dark:text-white">
                Keyingi kupongacha: {referralStats.friends_needed_for_next} ta do'st
              </span>
              <span className="text-sakura-rose font-mono">
                {referralStats.confirmed_count % 5} / 5
              </span>
            </div>
            <div className="w-full h-2 rounded-full bg-sakura-pink/20 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-sakura-pink to-sakura-rose transition-all duration-500 rounded-full"
                style={{ width: `${((referralStats.confirmed_count % 5) / 5) * 100}%` }}
              />
            </div>
          </div>

          {/* Available and Locked coupons */}
          {referralStats.available_coupons && referralStats.available_coupons.length > 0 && (
            <div className="mb-3 space-y-2">
              {/* Active Coupons */}
              {referralStats.available_coupons.filter((cp) => cp.is_valid && !cp.is_used).length > 0 && (
                <div className="space-y-1">
                  <span className="text-[10px] font-bold text-sakura-darkrose dark:text-sakura-pink uppercase">
                    🎟 Faol 20% kuponlaringiz:
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {referralStats.available_coupons
                      .filter((cp) => cp.is_valid && !cp.is_used)
                      .map((cp) => (
                        <span
                          key={cp.id}
                          className="px-2 py-1 rounded-xl bg-sakura-rose text-white font-mono font-bold text-[11px] shadow-xs"
                        >
                          {cp.code} (-20%)
                        </span>
                      ))}
                  </div>
                </div>
              )}

              {/* Locked Coupons (when invited friends left channel) */}
              {referralStats.available_coupons.filter((cp) => !cp.is_valid && !cp.is_used).length > 0 && (
                <div className="space-y-1">
                  <span className="text-[10px] font-bold text-amber-700 dark:text-amber-400 uppercase">
                    🔒 Qulflangan kuponlar:
                  </span>
                  <div className="flex flex-wrap gap-1">
                    {referralStats.available_coupons
                      .filter((cp) => !cp.is_valid && !cp.is_used)
                      .map((cp) => (
                        <span
                          key={cp.id}
                          className="px-2 py-1 rounded-xl bg-gray-200 dark:bg-gray-800 text-gray-700 dark:text-gray-300 font-mono text-[11px] border border-gray-300 dark:border-gray-700"
                        >
                          {cp.code} (yana {Math.max(1, cp.milestone - referralStats.confirmed_count)} ta do'st kerak)
                        </span>
                      ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Link action buttons */}
          <div className="flex gap-2">
            <button
              onClick={async () => {
                await copyTextToClipboard(referralStats.referral_link);
                setCopiedLink(true);
                haptic.notification('success');
                setTimeout(() => setCopiedLink(false), 2000);
              }}
              className="flex-1 py-2 px-3 rounded-xl bg-white dark:bg-sakura-darkcard text-sakura-plum dark:text-white font-bold text-xs flex items-center justify-center gap-1.5 border border-sakura-pink/40 active:scale-95 transition-transform"
            >
              {copiedLink ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5 text-sakura-rose" />}
              <span>{copiedLink ? "Nusxalandi" : "Havolani nusxalash"}</span>
            </button>

            <button
              onClick={() => {
                const text = `🌸 Moonlight Chinese Shop go'zal do'koniga taklif qilaman! ✨\nKanalga a'zo bo'ling: ${referralStats.referral_link}`;
                openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(referralStats.referral_link)}&text=${encodeURIComponent(text)}`);
              }}
              className="py-2 px-3 rounded-xl bg-gradient-to-r from-sakura-rose to-sakura-darkrose text-white font-bold text-xs flex items-center justify-center gap-1.5 shadow-sakura active:scale-95 transition-transform"
            >
              <Share2 className="w-3.5 h-3.5" />
              <span>Ulashish</span>
            </button>
          </div>
        </div>
      )}

      {/* Language Selection Card */}
      <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-sakura-sm mb-3">
        <div className="flex items-center gap-2 mb-3 text-xs font-extrabold text-sakura-plum dark:text-white">
          <Globe className="w-4 h-4 text-sakura-rose" />
          <span>{t.languageSelect}</span>
        </div>

        <div className="grid grid-cols-3 gap-2">
          {languages.map((l) => (
            <button
              key={l.code}
              onClick={() => {
                haptic.selection();
                onLanguageChange(l.code);
              }}
              className={`py-2 px-3 rounded-2xl flex flex-col items-center justify-center gap-1 text-xs font-extrabold transition-all active:scale-95 ${
                currentLang === l.code
                  ? 'bg-gradient-to-r from-sakura-rose to-sakura-darkrose text-white shadow-sakura'
                  : 'bg-sakura-cream dark:bg-sakura-darkcardsoft border border-sakura-pink/30 text-sakura-plum dark:text-sakura-blush'
              }`}
            >
              <span className="text-base">{l.flag}</span>
              <span>{l.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Visual Effects Toggles */}
      <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-sakura-sm mb-3">
        <div className="flex items-center justify-between py-2 border-b border-sakura-pink/15">
          <div className="flex items-center gap-2">
            <span className="text-base">🌸</span>
            <span className="text-xs font-bold text-sakura-plum dark:text-white">{t.fallingPetals}</span>
          </div>
          <button
            onClick={() => {
              haptic.selection();
              onTogglePetals();
            }}
            className={`w-12 h-6 flex items-center rounded-full p-1 transition-colors duration-200 ${
              petalsEnabled ? 'bg-sakura-rose' : 'bg-gray-300 dark:bg-gray-700'
            }`}
          >
            <div
              className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform duration-200 ${
                petalsEnabled ? 'translate-x-6' : 'translate-x-0'
              }`}
            />
          </button>
        </div>

        <div className="flex items-center justify-between py-2 mt-1">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-sakura-rose" />
            <span className="text-xs font-bold text-sakura-plum dark:text-white">{t.reducedMotion}</span>
          </div>
          <button
            onClick={() => {
              haptic.selection();
              onToggleReducedMotion();
            }}
            className={`w-12 h-6 flex items-center rounded-full p-1 transition-colors duration-200 ${
              reducedMotion ? 'bg-sakura-rose' : 'bg-gray-300 dark:bg-gray-700'
            }`}
          >
            <div
              className={`bg-white w-4 h-4 rounded-full shadow-md transform transition-transform duration-200 ${
                reducedMotion ? 'translate-x-6' : 'translate-x-0'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Official Links & Contact */}
      <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-sakura-sm mb-3">
        <h4 className="text-xs font-extrabold text-sakura-plum dark:text-white uppercase mb-2">
          Rasmiy kanallar 💌
        </h4>

        <div className="flex flex-col gap-2">
          <button
            onClick={() => openTelegramLink(settings.channel_url || 'https://t.me/moonlight_chinese_shop')}
            className="flex items-center justify-between p-3 rounded-2xl bg-sakura-cream dark:bg-sakura-darkcardsoft text-left hover:bg-sakura-blush/40 transition-colors"
          >
            <div className="flex items-center gap-2.5">
              <span className="text-lg">📢</span>
              <div>
                <span className="text-xs font-extrabold block">Telegram Kanal</span>
                <span className="text-[11px] text-sakura-rose font-mono">
                  {settings.channel_url ? settings.channel_url.replace('https://t.me/', '@') : '@moonlight_chinese_shop'}
                </span>
              </div>
            </div>
            <ExternalLink className="w-4 h-4 text-sakura-rose/70" />
          </button>

          <button
            onClick={() => {
              const rawContact = settings.contact_username || 'MOONLIGHT_ADMINNN';
              const clean = rawContact.replace('@', '');
              const link = rawContact.startsWith('+') || /^\d+$/.test(rawContact)
                ? `https://t.me/+${clean.replace('+', '')}`
                : `https://t.me/${clean}`;
              openTelegramLink(link);
            }}
            className="flex items-center justify-between p-3 rounded-2xl bg-sakura-cream dark:bg-sakura-darkcardsoft text-left hover:bg-sakura-blush/40 transition-colors"
          >
            <div className="flex items-center gap-2.5">
              <span className="text-lg">💌</span>
              <div>
                <span className="text-xs font-extrabold block">Do'kon egasi & Buyurtmalar</span>
                <span className="text-[11px] text-sakura-rose font-mono">
                  {settings.contact_username
                    ? (settings.contact_username.startsWith('+') ? settings.contact_username : `@${settings.contact_username.replace('@', '')}`)
                    : '@MOONLIGHT_ADMINNN'}
                </span>
              </div>
            </div>
            <ExternalLink className="w-4 h-4 text-sakura-rose/70" />
          </button>
        </div>
      </div>

      {/* Store Terms Info */}
      <div className="p-4 rounded-3xl bg-white/90 dark:bg-sakura-darkcard/90 backdrop-blur-md border border-sakura-pink/20 shadow-sakura-sm text-xs text-sakura-plum/80 dark:text-sakura-blush/80 space-y-1.5">
        <div className="font-extrabold text-sakura-rose flex items-center gap-1.5 mb-1">
          <Heart className="w-3.5 h-3.5 fill-sakura-rose" />
          <span>Moonlight Chinese Shop haqida</span>
        </div>
        <p className="font-bold">📦 Kargo tariflari:</p>
        <p className="pl-3">✈️ AVIA (7–9 kun): {formatPrice(settings.cargo_rate_avia || 14000)} / 100g</p>
        <p className="pl-3">🚗 AVTO (14–18 kun): {formatPrice(settings.cargo_rate_avto || 10000)} / 100g</p>
        <p>🚚 Dastavka: {settings.delivery_scope || "O'zbekiston bo'ylab"}</p>
        <p>💳 To'lov: {settings.payment_terms || "100% oldindan to'lov"}</p>
        <p>📍 Joylashuv: {settings.location || "Toshkent"}</p>
      </div>

      <div className="text-center mt-6 text-[10px] text-sakura-plum/40 dark:text-sakura-blush/40">
        Moonlight Chinese Shop Mini App v1.0.0 🌸
      </div>
    </div>
  );
};
