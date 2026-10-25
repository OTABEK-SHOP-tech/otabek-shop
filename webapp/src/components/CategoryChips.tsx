import React from 'react';
import { Grid2X2, Shirt, Footprints, Backpack, Layers, Wind } from 'lucide-react';
import { Category } from '../types';
import { haptic } from '../utils/telegram';

interface CategoryChipsProps { categories: Category[]; selectedCategoryId: number | null; onSelectCategory: (id: number | null) => void; }
const categoryIcon = (name: string) => /oyoq|kross/i.test(name) ? Footprints : /akses|sumka|taqin/i.test(name) ? Backpack : /kurt/i.test(name) ? Wind : /hudi|svit/i.test(name) ? Layers : Shirt;
const shortName = (name: string) => name.replace('Hudi va svitshotlar', 'Hudi va svitshot').replace('Futbolkalar', 'Futbolka').replace('Kurtkalar', 'Kurtka').replace('Shimlar', 'Shim');
export const CategoryChips: React.FC<CategoryChipsProps> = ({ categories, selectedCategoryId, onSelectCategory }) => (
  <div className="bs-category-strip" aria-label="Mahsulot bo‘limlari">
    <button className={`bs-chip ${selectedCategoryId === null ? 'is-active' : ''}`} onClick={() => { haptic.selection(); onSelectCategory(null); }}><Grid2X2 size={15} /> Barchasi</button>
    {categories.map(cat => { const Icon = categoryIcon(cat.name); return <button key={cat.id} className={`bs-chip ${selectedCategoryId === cat.id ? 'is-active' : ''}`} onClick={() => { haptic.selection(); onSelectCategory(cat.id); }}><Icon size={16} strokeWidth={1.7} /><span>{shortName(cat.name)}</span>{cat.product_count > 0 && <small>{cat.product_count}</small>}</button>; })}
  </div>
);
