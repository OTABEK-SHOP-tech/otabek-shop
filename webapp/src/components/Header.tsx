import React from 'react';
import { ArrowUpRight, Heart, Search, X } from 'lucide-react';

interface HeaderProps {
  searchQuery?: string;
  onSearchChange?: (q: string) => void;
  onSearchClick?: () => void;
  onHomeClick?: () => void;
  onWishlistClick?: () => void;
  wishlistCount?: number;
  showSearch?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ searchQuery = '', onSearchChange, onSearchClick, onHomeClick, onWishlistClick, wishlistCount = 0, showSearch = true }) => (
  <header className="bs-header">
    <div className="bs-header-row">
      <button className="bs-brand" onClick={onHomeClick} aria-label="BEK STYLE bosh sahifasi">
        <span className="bs-brand-symbol">b<span>.</span></span>
        <span><span className="bs-wordmark">Bek <i>style</i><span className="bs-brand-dot">.</span></span><span className="bs-brand-caption">Yigitlar kiyimi va aksessuarlari</span></span>
      </button>
      <button className="bs-wishlist-button" onClick={onWishlistClick} aria-label="Sevimli mahsulotlar">
        <Heart size={19} strokeWidth={1.65} />
        {wishlistCount > 0 && <span>{wishlistCount}</span>}
      </button>
    </div>
    {showSearch && <div className="bs-search-wrap">
      <Search size={19} strokeWidth={1.7} />
      <input aria-label="Mahsulot qidirish" type="search" value={searchQuery} onFocus={onSearchClick} onChange={e => onSearchChange?.(e.target.value)} placeholder="O‘zingizga mosini qidiring..." />
      {searchQuery ? <button onClick={() => onSearchChange?.('')} aria-label="Qidiruvni tozalash"><X size={16} /></button> : <span className="bs-search-arrow"><ArrowUpRight size={16} /></span>}
    </div>}
  </header>
);
