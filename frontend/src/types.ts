/** Shared types for the Django API responses. */

export interface BookSummary {
  id: number;
  title: string;
  author: string;
  isbn: string;
  category: string;
  price: string;
  stock_quantity: number;
  in_stock: boolean;
  cover_image_url: string;
}

export interface BookDetail extends BookSummary {
  description: string;
  publisher: string;
  publication_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface BookListResponse {
  count: number;
  books: BookSummary[];
}

export interface CategoriesResponse {
  categories: string[];
}

export interface BookResponse {
  book: BookDetail;
}

export interface CartItem {
  id: number;
  book: BookSummary;
  quantity: number;
  subtotal: string;
}

export interface Cart {
  items: CartItem[];
  total: string;
  item_count: number;
}

export interface CartResponse {
  cart: Cart;
}

export interface OrderItem {
  id: number;
  book_id: number;
  title: string;
  unit_price: string;
  quantity: number;
  line_total: string;
}

export type OrderStatus = "PENDING" | "CONFIRMED";

export interface Order {
  id: number;
  status: OrderStatus;
  is_confirmed: boolean;
  total_amount: string;
  item_count: number;
  items: OrderItem[];
  created_at: string;
}

export interface OrderSummary {
  id: number;
  status: OrderStatus;
  is_confirmed: boolean;
  total_amount: string;
  item_count: number;
  created_at: string;
}

export interface OrderResponse {
  order: Order;
}

export interface OrderListResponse {
  count: number;
  orders: OrderSummary[];
}

export interface AvailabilityProblem {
  book_id: number | null;
  title: string;
  requested: number;
  available: number;
  reason: string;
}

export interface AvailabilityResponse {
  available: boolean;
  problems: AvailabilityProblem[];
}

export type PaymentStatus = "SUCCEEDED" | "FAILED";

export interface Payment {
  id: number;
  order_id: number;
  amount: string;
  method: string;
  status: PaymentStatus;
  card_last4: string;
  created_at: string;
  reference?: string;
  failure_reason?: string;
}

export interface PaymentResponse {
  order: Order;
  payment: Payment;
}

export interface CardPaymentInput {
  order_id: number;
  card_number: string;
  cvc: string;
  expiry_month: number;
  expiry_year: number;
}

export interface BookFilters {
  q?: string;
  category?: string;
  author?: string;
  min_price?: string;
  max_price?: string;
  available?: string;
}
