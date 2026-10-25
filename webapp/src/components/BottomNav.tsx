import React from 'react';
import { Home, Compass, ShoppingBag, User } from 'lucide-react';
import { TabType } from '../types';
import { haptic } from '../utils/telegram';

interface BottomNavProps {
  activeTab: TabType;
  onTabChange: (tab: TabType) => void;
  cartCount: number;
}

export const BottomNav: React.FC<BottomNavProps> = ({
  activeTab,
  onTabChange,
  cartCount,
}) => {
  const tabs = [
    { id: 'home' as TabType, label: 'Bosh sahifa', icon: Home },
    { id: 'catalog' as TabType, label: 'Katalog', icon: Compass },
    { id: 'cart' as TabType, label: 'Savat', icon: ShoppingBag, badge: cartCount },
    { id: 'profile' as TabType, label: 'Profil', icon: User },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 backdrop-blur-md border-t border-gray-200/80 pb-safe shadow-[0_-2px_12px_rgba(0,0,0,0.04)]">
      <div className="flex items-center justify-around max-w-lg mx-auto py-1.5 px-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;

          return (
            <button
              key={tab.id}
              onClick={() => {
                haptic.selection();
                onTabChange(tab.id);
              }}
              className="relative flex flex-col items-center justify-center flex-1 py-1 transition-all active:scale-95"
            >
              <div className="relative">
                <div
                  className={`p-1 rounded-xl transition-all ${
                    isActive ? 'bg-emerald-50 text-emerald-600 scale-105' : 'text-gray-400'
                  }`}
                >
                  <Icon
                    size={20}
                    className={`transition-colors duration-200 ${
                      isActive ? 'text-emerald-600' : 'text-gray-400'
                    }`}
                    strokeWidth={isActive ? 2.4 : 1.9}
                  />
                </div>

                {tab.badge !== undefined && tab.badge > 0 && (
                  <span className="absolute -top-1 -right-2 bg-emerald-600 text-white font-black text-[10px] min-w-[17px] h-[17px] rounded-full flex items-center justify-center px-1 shadow-xs">
                    {tab.badge > 99 ? '99+' : tab.badge}
                  </span>
                )}
              </div>
              <span
                className={`text-[10px] font-bold mt-0.5 tracking-tight transition-colors duration-200 ${
                  isActive ? 'text-emerald-700 font-extrabold' : 'text-gray-400'
                }`}
              >
                {tab.label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
