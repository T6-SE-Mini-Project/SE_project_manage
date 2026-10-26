import { API_BASE_URL } from "./config";
import type {
  AdminBookFilters,
  AdminBookListResponse,
  AdminBookResponse,
  AdminOrderDetailResponse,
  AdminOrderFilters,
  AdminOrderListResponse,
  AdminOrderSummaryResponse,
  AvailabilityResponse,
  BackupListResponse,
  BookFilters,
  BookInput,
  BookListResponse,
  BookResponse,
  CartResponse,
  CategoriesResponse,
  CardPaymentInput,
  CustomerDetailResponse,
  CustomerListResponse,
  CustomerResponse,
  LoginInput,
  OrderListResponse,
  OrderResponse,
  OrderStatus,
  PaymentResponse,
  RegisterInput,
  ReviewInput,
  ReviewListResponse,
  ReviewResponse,
  SalesReportFilters,
  SalesReportResponse,
  SessionResponse,
} from "./types";

/** Error thrown by every failed API call, carrying the HTTP status. */
export class ApiError extends Error {
  status: number;
  body: Record<string, unknown>;

  constructor(message: string, status: number, body: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function readCookie(name: string): string {
  const match = document.cookie.match(
    new RegExp(`(^|;\\s*)${name}=([^;]*)`),
  );
  return match ? decodeURIComponent(match[2]) : "";
}

let csrfPromise: Promise<string> | null = null;

async function ensureCsrfToken(): Promise<string> {
  const existing = readCookie("csrftoken");
  if (existing) {
    return existing;
  }

  if (!csrfPromise) {
    csrfPromise = fetch(`${API_BASE_URL}/csrf/`, {
      credentials: "same-origin",
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("Unable to initialize a secure session.");
        }
        const data = await response.json();
        return data.csrfToken || readCookie("csrftoken");
      })
      .finally(() => {
        csrfPromise = null;
      });
  }

  const token = await csrfPromise;
  if (!token) {
    throw new Error("The request token could not be initialized.");
  }
  return token;
}

async function request<T>(
  path: string,
  { method = "GET", body, headers = {} }: {
    method?: string;
    body?: unknown;
    headers?: Record<string, string>;
  } = {},
): Promise<T> {
  const options: RequestInit = {
    method,
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...headers,
    },
  };

  if (body !== undefined) {
    options.headers = {
      ...options.headers,
      "Content-Type": "application/json",
    };
    options.body = JSON.stringify(body);
  }

  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    options.headers = {
      ...options.headers,
      "X-CSRFToken": await ensureCsrfToken(),
    };
  }

  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const bodyRecord = (data ?? {}) as Record<string, unknown>;
    const message =
      typeof bodyRecord.error === "string"
        ? bodyRecord.error
        : `Request failed (${response.status}).`;
    throw new ApiError(message, response.status, bodyRecord);
  }

  return data as T;
}

function queryString(filters: Record<string, string | undefined>): string {
  const params = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    params.set(key, value);
  });

  const query = params.toString();
  return query ? `?${query}` : "";
}

export function getBooks(filters: BookFilters = {}): Promise<BookListResponse> {
  return request(`/books/${queryString(filters)}`);
}

export function getCategories(): Promise<CategoriesResponse> {
  return request("/books/categories/");
}

export function getBook(bookId: string | number): Promise<BookResponse> {
  return request(`/books/${bookId}/`);
}

export function getCart(): Promise<CartResponse> {
  return request("/cart/");
}

export function addToCart(
  bookId: number,
  quantity = 1,
): Promise<CartResponse> {
  return request("/cart/items/", {
    method: "POST",
    body: { book_id: bookId, quantity },
  });
}

export function updateCartItem(
  itemId: number,
  quantity: number,
): Promise<CartResponse> {
  return request(`/cart/items/${itemId}/`, {
    method: "PATCH",
    body: { quantity },
  });
}

export function removeCartItem(itemId: number): Promise<CartResponse> {
  return request(`/cart/items/${itemId}/`, {
    method: "DELETE",
  });
}

export function getCartAvailability(): Promise<AvailabilityResponse> {
  return request("/orders/availability/");
}

export function placeOrder(): Promise<OrderResponse> {
  return request("/orders/", { method: "POST" });
}

export function getOrders(): Promise<OrderListResponse> {
  return request("/orders/");
}

export function getOrder(orderId: string | number): Promise<OrderResponse> {
  return request(`/orders/${orderId}/`);
}

export function payOrder(input: CardPaymentInput): Promise<PaymentResponse> {
  return request("/payments/", { method: "POST", body: input });
}


/* --- Accounts (session authentication) ------------------------------- */

export function getSession(): Promise<SessionResponse> {
  return request("/auth/session/");
}

export function login(input: LoginInput): Promise<SessionResponse> {
  return request("/auth/login/", { method: "POST", body: input });
}

export function logout(): Promise<SessionResponse> {
  return request("/auth/logout/", { method: "POST", body: {} });
}

export function register(input: RegisterInput): Promise<SessionResponse> {
  return request("/auth/register/", { method: "POST", body: input });
}

/* --- Orders (issue #10) ---------------------------------------------- */

export function cancelOrder(
  orderId: number,
  reason = "",
): Promise<OrderResponse> {
  return request(`/orders/${orderId}/cancel/`, {
    method: "POST",
    body: { reason },
  });
}

/* --- Reviews (issue #11) --------------------------------------------- */

export function getReviews(
  bookId: string | number,
): Promise<ReviewListResponse> {
  return request(`/reviews/${queryString({ book: String(bookId) })}`);
}

export function createReview(
  bookId: number,
  input: ReviewInput,
): Promise<ReviewResponse> {
  return request("/reviews/", {
    method: "POST",
    body: { book_id: bookId, ...input },
  });
}

export function updateReview(
  reviewId: number,
  input: Partial<ReviewInput>,
): Promise<ReviewResponse> {
  return request(`/reviews/${reviewId}/`, {
    method: "PATCH",
    body: input,
  });
}

export function deleteReview(
  reviewId: number,
): Promise<{ summary: ReviewListResponse["summary"] }> {
  return request(`/reviews/${reviewId}/`, { method: "DELETE" });
}

/* --- Administrator catalogue (issue #12) ----------------------------- */

export function getAdminBooks(
  filters: AdminBookFilters = {},
): Promise<AdminBookListResponse> {
  return request(`/admin/books/${queryString(filters)}`);
}

export function createAdminBook(
  input: BookInput,
): Promise<AdminBookResponse> {
  return request("/admin/books/", { method: "POST", body: input });
}

export function updateAdminBook(
  bookId: number,
  input: Partial<BookInput>,
): Promise<AdminBookResponse> {
  return request(`/admin/books/${bookId}/`, {
    method: "PATCH",
    body: input,
  });
}

export function deleteAdminBook(
  bookId: number,
): Promise<{ deleted: boolean; id: number }> {
  return request(`/admin/books/${bookId}/`, { method: "DELETE" });
}

/* --- Administrator orders (issue #12) -------------------------------- */

export function getAdminOrders(
  filters: AdminOrderFilters = {},
): Promise<AdminOrderListResponse> {
  return request(`/admin/orders/${queryString(filters)}`);
}

export function getAdminOrder(
  orderId: string | number,
): Promise<AdminOrderDetailResponse> {
  return request(`/admin/orders/${orderId}/`);
}

export function setAdminOrderStatus(
  orderId: number,
  status: OrderStatus,
): Promise<AdminOrderSummaryResponse> {
  return request(`/admin/orders/${orderId}/status/`, {
    method: "POST",
    body: { status },
  });
}

export function cancelAdminOrder(
  orderId: number,
  reason = "",
): Promise<AdminOrderSummaryResponse> {
  return request(`/admin/orders/${orderId}/cancel/`, {
    method: "POST",
    body: { reason },
  });
}

/* --- Administrator customers and reports (issue #24) ----------------- */

export function getCustomers(
  filters: { q?: string; status?: string } = {},
): Promise<CustomerListResponse> {
  return request(`/admin/customers/${queryString(filters)}`);
}

export function getCustomer(
  customerId: string | number,
): Promise<CustomerDetailResponse> {
  return request(`/admin/customers/${customerId}/`);
}

export function setCustomerActive(
  customerId: number,
  isActive: boolean,
): Promise<CustomerResponse> {
  return request(`/admin/customers/${customerId}/status/`, {
    method: "POST",
    body: { is_active: isActive },
  });
}

export function getSalesReport(
  filters: SalesReportFilters = {},
): Promise<SalesReportResponse> {
  return request(`/admin/reports/sales/${queryString(filters)}`);
}

/* --- Backups (issue #18) --------------------------------------------- */

export function getBackups(): Promise<BackupListResponse> {
  return request("/admin/backups/");
}
