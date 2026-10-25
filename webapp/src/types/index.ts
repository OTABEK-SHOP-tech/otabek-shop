export interface Product {
  is_demo?: boolean;
  id: number;
  title: string;
  name?: string;
  description: string;
  price: number;
  formatted_price: string;
  old_price?: number | null;
  formatted_old_price?: string | null;
  discount_percent?: number | null;
  category_id: number;
  category_name: string;
  photos: string[];
  colors: string[];
  sizes: string[];
  in_stock: boolean;
  is_new: boolean;
  is_hit: boolean;
  views: number;
}

export interface Category {
  id: number;
  name: string;
  emoji: string;
  sort_order: number;
  product_count: number;
}

export interface CartItem {
  id: number;
  product_id: number;
  product_title: string;
  product_price: number;
  formatted_price: string;
  product_photo?: string | null;
  color?: string | null;
  size?: string | null;
  qty: number;
  item_total: number;
  formatted_item_total: string;
}

export interface CartSummary {
  items: CartItem[];
  total_items: number;
  subtotal: number;
  formatted_subtotal: string;
  grand_total: number;
  formatted_grand_total: string;
}

export interface OrderItem {
  product_id: number;
  title: string;
  price: number;
  color?: string;
  size?: string;
  qty: number;
  photo?: string;
}

export interface Order {
  id: number;
  user_id: number;
  customer_name: string;
  customer_username?: string | null;
  phone: string;
  city: string;
  address: string;
  items: OrderItem[];
  total: number;
  formatted_total: string;
  status: string;
  status_label: string;
  selected_card?: string | null;
  receipt_url?: string | null;
  receipt_uploaded_at?: string | null;
  reject_reason?: string | null;
  cargo_price?: number | null;
  formatted_cargo_price?: string | null;
  cargo_status?: string | null;
  cargo_weight?: number | null;
  created_at: string;
}

export interface UserProfile {
  telegram_id: number;
  name: string;
  username?: string | null;
  phone?: string | null;
  saved_city?: string | null;
  saved_address?: string | null;
  orders_count: number;
  is_admin: boolean;
}

export interface ShopSettings {
  contact_username: string;
  delivery_text: string;
  channel_username: string;
  payment_card_1: string;
  payment_card_2: string;
  cargo_info: string;
}

export type TabType = 'home' | 'catalog' | 'cart' | 'profile';
