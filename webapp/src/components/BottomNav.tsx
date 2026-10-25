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
    <nav className="fixed bottom-0 left-0 right-0 z-40 bg-[#111315]/95 backdrop-blur-lg border-t border-[#26292E] pb-safe">
      <div className="flex items-center justify-around max-w-lg mx-auto py-2">
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
                <Icon
                  size={21}
                  className={`transition-colors duration-200 ${
                    isActive ? 'text-[#C7F464]' : 'text-[#8E95A0]'
                  }`}
                  strokeWidth={isActive ? 2.5 : 2}
                />
                {tab.badge && tab.badge > 0 ? (
                  <span className="absolute -top-1.5 -right-2.5 bg-[#C7F464] text-[#111315] font-black text-[10px] min-w-[17px] h-[17px] rounded-full flex items-center justify-center px-1 shadow-sm">
                    {tab.badge > 99 ? '99+' : tab.badge}
                  </span>
                ) : null}
              </div>
              <span
                className={`text-[11px] font-semibold mt-1 transition-colors duration-200 ${
                  isActive ? 'text-[#C7F464]' : 'text-[#8E95A0]'
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
