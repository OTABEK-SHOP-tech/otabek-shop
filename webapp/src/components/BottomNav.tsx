import React from 'react';
import { House, LayoutGrid, ShoppingBag, UserRound } from 'lucide-react';
import { TabType } from '../types';

interface BottomNavProps { activeTab: TabType; onTabChange: (tab: TabType) => void; cartCount: number; }

export const BottomNav: React.FC<BottomNavProps> = ({ activeTab, onTabChange, cartCount }) => {
  const tabs = [
    { id: 'home' as TabType, label: 'Bosh sahifa', icon: House },
    { id: 'catalog' as TabType, label: 'Katalog', icon: LayoutGrid },
    { id: 'cart' as TabType, label: 'Savat', icon: ShoppingBag },
    { id: 'profile' as TabType, label: 'Profil', icon: UserRound },
  ];
  return <nav className="bs-bottom-nav" aria-label="Asosiy menyu"><div className="bs-nav-inner">{tabs.map(tab => {
    const Icon = tab.icon;
    const active = activeTab === tab.id;
    return <button key={tab.id} onClick={() => onTabChange(tab.id)} className={`bs-nav-item ${active ? 'is-active' : ''}`} aria-current={active ? 'page' : undefined}>
      <span className="bs-nav-icon"><Icon size={22} strokeWidth={active ? 2.15 : 1.65} />{tab.id === 'cart' && cartCount > 0 && <b className="bs-cart-badge">{cartCount > 99 ? '99+' : cartCount}</b>}</span>
      <span>{tab.label}</span><i />
    </button>;
  })}</div></nav>;
};
