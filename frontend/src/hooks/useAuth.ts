/**
 * Session-authentication hooks (TanStack Query).
 *
 * The signed-in customer is itself a query, so every screen reads the
 * same cached value and a login or logout refreshes all of them at once.
 * Logging in or out also clears cached per-customer data (cart, orders,
 * reviews), so one customer never sees another customer's data.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError, getSession, login, logout, register } from "../api";
import type { LoginInput, RegisterInput, SessionResponse } from "../types";

export const authKeys = {
  session: () => ["auth", "session"] as const,
};

/** The current session: who is signed in, and whether they are staff. */
export function useSession() {
  const query = useQuery<SessionResponse, ApiError>({
    queryKey: authKeys.session(),
    queryFn: getSession,
    // The session is cheap and decides what the whole UI may show, so it
    // is kept fresh rather than served from a long-lived cache.
    staleTime: 0,
  });

  return {
    ...query,
    user: query.data?.user ?? null,
    isAuthenticated: Boolean(query.data?.authenticated),
    isStaff: Boolean(query.data?.user?.is_staff),
  };
}

function useSessionMutation<TVariables>(
  mutationFn: (variables: TVariables) => Promise<SessionResponse>,
) {
  const queryClient = useQueryClient();

  return useMutation<SessionResponse, ApiError, TVariables>({
    mutationFn,
    onSuccess: (data) => {
      queryClient.setQueryData(authKeys.session(), data);
      // Who the customer is changes what the cart, order history and
      // review ownership contain, so drop those caches.
      void queryClient.invalidateQueries({ queryKey: ["cart"] });
      void queryClient.invalidateQueries({ queryKey: ["orders"] });
      void queryClient.invalidateQueries({ queryKey: ["reviews"] });
      void queryClient.invalidateQueries({ queryKey: ["admin"] });
    },
  });
}

export function useLogin() {
  return useSessionMutation((input: LoginInput) => login(input));
}

export function useRegister() {
  return useSessionMutation((input: RegisterInput) => register(input));
}

export function useLogout() {
  return useSessionMutation(() => logout());
}