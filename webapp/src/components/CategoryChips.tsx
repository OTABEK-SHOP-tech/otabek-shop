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
            ? 'bg-gray-900 text-white shadow-sm ring-2 ring-gray-900/10'
            : 'bg-white text-gray-600 border border-gray-200/90 hover:bg-gray-50'
        }`}
      >
        ⚡ Barchasi
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
                ? 'bg-gray-900 text-white shadow-sm ring-2 ring-gray-900/10'
                : 'bg-white text-gray-600 border border-gray-200/90 hover:bg-gray-50'
            }`}
          >
            <span>{cat.emoji}</span>
            <span>{cat.name}</span>
            {cat.product_count > 0 && (
              <span
                className={`text-[10px] px-1.5 py-0.2 rounded-full ${
                  isSelected ? 'bg-white/20 text-white' : 'bg-gray-100 text-gray-500'
                }`}
              >
                {cat.product_count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
