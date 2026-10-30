import { API_BASE_URL } from "./config";
import { currentIdToken } from "./firebase";
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
  OrderListResponse,
  OrderResponse,
  OrderStatus,
  PaymentResponse,
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

/**
 * Whether a failed request is worth retrying.
 *
 * A 4xx will not become a 2xx by being asked again: the request is wrong,
 * the caller is not allowed, or — for `429` — they have already made too
 * many, and a retry spends the next window's allowance as well. Network
 * failures and 5xx are worth one more attempt.
 */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (error instanceof ApiError && error.status < 500) {
    return false;
  }
  return failureCount < 1;
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
  // Who the caller is comes from the Firebase ID token, on every request:
  // the backend's middleware verifies it and resolves the account. The
  // session cookie still rides along (credentials: "same-origin") because
  // it keys a *guest* cart, but it no longer authenticates anybody.
  const token = await currentIdToken();

  const options: RequestInit = {
    method,
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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


/* --- Accounts (Firebase authentication) ------------------------------ */

/** The login check: who the current ID token identifies, if anybody. */
export function getSession(): Promise<SessionResponse> {
  return request("/auth/session/");
}

/**
 * Registers a Firebase sign-in with the API.
 *
 * Called once, straight after the Firebase SDK reports a successful
 * sign-in. It links the Firebase uid to a customer account (creating one
 * on a first sign-in) and hands over anything done as a guest in this
 * browser: the cart, and any order placed before signing in.
 */
export function syncSession(): Promise<SessionResponse> {
  return request("/auth/signin/", { method: "POST", body: {} });
}

/**
 * Ends the browser session that keyed the guest cart.
 *
 * Signing out of Firebase happens in the browser; that is what stops the
 * ID token being sent. This tells the API to forget the session, so the
 * next person on this browser does not inherit the cart.
 */
export function endSession(): Promise<SessionResponse> {
  return request("/auth/logout/", { method: "POST", body: {} });
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
