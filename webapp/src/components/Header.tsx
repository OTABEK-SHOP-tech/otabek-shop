import React from 'react';
import { Search } from 'lucide-react';

interface HeaderProps {
  onSearchClick: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onSearchClick }) => {
  return (
    <header className="sticky top-0 z-30 bg-[#111315]/95 backdrop-blur-md border-b border-[#26292E] px-4 py-3">
      <div className="flex items-center justify-between max-w-lg mx-auto">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-[#C7F464] flex items-center justify-center font-black text-[#111315] text-sm tracking-tighter">
            BS
          </div>
          <div>
            <h1 className="text-base font-black tracking-wider text-[#F5F2E9] uppercase flex items-center gap-1.5">
              BEK STYLE
              <span className="w-1.5 h-1.5 rounded-full bg-[#C7F464]"></span>
            </h1>
            <p className="text-[10px] font-medium tracking-widest text-[#8E95A0] uppercase">
              Streetwear &amp; Casual
            </p>
          </div>
        </div>

        <button
          onClick={onSearchClick}
          aria-label="Qidirish"
          className="w-9 h-9 rounded-full bg-[#1A1D20] border border-[#26292E] flex items-center justify-center text-[#F5F2E9] active:scale-95 transition-transform"
        >
          <Search size={17} className="text-[#8E95A0]" />
        </button>
      </div>
    </header>
  );
};
