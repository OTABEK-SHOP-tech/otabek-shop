import React from 'react';
import { ArrowRight, ArrowUpRight, PackageCheck, Truck, Sparkles, ShoppingBag } from 'lucide-react';
import { Category, Product } from '../types';
import { CategoryChips } from '../components/CategoryChips';
import { ProductCard } from '../components/ProductCard';
import { formatPrice, getMediaUrl } from '../utils/format';

interface HomePageProps {
  products: Product[]; categories: Category[]; selectedCategoryId: number | null;
  onSelectCategory: (id: number | null) => void; onSelectProduct: (product: Product) => void;
  onGoToCatalog: () => void; wishlistIds?: number[]; onToggleWishlist?: (id: number) => void;
}
export const HomePage: React.FC<HomePageProps> = ({ products, categories, selectedCategoryId, onSelectCategory, onSelectProduct, onGoToCatalog, wishlistIds = [], onToggleWishlist }) => {
  const filtered = selectedCategoryId === null ? products : products.filter(p => p.category_id === selectedCategoryId);
  const hero = products.find(p => p.is_hit && p.photos?.length) || products.find(p => p.photos?.length);
  const arrivals = products.filter(p => p.is_new).slice(0, 6);
  const selectedName = categories.find(c => c.id === selectedCategoryId)?.name;
  return <div className="bs-home bs-page">
    <CategoryChips categories={categories} selectedCategoryId={selectedCategoryId} onSelectCategory={onSelectCategory} />
    {selectedCategoryId === null && <>
      <section className="bs-hero">
        <div className="bs-hero-copy"><span className="bs-hero-kicker"><span /> {hero?.is_demo ? 'Namuna tanlovi' : 'BEK tanlovi'}</span><h2>O‘z uslubing.<br /><i>O‘z qoidang.</i></h2><p>Kuningga mos kiyimlar<br />va kichik detallar.</p><button onClick={hero ? () => onSelectProduct(hero) : onGoToCatalog}>{hero?.is_demo ? 'Namunani ko‘rish' : 'Kolleksiyani ko‘rish'} <ArrowUpRight size={16} /></button></div>
        {hero && <div className="bs-hero-visual"><div className="bs-hero-photo"><img src={getMediaUrl(hero.photos[0])} alt={hero.title} /></div><span className="bs-hero-price"><small>BEK STYLE</small><b>{formatPrice(hero.price)}</b></span></div>}
        <span className="bs-hero-line" aria-hidden="true" />
      </section>
      {products.length > 0 && products.every(p => p.is_demo) && <p className="bs-demo-notice">Namuna katalogi <span>·</span> Haqiqiy mahsulotlar tayyorlanmoqda</p>}
      <div className="bs-service-strip"><span><PackageCheck size={15} /> Buyurtma asosida</span><i /><span><Truck size={15} /> Kargo alohida</span></div>
      {arrivals.length > 0 && <section className="bs-arrivals-section"><div className="bs-section-heading"><div><span className="bs-eyebrow">Yangi tanlov</span><h2>Yangi kelganlar <Sparkles size={16} /></h2></div><button onClick={onGoToCatalog} aria-label="Barcha yangi mahsulotlarni ko‘rish"><ArrowRight size={20} /></button></div><div className="bs-arrivals">{arrivals.map(p => <ProductCard key={p.id} product={p} onSelect={onSelectProduct} isWishlisted={wishlistIds.includes(p.id)} onToggleWishlist={onToggleWishlist} />)}</div></section>}
    </>}
    <section><div className="bs-section-heading"><div><span className="bs-eyebrow">Sizning garderobingiz</span><h2>{selectedName || 'Kiyimingni tanla'}<span className="bs-result-count">{filtered.length}</span></h2></div>{selectedCategoryId === null && <button className="bs-text-link" onClick={onGoToCatalog}>Barchasi <ArrowRight size={14} /></button>}</div>
      {filtered.length ? <div className="bs-product-grid">{filtered.map(p => <ProductCard key={p.id} product={p} onSelect={onSelectProduct} isWishlisted={wishlistIds.includes(p.id)} onToggleWishlist={onToggleWishlist} />)}</div> : <div className="bs-empty"><ShoppingBag size={32} strokeWidth={1.3} /><h3>Bu bo‘lim hali yangilanmoqda</h3><p>Boshqa bo‘limdagi mahsulotlarni ko‘ring.</p><button className="bs-button" onClick={() => onSelectCategory(null)}>Barchasini ko‘rish</button></div>}
    </section>
    <div className="bs-page-signature"><span>Bek <i>style.</i></span><p>Uslub — o‘zingdan boshlanadi.</p></div>
  </div>;
};
