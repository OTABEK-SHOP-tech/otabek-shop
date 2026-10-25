import React, { useState, useMemo } from 'react';
import { ArrowUpDown, SlidersHorizontal, X, Search, Heart } from 'lucide-react';
import { Category, Product } from '../types';
import { ProductCard } from '../components/ProductCard';
import { CategoryChips } from '../components/CategoryChips';

interface CatalogPageProps {
  products: Product[]; categories: Category[]; selectedCategoryId: number | null;
  onSelectCategory: (id: number | null) => void; onSelectProduct: (p: Product) => void;
  initialSearch?: string; wishlistIds?: number[]; onToggleWishlist?: (id: number) => void;
  wishlistOnly?: boolean; onClearWishlistFilter?: () => void;
}
export const CatalogPage: React.FC<CatalogPageProps> = ({ products, categories, selectedCategoryId, onSelectCategory, onSelectProduct, initialSearch = '', wishlistIds = [], onToggleWishlist, wishlistOnly = false, onClearWishlistFilter }) => {
  const [size, setSize] = useState<string | null>(null);
  const [sort, setSort] = useState('newest');
  const [filters, setFilters] = useState(false);
  const sizes = Array.from(new Set(products.flatMap(p => p.sizes || [])));
  const filtered = useMemo(() => products.filter(p =>
    (selectedCategoryId === null || p.category_id === selectedCategoryId) &&
    (!initialSearch.trim() || `${p.title} ${p.description} ${p.category_name}`.toLocaleLowerCase().includes(initialSearch.trim().toLocaleLowerCase())) &&
    (!size || p.sizes.includes(size)) && (!wishlistOnly || wishlistIds.includes(p.id))
  ).sort((a,b) => sort === 'price_asc' ? a.price - b.price : sort === 'price_desc' ? b.price - a.price : b.id - a.id), [products, selectedCategoryId, initialSearch, size, sort, wishlistOnly, wishlistIds]);
  return <div className="bs-page bs-catalog"><div className="bs-section-heading bs-catalog-title"><div><span className="bs-eyebrow">BEK STYLE tanlovi</span><h1>{wishlistOnly ? 'Sevimlilar' : 'Katalog'}{wishlistOnly && <Heart size={20} />}</h1></div><span className="bs-count-label">{filtered.length} ta mahsulot</span></div>
    {wishlistOnly && <button className="bs-filter-tag" onClick={onClearWishlistFilter}>Sevimli mahsulotlar <X size={13} /></button>}
    <CategoryChips categories={categories} selectedCategoryId={selectedCategoryId} onSelectCategory={onSelectCategory} />
    <div className="bs-catalog-tools"><button onClick={() => setFilters(!filters)} className={filters || size ? 'is-active' : ''}><SlidersHorizontal size={16} /> Filtrlar {size && <span className="bs-small-dot" />}</button><div className="bs-sort"><ArrowUpDown size={14} /><select aria-label="Mahsulotlarni saralash" value={sort} onChange={e => setSort(e.target.value)}><option value="newest">Eng yangi</option><option value="price_asc">Arzonroq</option><option value="price_desc">Qimmatroq</option></select></div></div>
    {filters && <div className="bs-filter-panel"><div><strong>O‘lchamni tanlang</strong>{size && <button onClick={() => setSize(null)}>Tozalash</button>}</div><div className="bs-option-list">{sizes.map(s => <button key={s} className={size === s ? 'is-selected' : ''} onClick={() => setSize(size === s ? null : s)} aria-pressed={size === s}>{s}</button>)}</div></div>}
    {initialSearch && <p className="bs-search-result">“{initialSearch}” uchun {filtered.length} ta natija</p>}
    {filtered.length ? <div className="bs-product-grid">{filtered.map(p => <ProductCard key={p.id} product={p} onSelect={onSelectProduct} isWishlisted={wishlistIds.includes(p.id)} onToggleWishlist={onToggleWishlist} />)}</div> : <div className="bs-empty"><Search size={36} strokeWidth={1.2} /><h3>{wishlistOnly ? 'Sevimlilaringiz shu yerda bo‘ladi' : 'Mahsulot topilmadi'}</h3><p>{wishlistOnly ? 'Yoqtirgan mahsulotingizdagi yurakchani bosing.' : 'Qidiruv yoki tanlangan filtrlarni o‘zgartirib ko‘ring.'}</p><button className="bs-button" onClick={() => { setSize(null); onSelectCategory(null); onClearWishlistFilter?.(); }}>Barcha mahsulotlar</button></div>}
  </div>;
};
