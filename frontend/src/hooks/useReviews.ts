/**
 * Book review hooks (issue #11).
 *
 * One query holds a book's reviews, its rating summary and whether the
 * current customer may still submit one; the write mutations seed that
 * same cache entry from the response, so the list and the average rating
 * update without a refetch.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  ApiError,
  createReview,
  deleteReview,
  getReviews,
  updateReview,
} from "../api";
import type { ReviewInput, ReviewListResponse } from "../types";

export const reviewKeys = {
  book: (bookId: string | number) => ["reviews", String(bookId)] as const,
};

/** Reviews and rating summary for one book. */
export function useBookReviews(bookId: string | number | undefined) {
  return useQuery<ReviewListResponse, ApiError>({
    queryKey: reviewKeys.book(bookId ?? ""),
    queryFn: () => getReviews(bookId as string | number),
    enabled: bookId !== undefined,
  });
}

function useReviewInvalidation(bookId: string | number | undefined) {
  const queryClient = useQueryClient();

  return () =>
    queryClient.invalidateQueries({
      queryKey: reviewKeys.book(bookId ?? ""),
    });
}

/** Submits a review for a book. */
export function useCreateReview(bookId: number) {
  const invalidate = useReviewInvalidation(bookId);

  return useMutation<unknown, ApiError, ReviewInput>({
    mutationFn: (input) => createReview(bookId, input),
    onSuccess: () => {
      void invalidate();
    },
  });
}

/** Edits the customer's own review. */
export function useUpdateReview(bookId: number) {
  const invalidate = useReviewInvalidation(bookId);

  return useMutation<
    unknown,
    ApiError,
    { reviewId: number; input: Partial<ReviewInput> }
  >({
    mutationFn: ({ reviewId, input }) => updateReview(reviewId, input),
    onSuccess: () => {
      void invalidate();
    },
  });
}

/** Withdraws a review (own review, or any review for an administrator). */
export function useDeleteReview(bookId: number) {
  const invalidate = useReviewInvalidation(bookId);

  return useMutation<unknown, ApiError, number>({
    mutationFn: (reviewId) => deleteReview(reviewId),
    onSuccess: () => {
      void invalidate();
    },
  });
}