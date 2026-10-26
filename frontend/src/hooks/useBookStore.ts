/**
 * TanStack Query hooks for the Online Book Store API.
 *
 * Every server interaction in the app goes through these hooks: queries
 * for reads (with shared cache keys) and mutations for writes (which
 * invalidate the affected queries so all screens stay in sync).
 */
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  ApiError,
  addToCart,
  cancelOrder,
  getBook,
  getBooks,
  getCart,
  getCartAvailability,
  getCategories,
  getOrder,
  getOrders,
  payOrder,
  placeOrder,
  removeCartItem,
  updateCartItem,
} from "../api";
import type {
  AvailabilityResponse,
  BookFilters,
  BookListResponse,
  BookResponse,
  CartResponse,
  CategoriesResponse,
  OrderListResponse,
  OrderResponse,
  PaymentResponse,
} from "../types";

export const queryKeys = {
  books: (filters: BookFilters) => ["books", filters] as const,
  book: (bookId: string | number) => ["books", "detail", bookId] as const,
  categories: () => ["books", "categories"] as const,
  cart: () => ["cart"] as const,
  availability: () => ["cart", "availability"] as const,
  orders: () => ["orders"] as const,
  order: (orderId: string | number) => ["orders", orderId] as const,
};

/** Catalogue with search/filter parameters. */
export function useBooks(filters: BookFilters = {}) {
  return useQuery<BookListResponse, ApiError>({
    queryKey: queryKeys.books(filters),
    queryFn: () => getBooks(filters),
  });
}

/** Single book details page. */
export function useBook(bookId: string | number | undefined) {
  return useQuery<BookResponse, ApiError>({
    queryKey: queryKeys.book(bookId ?? ""),
    queryFn: () => getBook(bookId as string | number),
    enabled: bookId !== undefined,
    retry: (failureCount, error) => {
      if (error.status === 404) {
        return false;
      }
      return failureCount < 2;
    },
  });
}

/** Distinct categories for the catalogue filter. */
export function useCategories() {
  return useQuery<CategoriesResponse, ApiError>({
    queryKey: queryKeys.categories(),
    queryFn: getCategories,
  });
}

/** The current session's shopping cart. */
export function useCart() {
  return useQuery<CartResponse, ApiError>({
    queryKey: queryKeys.cart(),
    queryFn: getCart,
  });
}

/** Availability pre-check for the current cart (checkout page). */
export function useCartAvailability(enabled = true) {
  return useQuery<AvailabilityResponse, ApiError>({
    queryKey: queryKeys.availability(),
    queryFn: getCartAvailability,
    enabled,
  });
}

/** The customer's order history (issue #10). */
export function useOrders() {
  return useQuery<OrderListResponse, ApiError>({
    queryKey: queryKeys.orders(),
    queryFn: getOrders,
  });
}

/** A single order by id (confirmation page). */
export function useOrder(orderId: string | number | undefined) {
  return useQuery<OrderResponse, ApiError>({
    queryKey: queryKeys.order(orderId ?? ""),
    queryFn: () => getOrder(orderId as string | number),
    enabled: orderId !== undefined,
  });
}

function useCartMutation<TVariables>(
  mutationFn: (variables: TVariables) => Promise<CartResponse>,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn,
    onSuccess: (data) => {
      // The API returns the updated cart; seed the cache with it and
      // refresh the derived availability check.
      queryClient.setQueryData(queryKeys.cart(), data);
      void queryClient.invalidateQueries({
        queryKey: queryKeys.availability(),
      });
    },
  });
}

export function useAddToCart() {
  return useCartMutation(({ bookId, quantity }: { bookId: number; quantity?: number }) =>
    addToCart(bookId, quantity ?? 1),
  );
}

export function useUpdateCartItem() {
  return useCartMutation(({ itemId, quantity }: { itemId: number; quantity: number }) =>
    updateCartItem(itemId, quantity),
  );
}

export function useRemoveCartItem() {
  return useCartMutation((itemId: number) => removeCartItem(itemId));
}

/** Places an order from the current cart (issue #8). */
export function usePlaceOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: placeOrder,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.orders() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.availability() });
    },
  });
}

/**
 * Pays a placed order (issue #9). On success the order is confirmed,
 * stock is reserved server-side and the cart is emptied.
 */
export function usePayOrder() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: payOrder,
    onSuccess: (data: PaymentResponse) => {
      queryClient.setQueryData(queryKeys.order(data.order.id), {
        order: data.order,
      } satisfies OrderResponse);
      queryClient.setQueryData(queryKeys.cart(), {
        cart: { items: [], total: "0.00", item_count: 0 },
      } satisfies CartResponse);
      void queryClient.invalidateQueries({ queryKey: queryKeys.orders() });
    },
  });
}


/**
 * Cancels one of the customer's own orders (issue #10).
 *
 * The server decides whether the order is still eligible, so a refused
 * cancellation surfaces as an ApiError with status 409 and the order's
 * current state.
 */
export function useCancelOrder() {
  const queryClient = useQueryClient();

  return useMutation<
    OrderResponse,
    ApiError,
    { orderId: number; reason?: string }
  >({
    mutationFn: ({ orderId, reason }) => cancelOrder(orderId, reason ?? ""),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.order(data.order.id), data);
      void queryClient.invalidateQueries({ queryKey: queryKeys.orders() });
      // A cancelled paid order returns its stock to the catalogue.
      void queryClient.invalidateQueries({ queryKey: ["books"] });
    },
  });
}
