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

export type OrderStatus =
  | "PENDING"
  | "CONFIRMED"
  | "PROCESSING"
  | "SHIPPED"
  | "DELIVERED"
  | "CANCELLED";

/** Cancellation and payment state shared by both order representations. */
export interface OrderLifecycle {
  status: OrderStatus;
  status_display: string;
  is_confirmed: boolean;
  is_paid: boolean;
  is_cancelled: boolean;
  is_cancellable: boolean;
  cancelled_at: string | null;
  cancellation_reason: string;
  refund_due: boolean;
}

export interface Order extends OrderLifecycle {
  id: number;
  total_amount: string;
  item_count: number;
  items: OrderItem[];
  created_at: string;
  paid_at: string | null;
}

export interface OrderCustomer {
  id: number;
  username: string;
  email: string;
}

/** Compact order row used by the administrator order list. */
export interface OrderSummary extends OrderLifecycle {
  id: number;
  total_amount: string;
  item_count: number;
  created_at: string;
  customer: OrderCustomer | null;
}

export interface OrderResponse {
  order: Order;
}

export interface OrderListResponse {
  count: number;
  orders: Order[];
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

export type BookFilters = {
  q?: string;
  category?: string;
  author?: string;
  min_price?: string;
  max_price?: string;
  available?: string;
};


/* --- Accounts (session authentication) ------------------------------- */

export interface User {
  id: number;
  username: string;
  email: string;
  is_staff: boolean;
  date_joined: string;
}

export interface SessionResponse {
  authenticated: boolean;
  user: User | null;
}

export interface LoginInput {
  username: string;
  password: string;
}

export interface RegisterInput {
  username: string;
  email: string;
  password1: string;
  password2: string;
}

/** Field-level errors returned by the form-backed endpoints. */
export type FieldErrors = Record<string, string[]>;

/* --- Reviews (issue #11) --------------------------------------------- */

export interface Review {
  id: number;
  book_id: number;
  rating: number;
  title: string;
  comment: string;
  author: string;
  is_owner: boolean;
  is_edited: boolean;
  created_at: string;
  updated_at: string;
}

export interface RatingSummary {
  book_id: number;
  review_count: number;
  /** One decimal place, or null when the book has no reviews yet. */
  average_rating: string | null;
  rating_counts: Record<string, number>;
}

export interface ReviewListResponse {
  summary: RatingSummary;
  reviews: Review[];
  can_review: boolean;
  my_review: Review | null;
}

export interface ReviewResponse {
  review: Review;
  summary: RatingSummary;
}

export interface ReviewInput {
  rating: number;
  title?: string;
  comment?: string;
}

/* --- Administrator API (issues #12, #18, #24) ------------------------ */

export interface BookInput {
  title: string;
  author: string;
  isbn: string;
  description: string;
  category: string;
  price: string;
  stock_quantity: number;
  cover_image_url: string;
  publisher: string;
  publication_date: string | null;
}

export interface AdminBookListResponse {
  count: number;
  books: BookDetail[];
}

export interface AdminBookResponse {
  book: BookDetail;
}

export type AdminBookFilters = {
  q?: string;
  category?: string;
  low_stock?: string;
};

export interface AdminOrderListResponse {
  count: number;
  limit: number;
  offset: number;
  orders: OrderSummary[];
  allowed_transitions: Partial<Record<OrderStatus, OrderStatus[]>>;
}

export type AdminOrderFilters = {
  status?: string;
  q?: string;
  limit?: string;
  offset?: string;
};

export interface OrderPayment {
  id: number;
  amount: string;
  status: PaymentStatus;
  method: string;
  reference: string;
  failure_reason: string;
  card_last4: string;
  created_at: string;
}

export interface AdminOrderDetail extends Order {
  customer: OrderCustomer | null;
  session_key: string;
  payments: OrderPayment[];
}

export interface AdminOrderDetailResponse {
  order: AdminOrderDetail;
}

export interface AdminOrderSummaryResponse {
  order: OrderSummary;
}

export interface Customer {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  is_staff: boolean;
  date_joined: string;
  last_login: string | null;
  order_count: number;
  cancelled_order_count: number;
  total_spent: string;
  last_order_at: string | null;
}

export interface CustomerListResponse {
  count: number;
  customers: Customer[];
}

export interface CustomerDetail extends Customer {
  orders: OrderSummary[];
}

export interface CustomerDetailResponse {
  customer: CustomerDetail;
}

export interface CustomerResponse {
  customer: Customer;
}

export interface SalesReport {
  period: { start: string | null; end: string | null };
  revenue: {
    total: string;
    order_count: number;
    average_order_value: string;
    items_sold: number;
    counted_statuses: OrderStatus[];
  };
  orders_by_status: Record<OrderStatus, number>;
  top_books: {
    book_id: number;
    title: string;
    quantity_sold: number;
    revenue: string;
  }[];
  daily: { date: string; order_count: number; revenue: string }[];
  generated_at: string;
}

export interface SalesReportResponse {
  report: SalesReport;
}

export type SalesReportFilters = {
  start?: string;
  end?: string;
};

export interface BackupRun {
  id: number;
  status: "SUCCESS" | "FAILED";
  trigger: "SCHEDULED" | "MANUAL";
  started_at: string;
  finished_at: string | null;
  duration_seconds: number | null;
  location: string;
  size_bytes: number;
  record_counts: Record<string, number>;
  total_records: number;
  error_message: string;
}

export interface BackupListResponse {
  freshness: {
    fresh: boolean;
    max_age_hours: number;
    age_hours: number | null;
    detail: string;
    latest: BackupRun | null;
  };
  runs: BackupRun[];
}
