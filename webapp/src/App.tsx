import React, { useState, useEffect, useCallback } from 'react';
import { Header } from './components/Header';
import { BottomNav } from './components/BottomNav';
import { HomePage } from './pages/HomePage';
import { CatalogPage } from './pages/CatalogPage';
import { ProductDetailPage } from './pages/ProductDetailPage';
import { BagPage } from './pages/BagPage';
import { ProfilePage } from './pages/ProfilePage';
import { Category, Product, CartSummary, Order, ShopSettings, TabType, UserProfile } from './types';
import { api } from './utils/api';
import { initTelegramApp, haptic } from './utils/telegram';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('home');
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selectedCategoryId, setSelectedCategoryId] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [cart, setCart] = useState<CartSummary>({
    items: [],
    total_items: 0,
    subtotal: 0,
    formatted_subtotal: "0 so'm",
    grand_total: 0,
    formatted_grand_total: "0 so'm",
  });
  const [orders, setOrders] = useState<Order[]>([]);
  const [user, setUser] = useState<UserProfile | null>(null);
  const [settings, setSettings] = useState<ShopSettings | null>(null);
  const [activePaymentOrder, setActivePaymentOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAddingToCart, setIsAddingToCart] = useState(false);

  // Initialize Telegram WebApp SDK
  useEffect(() => {
    initTelegramApp();
  }, []);

  // Fetch initial shop data
  const loadInitialData = useCallback(async () => {
    try {
      setLoading(true);
      const [prodsData, catsData, cartData, userData, settingsData] = await Promise.all([
        api.get<Product[]>('/products'),
        api.get<Category[]>('/categories'),
        api.get<CartSummary>('/cart').catch(() => ({
          items: [],
          total_items: 0,
          subtotal: 0,
          formatted_subtotal: "0 so'm",
          grand_total: 0,
          formatted_grand_total: "0 so'm",
        })),
        api.get<UserProfile>('/user/profile').catch(() => null),
        api.get<ShopSettings>('/settings').catch(() => null),
      ]);

      setProducts(prodsData || []);
      setCategories(catsData || []);
      if (cartData) setCart(cartData);
      if (userData) setUser(userData);
      if (settingsData) setSettings(settingsData);

      // Load user orders
      if (userData) {
        api.get<Order[]>('/orders/my').then(setOrders).catch(() => {});
      }
    } catch (err) {
      console.error('Failed to load shop data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Cart actions
  const handleAddToCart = async (
    product: Product,
    size: string | null,
    color: string | null,
    qty: number
  ) => {
    try {
      setIsAddingToCart(true);
      const updatedCart = await api.post<CartSummary>('/cart', {
        product_id: product.id,
        size,
        color,
        qty,
      });
      setCart(updatedCart);
      haptic.notification('success');
    } catch (err: any) {
      console.error('Add to cart failed:', err);
      haptic.notification('error');
    } finally {
      setIsAddingToCart(false);
    }
  };

  const handleUpdateQty = async (itemId: number, qty: number) => {
    try {
      const updatedCart = await api.patch<CartSummary>(`/cart/${itemId}`, { qty });
      setCart(updatedCart);
    } catch (err) {
      console.error('Update qty failed:', err);
    }
  };

  const handleRemoveItem = async (itemId: number) => {
    try {
      const updatedCart = await api.delete<CartSummary>(`/cart/${itemId}`);
      setCart(updatedCart);
      haptic.impact('light');
    } catch (err) {
      console.error('Remove item failed:', err);
    }
  };

  const handleClearCart = async () => {
    try {
      const updatedCart = await api.delete<CartSummary>('/cart');
      setCart(updatedCart);
    } catch (err) {
      console.error('Clear cart failed:', err);
    }
  };

  // Order submission
  const handleSubmitOrder = async (orderData: {
    customer_name: string;
    phone: string;
    city: string;
    address: string;
  }): Promise<Order> => {
    const newOrder = await api.post<Order>('/orders', orderData);
    // Reload cart and orders
    api.get<CartSummary>('/cart').then(setCart).catch(() => {});
    api.get<Order[]>('/orders/my').then(setOrders).catch(() => {});
    return newOrder;
  };

  const handleRefreshOrders = () => {
    api.get<Order[]>('/orders/my').then(setOrders).catch(() => {});
  };

  const handlePayForOrderFromProfile = (order: Order) => {
    setActivePaymentOrder(order);
    setActiveTab('cart');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#F8F9FA] flex flex-col items-center justify-center space-y-3">
        <div className="w-12 h-12 rounded-2xl bg-gray-900 text-white flex items-center justify-center font-extrabold text-sm tracking-wider shadow-md animate-pulse">
          BS
        </div>
        <p className="text-xs font-bold text-gray-500 tracking-wider uppercase">
          BEK STYLE yuklanmoqda...
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F8F9FA] text-gray-900 selection:bg-emerald-500 selection:text-white">
      {/* Top Header (only when not in product detail view) */}
      {!selectedProduct && (
        <Header
          searchQuery={searchQuery}
          onSearchChange={(q) => {
            setSearchQuery(q);
            if (activeTab !== 'catalog') {
              setActiveTab('catalog');
            }
          }}
          onSearchClick={() => {
            if (activeTab !== 'catalog') {
              setActiveTab('catalog');
            }
          }}
        />
      )}

      {/* Main Views */}
      <main className="max-w-lg mx-auto">
        {selectedProduct ? (
          <ProductDetailPage
            product={selectedProduct}
            onClose={() => setSelectedProduct(null)}
            onAddToCart={handleAddToCart}
            isAddingToCart={isAddingToCart}
          />
        ) : (
          <>
            {activeTab === 'home' && (
              <HomePage
                products={products}
                categories={categories}
                selectedCategoryId={selectedCategoryId}
                onSelectCategory={(catId) => {
                  setSelectedCategoryId(catId);
                }}
                onSelectProduct={setSelectedProduct}
                onGoToCatalog={() => setActiveTab('catalog')}
              />
            )}

            {activeTab === 'catalog' && (
              <CatalogPage
                products={products}
                categories={categories}
                selectedCategoryId={selectedCategoryId}
                onSelectCategory={setSelectedCategoryId}
                onSelectProduct={setSelectedProduct}
                initialSearch={searchQuery}
              />
            )}

            {activeTab === 'cart' && (
              <BagPage
                cart={cart}
                onUpdateQty={handleUpdateQty}
                onRemoveItem={handleRemoveItem}
                onClearCart={handleClearCart}
                onSubmitOrder={handleSubmitOrder}
                onGoToCatalog={() => setActiveTab('catalog')}
                onGoToProfile={() => setActiveTab('profile')}
                defaultUserName={user?.name || ''}
                settings={settings}
                activePaymentOrder={activePaymentOrder}
                onClearActivePaymentOrder={() => setActivePaymentOrder(null)}
              />
            )}

            {activeTab === 'profile' && (
              <ProfilePage
                user={user}
                orders={orders}
                settings={settings}
                onRefreshOrders={handleRefreshOrders}
                onGoToCatalog={() => setActiveTab('catalog')}
                onPayForOrder={handlePayForOrderFromProfile}
              />
            )}
          </>
        )}
      </main>

      {/* Persistent Bottom Nav (hidden during product detail view for maximum immersion) */}
      {!selectedProduct && (
        <BottomNav
          activeTab={activeTab}
          onTabChange={(tab) => {
            haptic.selection();
            setActiveTab(tab);
          }}
          cartCount={cart.total_items}
        />
      )}
    </div>
  );
};

export default App;
