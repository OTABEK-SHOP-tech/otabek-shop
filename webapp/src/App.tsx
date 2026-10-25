import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, WifiOff } from 'lucide-react';
import { Header } from './components/Header';
import { BottomNav } from './components/BottomNav';
import { HomePage } from './pages/HomePage';
import { CatalogPage } from './pages/CatalogPage';
import { ProductDetailPage } from './pages/ProductDetailPage';
import { BagPage } from './pages/BagPage';
import { ProfilePage } from './pages/ProfilePage';
import { Category, Product, CartSummary, Order, ShopSettings, TabType, UserProfile } from './types';
import { api } from './utils/api';
import { initTelegramApp, haptic, getTelegramInitData, openTelegramLink } from './utils/telegram';

const emptyCart: CartSummary = { items: [], total_items: 0, subtotal: 0, formatted_subtotal: '0 so‘m', grand_total: 0, formatted_grand_total: '0 so‘m' };
export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('home');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [cart, setCart] = useState<CartSummary>(emptyCart);
  const [orders, setOrders] = useState<Order[]>([]);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [settings, setSettings] = useState<ShopSettings | null>(null);
  const [activePaymentOrder, setActivePaymentOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [isAddingToCart, setIsAddingToCart] = useState(false);
  const [toast, setToast] = useState('');
  const [wishlistOnly, setWishlistOnly] = useState(false);
  const [wishlistIds, setWishlistIds] = useState<number[]>(() => {
    try { const saved = JSON.parse(localStorage.getItem('bek_wishlist') || '[]'); return Array.isArray(saved) ? saved.filter(x => typeof x === 'number') : []; } catch { return []; }
  });
  const authenticated = Boolean(getTelegramInitData());
  const closeProduct = useCallback(() => setSelectedProduct(null), []);
  useEffect(() => { initTelegramApp(); }, []);
  useEffect(() => { if (!toast) return; const timer = window.setTimeout(() => setToast(''), 6000); return () => clearTimeout(timer); }, [toast]);
  useEffect(() => { window.scrollTo(0,0); }, [activeTab]);
  const toggleWishlist = (id: number) => setWishlistIds(prev => {
    const next = prev.includes(id) ? prev.filter(x => x !== id) : [...prev,id];
    try { localStorage.setItem('bek_wishlist', JSON.stringify(next)); } catch { /* Storage may be unavailable in a private WebView. */ }
    return next;
  });
  const loadInitialData = useCallback(async () => {
    setLoading(true); setLoadError(false);
    try {
      const [prods,cats,config] = await Promise.all([api.get<Product[]>('/products'),api.get<Category[]>('/categories'),api.get<ShopSettings>('/settings')]);
      // One inherited demo photo depicts women's clothing; keep this men's storefront relevant.
      const visibleProducts = prods.filter(p => !(p.is_demo && p.photos?.some(photo => photo.includes('photo-1578587018452-892bacefd3f2'))));
      setProducts(visibleProducts); setCategories(cats.map(c => ({...c, product_count:visibleProducts.filter(p => p.category_id === c.id).length}))); setSettings(config);
      if (getTelegramInitData()) {
        const [basket,profile,myOrders] = await Promise.all([api.get<CartSummary>('/cart').catch(()=>emptyCart),api.get<UserProfile>('/user/profile').catch(()=>null),api.get<Order[]>('/orders/my').catch(()=>[])]);
        setCart(basket); setUser(profile); setOrders(myOrders);
      }
    } catch { setLoadError(true); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { loadInitialData(); }, [loadInitialData]);
  const handleAddToCart = async (product: Product, size: string|null, color: string|null, qty: number) => {
    if (!getTelegramInitData()) throw new Error('Buyurtma berish uchun do‘konni Telegram bot orqali oching.');
    setIsAddingToCart(true);
    try { setCart(await api.post<CartSummary>('/cart',{product_id:product.id,size,color,qty})); }
    finally { setIsAddingToCart(false); }
  };
  const handleUpdateQty = async (id:number,qty:number) => {
    try { setCart(await api.patch<CartSummary>(`/cart/${id}`,{qty})); } catch(e) { setToast(e instanceof Error ? e.message : 'Miqdor o‘zgartirilmadi.'); }
  };
  const handleRemoveItem = async (id:number) => {
    try { setCart(await api.delete<CartSummary>(`/cart/${id}`)); haptic.impact('light'); } catch { setToast('Mahsulot olib tashlanmadi. Qayta urinib ko‘ring.'); }
  };
  const handleClearCart = async () => {
    try { setCart(await api.delete<CartSummary>('/cart')); } catch { setToast('Savat tozalanmadi. Qayta urinib ko‘ring.'); }
  };
  const refreshOrders = () => { if (getTelegramInitData()) api.get<Order[]>('/orders/my').then(setOrders).catch(()=>setToast('Buyurtmalarni yangilab bo‘lmadi.')); };
  const submitOrder = async (data:{customer_name:string;phone:string;city:string;address:string}):Promise<Order> => {
    let checkoutKey = sessionStorage.getItem('bek_checkout_key');
    if (!checkoutKey) { checkoutKey = crypto.randomUUID(); sessionStorage.setItem('bek_checkout_key',checkoutKey); }
    const order = await api.post<Order>('/orders',data, {'Idempotency-Key':checkoutKey});
    sessionStorage.removeItem('bek_checkout_key');
    api.get<CartSummary>('/cart').then(setCart).catch(()=>{});
    api.get<Order[]>('/orders/my').then(setOrders).catch(()=>{});
    return order;
  };
  const goCatalog = () => { setWishlistOnly(false); setActiveTab('catalog'); };
  const showWishlist = () => { setWishlistOnly(true); setSelectedCategoryId(null); setSearchQuery(''); setSelectedProduct(null); setActiveTab('catalog'); };
  if (loading) return <div className="bs-loading"><span className="bs-wordmark">Bek <i>style.</i></span><span className="bs-loading-line"/><p className="bs-eyebrow">Do‘kon tayyorlanmoqda</p></div>;
  return <div className="bs-app">
    {!selectedProduct && <Header searchQuery={searchQuery} onSearchChange={q=>{setSearchQuery(q);setWishlistOnly(false);setActiveTab('catalog');}} onSearchClick={()=>setActiveTab('catalog')} onHomeClick={()=>{setSearchQuery('');setSelectedCategoryId(null);setActiveTab('home');}} onWishlistClick={showWishlist} wishlistCount={wishlistIds.length} showSearch={activeTab==='home'||activeTab==='catalog'}/>}
    <main className="bs-main">
      {loadError ? <div className="bs-load-error"><WifiOff size={34} className="mx-auto text-[#8b9e7a]"/><h2 className="mt-4 font-semibold">Do‘konni yuklab bo‘lmadi</h2><p>Internet aloqasini tekshirib, qayta urinib ko‘ring.</p><button className="bs-button" onClick={loadInitialData}><RefreshCw size={16}/> Qayta urinish</button></div> : selectedProduct ? <ProductDetailPage product={selectedProduct} onClose={closeProduct} onAddToCart={handleAddToCart} isAddingToCart={isAddingToCart} isWishlisted={wishlistIds.includes(selectedProduct.id)} onToggleWishlist={toggleWishlist} onGoToCart={()=>{setSelectedProduct(null);setActiveTab('cart');}}/> : <>
        {activeTab==='home' && <HomePage products={products} categories={categories} selectedCategoryId={selectedCategoryId} onSelectCategory={setSelectedCategoryId} onSelectProduct={setSelectedProduct} onGoToCatalog={goCatalog} wishlistIds={wishlistIds} onToggleWishlist={toggleWishlist}/>}
        {activeTab==='catalog' && <CatalogPage products={products} categories={categories} selectedCategoryId={selectedCategoryId} onSelectCategory={setSelectedCategoryId} onSelectProduct={setSelectedProduct} initialSearch={searchQuery} wishlistIds={wishlistIds} onToggleWishlist={toggleWishlist} wishlistOnly={wishlistOnly} onClearWishlistFilter={()=>{setWishlistOnly(false);setSearchQuery('');}}/>}
        {activeTab==='cart' && <BagPage cart={cart} onUpdateQty={handleUpdateQty} onRemoveItem={handleRemoveItem} onClearCart={handleClearCart} onSubmitOrder={submitOrder} onGoToCatalog={goCatalog} onGoToProfile={()=>{refreshOrders();setActiveTab('profile');}} defaultUserName={user?.name||''} settings={settings} activePaymentOrder={activePaymentOrder} onClearActivePaymentOrder={()=>setActivePaymentOrder(null)}/>}
        {activeTab==='profile' && <ProfilePage user={user} orders={orders} settings={settings} onRefreshOrders={refreshOrders} onGoToCatalog={goCatalog} onPayForOrder={o=>{setActivePaymentOrder(o);setActiveTab('cart');}}/>}
      </>}
    </main>
    {!selectedProduct && <BottomNav activeTab={activeTab} onTabChange={tab=>{haptic.selection();setActiveTab(tab);if(tab==='profile')refreshOrders();if(tab==='catalog')setWishlistOnly(false);}} cartCount={cart.total_items}/>}
    {toast && <div role="status" className="bs-toast"><span>{toast}</span><button onClick={()=>setToast('')}>Yopish</button></div>}
    {!authenticated && selectedProduct && <div className="bs-guest-link"><button onClick={()=>openTelegramLink('https://t.me/bek_styleee_bot')}>Telegramda do‘konni ochish <span>↗</span></button></div>}
  </div>;
};
export default App;
