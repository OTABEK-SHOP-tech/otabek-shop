import React from 'react';
import { Search, X } from 'lucide-react';

interface HeaderProps {
  searchQuery?: string;
  onSearchChange?: (q: string) => void;
  onSearchClick?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  searchQuery = '',
  onSearchChange,
  onSearchClick,
}) => {
  return (
    <header className="sticky top-0 z-30 bg-white/95 backdrop-blur-md border-b border-gray-200/80 px-4 pt-3 pb-3.5 transition-all">
      <div className="max-w-lg mx-auto">
        {/* Brand Top Row */}
        <div className="flex items-center justify-between mb-2.5">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-gray-900 flex items-center justify-center font-black text-white text-xs tracking-wider shadow-sm">
              BS
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <h1 className="text-base font-extrabold tracking-wide text-gray-900">
                  BEK STYLE
                </h1>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
              </div>
              <p className="text-[11px] font-semibold text-gray-500 tracking-tight">
                Yigitlar kiyimi
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200/60">
              Original • Pinduoduo
            </span>
          </div>
        </div>

        {/* Search Input Bar */}
        <div className="relative flex items-center">
          <Search className="absolute left-3.5 w-4 h-4 text-gray-400 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onClick={onSearchClick}
            onChange={(e) => onSearchChange && onSearchChange(e.target.value)}
            placeholder="Mahsulot qidirish..."
            className="w-full pl-10 pr-9 py-2 rounded-xl bg-gray-100/80 hover:bg-gray-100 focus:bg-white border border-transparent focus:border-gray-300 text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/20 transition-all"
          />
          {searchQuery && onSearchChange && (
            <button
              onClick={() => onSearchChange('')}
              className="absolute right-3 p-0.5 rounded-full text-gray-400 hover:text-gray-600 active:scale-95"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
