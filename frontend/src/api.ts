import { API_BASE_URL } from "./config";
import type {
  AvailabilityResponse,
  BookFilters,
  BookListResponse,
  BookResponse,
  CartResponse,
  CategoriesResponse,
  CardPaymentInput,
  OrderListResponse,
  OrderResponse,
  PaymentResponse,
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
  return request(
    `/books/${queryString(
      filters as unknown as Record<string, string | undefined>,
    )}`,
  );
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
