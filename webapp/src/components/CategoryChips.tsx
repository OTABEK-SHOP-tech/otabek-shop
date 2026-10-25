import React from 'react';
import { Category } from '../types';
import { haptic } from '../utils/telegram';

interface CategoryChipsProps {
  categories: Category[];
  selectedCategoryId: number | null;
  onSelectCategory: (categoryId: number | null) => void;
}

export const CategoryChips: React.FC<CategoryChipsProps> = ({
  categories,
  selectedCategoryId,
  onSelectCategory,
}) => {
  return (
    <div className="flex items-center gap-2 overflow-x-auto no-scrollbar py-1 px-4 -mx-4">
      <button
        onClick={() => {
          haptic.selection();
          onSelectCategory(null);
        }}
        className={`whitespace-nowrap px-3.5 py-1.5 rounded-full text-xs font-bold transition-all ${
          selectedCategoryId === null
            ? 'bg-[#C7F464] text-[#111315] shadow-sm'
            : 'bg-[#1A1D20] text-[#8E95A0] border border-[#26292E] hover:text-[#F5F2E9]'
        }`}
      >
        🔥 Barchasi
      </button>

      {categories.map((cat) => {
        const isSelected = selectedCategoryId === cat.id;
        return (
          <button
            key={cat.id}
            onClick={() => {
              haptic.selection();
              onSelectCategory(cat.id);
            }}
            className={`whitespace-nowrap px-3.5 py-1.5 rounded-full text-xs font-bold transition-all flex items-center gap-1.5 ${
              isSelected
                ? 'bg-[#C7F464] text-[#111315] shadow-sm'
                : 'bg-[#1A1D20] text-[#8E95A0] border border-[#26292E] hover:text-[#F5F2E9]'
            }`}
          >
            <span>{cat.emoji}</span>
            <span>{cat.name}</span>
            {cat.product_count > 0 && (
              <span className={`text-[10px] opacity-70 ${isSelected ? 'text-[#111315]' : 'text-[#8E95A0]'}`}>
                {cat.product_count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
