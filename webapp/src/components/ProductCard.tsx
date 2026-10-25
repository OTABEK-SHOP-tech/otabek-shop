import React, { useState } from 'react';
import { ArrowUpRight, Heart, Image } from 'lucide-react';
import { Product } from '../types';
import { getMediaUrl, formatPrice } from '../utils/format';
import { haptic } from '../utils/telegram';

interface ProductCardProps { product: Product; isWishlisted?: boolean; onToggleWishlist?: (id: number) => void; onSelect: (product: Product) => void; onQuickAdd?: (product: Product, e: React.MouseEvent) => void; }
export const ProductCard: React.FC<ProductCardProps> = ({ product, isWishlisted = false, onToggleWishlist, onSelect }) => {
  const [failed, setFailed] = useState(false);
  const validDiscount = !product.is_demo && product.old_price != null && product.old_price > product.price;
  return <article className="bs-product-card">
    <button className="bs-product-photo" onClick={() => { haptic.selection(); onSelect(product); }} aria-label={`${product.title} — batafsil`}>
      {!failed && product.photos?.length ? <img src={getMediaUrl(product.photos[0])} alt={product.title} onError={() => setFailed(true)} loading="lazy" /> : <span className="bs-photo-fallback"><Image size={28} strokeWidth={1} /><span>BEK STYLE</span></span>}
      <span className="bs-product-badges">{product.is_demo ? <span className="bs-badge-new">Namuna</span> : validDiscount ? <span className="bs-badge-sale">−{Math.round((1 - product.price / product.old_price!) * 100)}%</span> : product.is_new ? <span className="bs-badge-new"><i />Yangi</span> : null}</span>
      {!product.in_stock && <span className="bs-sold-out">Hozircha mavjud emas</span>}
      <span className="bs-product-open"><ArrowUpRight size={17} /></span>
    </button>
    {onToggleWishlist && <button className={`bs-product-heart ${isWishlisted ? 'is-saved' : ''}`} onClick={() => { haptic.impact('light'); onToggleWishlist(product.id); }} aria-label={isWishlisted ? 'Sevimlilardan olib tashlash' : 'Sevimlilarga qo‘shish'} aria-pressed={isWishlisted}><Heart size={17} fill={isWishlisted ? 'currentColor' : 'none'} strokeWidth={1.7} /></button>}
    <button className="bs-product-info" onClick={() => onSelect(product)}>
      <span className="bs-product-category">{product.category_name}</span>
      <h3>{product.title}</h3>
      <span className="bs-product-prices"><strong>{formatPrice(product.price)}</strong>{validDiscount && <del>{formatPrice(product.old_price)}</del>}</span>
      <span className="bs-product-size">{product.sizes?.length ? product.sizes.slice(0, 4).join(' · ') + (product.sizes.length > 4 ? ' +' : '') : 'Batafsil ko‘rish'}</span>
    </button>
  </article>;
};
