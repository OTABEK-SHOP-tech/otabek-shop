import React, { useState, useEffect, useRef } from 'react';
import { ArrowLeft, Check, Minus, Plus, ShoppingBag, Package, Heart, ArrowRight, ChevronLeft, ChevronRight, Image } from 'lucide-react';
import { Product } from '../types';
import { haptic, setBackButton } from '../utils/telegram';
import { formatPrice, getMediaUrl } from '../utils/format';

interface ProductDetailPageProps {
  product: Product; onClose: () => void;
  onAddToCart: (p: Product, size: string | null, color: string | null, qty: number) => Promise<void>;
  isAddingToCart?: boolean; isWishlisted?: boolean; onToggleWishlist?: (id: number) => void;
  onGoToCart?: () => void;
}
const colorNames: Record<string,string> = {black:'Qora',white:'Oq',green:'Yashil',brown:'Jigarrang',gray:'Kulrang',grey:'Kulrang',blue:'Ko‘k',beige:'Bej',khaki:'Xaki',navy:'To‘q ko‘k',cream:'Qaymoqrang',red:'Qizil'};
const colorLabel = (c:string) => colorNames[c.toLowerCase()] || c;
export const ProductDetailPage: React.FC<ProductDetailPageProps> = ({ product, onClose, onAddToCart, isAddingToCart = false, isWishlisted = false, onToggleWishlist, onGoToCart }) => {
  const [photo, setPhoto] = useState(0);
  const [color, setColor] = useState<string | null>(null);
  const [size, setSize] = useState<string | null>(null);
  const [qty, setQty] = useState(1);
  const [added, setAdded] = useState(false);
  const [error, setError] = useState('');
  const touchStart = useRef<number | null>(null);
  const photos = product.photos || [];
  const variantAvailable = (nextColor: string | null, nextSize: string | null) => product.available_variants == null || product.available_variants.some(v => (!nextColor || v.color === nextColor) && (!nextSize || v.size === nextSize));
  useEffect(() => { setBackButton(true, onClose); window.scrollTo(0,0); return () => setBackButton(false, onClose); }, [onClose]);
  useEffect(() => { setPhoto(0); setColor(product.colors?.length === 1 ? product.colors[0] : null); setSize(product.sizes?.length === 1 ? product.sizes[0] : null); setQty(1); setError(''); setAdded(false); }, [product.id]);
  const handleAdd = async () => {
    if (product.colors?.length && !color) { setError('Avval rangni tanlang.'); return; }
    if (product.sizes?.length && !size) { setError('Avval o‘lchamni tanlang.'); return; }
    if (!variantAvailable(color, size)) { setError('Bu rang va o‘lcham hozir mavjud emas. Qayta tanlang.'); return; }
    setError('');
    try { await onAddToCart(product,size,color,qty); setAdded(true); haptic.notification('success'); }
    catch(e) { setError(e instanceof Error ? e.message : 'Savatga qo‘shilmadi. Qayta urinib ko‘ring.'); }
  };
  return <div className="bs-detail">
    <div className="bs-detail-top"><button className="bs-circle-button" onClick={onClose} aria-label="Orqaga"><ArrowLeft size={20} /></button><span>Mahsulot haqida</span><button className={`bs-circle-button ${isWishlisted ? 'is-saved' : ''}`} onClick={() => onToggleWishlist?.(product.id)} aria-label="Sevimlilarga qo‘shish" aria-pressed={isWishlisted}><Heart size={19} fill={isWishlisted ? 'currentColor' : 'none'} /></button></div>
    <div className="bs-detail-gallery" onTouchStart={e=>{touchStart.current=e.touches[0].clientX;}} onTouchEnd={e=>{if(touchStart.current===null || photos.length<2)return; const d=touchStart.current-e.changedTouches[0].clientX;if(Math.abs(d)>35)setPhoto(p=>(p+(d>0?1:-1)+photos.length)%photos.length);touchStart.current=null;}}>
      {photos[photo] ? <img src={getMediaUrl(photos[photo])} alt={`${product.title} — ${photo+1}-rasm`} /> : <span className="bs-photo-fallback"><Image size={40} /></span>}
      {product.is_new && <span className="bs-detail-label"><i /> Yangi tanlov</span>}
      {photos.length>1 && <><button className="bs-gallery-prev" onClick={()=>setPhoto((photo-1+photos.length)%photos.length)} aria-label="Oldingi rasm"><ChevronLeft size={22} /></button><button className="bs-gallery-next" onClick={()=>setPhoto((photo+1)%photos.length)} aria-label="Keyingi rasm"><ChevronRight size={22} /></button><span className="bs-photo-counter">{photo+1} / {photos.length}</span></>}
    </div>
    <div className="bs-detail-body">{product.is_demo && <div className="bs-demo-detail"><strong>Bu namuna mahsuloti</strong><p>Ko‘rinishni sinab ko‘rish uchun qo‘shilgan. Bu mahsulot uchun buyurtma va to‘lov qabul qilinmaydi.</p></div>}<div className="bs-detail-heading"><span className="bs-eyebrow">{product.category_name}</span><h1>{product.title}</h1><div className="bs-detail-prices"><strong>{formatPrice(product.price)}</strong>{!product.is_demo && product.old_price != null && product.old_price>product.price && <del>{formatPrice(product.old_price)}</del>}</div></div>
      {product.colors?.length>0 && <section className="bs-variant-section"><div className="bs-variant-label"><h2>Rang</h2><span>{color ? colorLabel(color) : 'Tanlang'}</span></div><div className="bs-option-list">{product.colors.map(c=><button key={c} disabled={!variantAvailable(c,null)} className={color===c?'is-selected':''} onClick={()=>{setColor(c);if(size&&!variantAvailable(c,size))setSize(null);setError('');setAdded(false);haptic.selection();}} aria-pressed={color===c}>{color===c&&<Check size={14}/>} {colorLabel(c)}</button>)}</div></section>}
      {product.sizes?.length>0 && <section className="bs-variant-section"><div className="bs-variant-label"><h2>O‘lcham</h2><span>{size || 'Tanlang'}</span></div><div className="bs-option-list bs-sizes">{product.sizes.map(s=><button key={s} disabled={!variantAvailable(color,s)} className={size===s?'is-selected':''} onClick={()=>{setSize(s);setError('');setAdded(false);haptic.selection();}} aria-pressed={size===s}>{s}</button>)}</div></section>}
      <div className="bs-quantity-line"><span>Miqdor</span><div className="bs-quantity"><button onClick={()=>{setQty(Math.max(1,qty-1));setAdded(false);}} disabled={qty<=1} aria-label="Miqdorni kamaytirish"><Minus size={16}/></button><b>{qty}</b><button onClick={()=>{setQty(Math.min(99,qty+1));setAdded(false);}} disabled={qty>=99} aria-label="Miqdorni oshirish"><Plus size={16}/></button></div></div>
      <div className="bs-cargo-note"><span><Package size={21} strokeWidth={1.5}/></span><div><strong>Buyurtma asosida olib kelinadi</strong><p>Kargo haqi tortilgandan keyin alohida hisoblanadi. Hozir faqat mahsulot uchun to‘laysiz.</p></div></div>
      {product.description && <section className="bs-description"><h2>Mahsulot tavsifi</h2><p>{product.description}</p></section>}
      {error && <p className="bs-inline-error" role="alert">{error}</p>}
    </div>
    <div className="bs-detail-footer"><div><small>{qty>1?`${qty} dona uchun`:'Mahsulot narxi'}</small><strong>{formatPrice(product.price*qty)}</strong></div><button onClick={added ? onGoToCart : handleAdd} disabled={isAddingToCart || !product.in_stock || product.is_demo || !variantAvailable(color,size)} className="bs-button">{added?<><Check size={18}/>Savatga o‘tish<ArrowRight size={16}/></>:<><ShoppingBag size={18}/>{product.is_demo?'Namuna mahsuloti':!product.in_stock?'Mavjud emas':isAddingToCart?'Qo‘shilmoqda...':'Savatga qo‘shish'}</>}</button></div>
  </div>;
};
