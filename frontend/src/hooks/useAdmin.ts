/**
 * Administrator hooks (issues #12, #18 and #24).
 *
 * Every hook here talks to /api/admin/, which the server gates on
 * is_staff. The UI hides these screens from customers, but that is
 * convenience only: authorization is enforced per request on the server.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  cancelAdminOrder,
  createAdminBook,
  deleteAdminBook,
  getAdminBooks,
  getAdminOrder,
  getAdminOrders,
  getBackups,
  getCustomer,
  getCustomers,
  getSalesReport,
  setAdminOrderStatus,
  setCustomerActive,
  updateAdminBook,
} from "../api";
import type {
  AdminBookFilters,
  AdminBookListResponse,
  AdminOrderDetailResponse,
  AdminOrderFilters,
  AdminOrderListResponse,
  BackupListResponse,
  BookInput,
  CustomerDetailResponse,
  CustomerListResponse,
  OrderStatus,
  SalesReportFilters,
  SalesReportResponse,
} from "../types";

export const adminKeys = {
  all: ["admin"] as const,
  books: (filters: AdminBookFilters) => ["admin", "books", filters] as const,
  orders: (filters: AdminOrderFilters) =>
    ["admin", "orders", filters] as const,
  order: (orderId: string | number) =>
    ["admin", "orders", "detail", String(orderId)] as const,
  customers: (filters: { q?: string; status?: string }) =>
    ["admin", "customers", filters] as const,
  customer: (customerId: string | number) =>
    ["admin", "customers", "detail", String(customerId)] as const,
  report: (filters: SalesReportFilters) =>
    ["admin", "reports", "sales", filters] as const,
  backups: () => ["admin", "backups"] as const,
};

/* --- Catalogue management (issue #12) -------------------------------- */

export function useAdminBooks(filters: AdminBookFilters = {}) {
  return useQuery<AdminBookListResponse, ApiError>({
    queryKey: adminKeys.books(filters),
    queryFn: () => getAdminBooks(filters),
  });
}

/** Invalidates the catalogue everywhere, including the customer-facing pages. */
function useCatalogueInvalidation() {
  const queryClient = useQueryClient();

  return () => {
    void queryClient.invalidateQueries({ queryKey: ["admin", "books"] });
    // A catalogue edit changes what customers see, so drop their caches
    // for the book list, book details and categories too.
    void queryClient.invalidateQueries({ queryKey: ["books"] });
  };
}

export function useCreateBook() {
  const invalidate = useCatalogueInvalidation();

  return useMutation<unknown, ApiError, BookInput>({
    mutationFn: (input) => createAdminBook(input),
    onSuccess: invalidate,
  });
}

export function useUpdateBook() {
  const invalidate = useCatalogueInvalidation();

  return useMutation<
    unknown,
    ApiError,
    { bookId: number; input: Partial<BookInput> }
  >({
    mutationFn: ({ bookId, input }) => updateAdminBook(bookId, input),
    onSuccess: invalidate,
  });
}

export function useDeleteBook() {
  const invalidate = useCatalogueInvalidation();

  return useMutation<unknown, ApiError, number>({
    mutationFn: (bookId) => deleteAdminBook(bookId),
    onSuccess: invalidate,
  });
}

/* --- Order management (issue #12) ------------------------------------ */

export function useAdminOrders(filters: AdminOrderFilters = {}) {
  return useQuery<AdminOrderListResponse, ApiError>({
    queryKey: adminKeys.orders(filters),
    queryFn: () => getAdminOrders(filters),
  });
}

export function useAdminOrder(orderId: string | number | undefined) {
  return useQuery<AdminOrderDetailResponse, ApiError>({
    queryKey: adminKeys.order(orderId ?? ""),
    queryFn: () => getAdminOrder(orderId as string | number),
    enabled: orderId !== undefined,
  });
}

/** Invalidates every view of an order after an administrator changes it. */
function useOrderInvalidation() {
  const queryClient = useQueryClient();

  return () => {
    void queryClient.invalidateQueries({ queryKey: ["admin", "orders"] });
    void queryClient.invalidateQueries({ queryKey: ["admin", "reports"] });
    void queryClient.invalidateQueries({ queryKey: ["admin", "customers"] });
    // The customer's own order history reflects the same change.
    void queryClient.invalidateQueries({ queryKey: ["orders"] });
    // Cancelling returns stock to the catalogue.
    void queryClient.invalidateQueries({ queryKey: ["books"] });
  };
}

export function useSetOrderStatus() {
  const invalidate = useOrderInvalidation();

  return useMutation<
    unknown,
    ApiError,
    { orderId: number; status: OrderStatus }
  >({
    mutationFn: ({ orderId, status }) => setAdminOrderStatus(orderId, status),
    onSuccess: invalidate,
  });
}

export function useAdminCancelOrder() {
  const invalidate = useOrderInvalidation();

  return useMutation<unknown, ApiError, { orderId: number; reason?: string }>({
    mutationFn: ({ orderId, reason }) => cancelAdminOrder(orderId, reason ?? ""),
    onSuccess: invalidate,
  });
}

/* --- Customer management (issue #24) --------------------------------- */

export function useCustomers(filters: { q?: string; status?: string } = {}) {
  return useQuery<CustomerListResponse, ApiError>({
    queryKey: adminKeys.customers(filters),
    queryFn: () => getCustomers(filters),
  });
}

export function useCustomer(customerId: string | number | undefined) {
  return useQuery<CustomerDetailResponse, ApiError>({
    queryKey: adminKeys.customer(customerId ?? ""),
    queryFn: () => getCustomer(customerId as string | number),
    enabled: customerId !== undefined,
  });
}

export function useSetCustomerActive() {
  const queryClient = useQueryClient();

  return useMutation<
    unknown,
    ApiError,
    { customerId: number; isActive: boolean }
  >({
    mutationFn: ({ customerId, isActive }) =>
      setCustomerActive(customerId, isActive),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["admin", "customers"],
      });
    },
  });
}

/* --- Sales reports (issue #24) and backups (issue #18) --------------- */

export function useSalesReport(filters: SalesReportFilters = {}) {
  return useQuery<SalesReportResponse, ApiError>({
    queryKey: adminKeys.report(filters),
    queryFn: () => getSalesReport(filters),
  });
}

export function useBackups() {
  return useQuery<BackupListResponse, ApiError>({
    queryKey: adminKeys.backups(),
    queryFn: getBackups,
  });
}
