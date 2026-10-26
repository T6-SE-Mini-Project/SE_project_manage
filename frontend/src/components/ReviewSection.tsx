/**
 * Reviews on the book details page (issue #11, OBS-F-016).
 *
 * Shows the aggregate rating, the submitted reviews, and — depending on
 * the session — the submission form, the customer's own review with edit
 * and delete controls, or a prompt to sign in.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import StarRating from "./StarRating";
import { useSession } from "../hooks/useAuth";
import {
  useBookReviews,
  useCreateReview,
  useDeleteReview,
  useUpdateReview,
} from "../hooks/useReviews";
import { errorMessage, fieldError, fieldErrors } from "../errors";
import { formatDateTime } from "../format";
import type { Review } from "../types";

interface ReviewSectionProps {
  bookId: number;
}

export default function ReviewSection({ bookId }: ReviewSectionProps) {
  const { isAuthenticated, isStaff } = useSession();
  const reviewsQuery = useBookReviews(bookId);

  const createMutation = useCreateReview(bookId);
  const updateMutation = useUpdateReview(bookId);
  const deleteMutation = useDeleteReview(bookId);

  const [rating, setRating] = useState(0);
  const [title, setTitle] = useState("");
  const [comment, setComment] = useState("");
  const [editing, setEditing] = useState(false);
  const [feedback, setFeedback] = useState("");

  const data = reviewsQuery.data;
  const myReview = data?.my_review ?? null;

  // When an edit starts, pre-fill the form with the stored review.
  useEffect(() => {
    if (editing && myReview) {
      setRating(myReview.rating);
      setTitle(myReview.title);
      setComment(myReview.comment);
    }
  }, [editing, myReview]);

  const activeMutation = editing ? updateMutation : createMutation;
  const errors = fieldErrors(activeMutation.error);
  const busy =
    createMutation.isPending ||
    updateMutation.isPending ||
    deleteMutation.isPending;

  function resetForm() {
    setRating(0);
    setTitle("");
    setComment("");
    setEditing(false);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFeedback("");

    const input = { rating, title, comment };

    try {
      if (editing && myReview) {
        await updateMutation.mutateAsync({
          reviewId: myReview.id,
          input,
        });
        setFeedback("Your review has been updated.");
      } else {
        await createMutation.mutateAsync(input);
        setFeedback("Thank you for your review.");
      }
      resetForm();
    } catch {
      // The error is rendered from the mutation's own state below.
    }
  }

  async function handleDelete(review: Review) {
    setFeedback("");

    try {
      await deleteMutation.mutateAsync(review.id);
      resetForm();
      setFeedback("The review has been removed.");
    } catch {
      // Rendered from the mutation state below.
    }
  }

  if (reviewsQuery.isPending) {
    return (
      <section className="reviews">
        <h2>Reviews</h2>
        <p className="muted">Loading reviews...</p>
      </section>
    );
  }

  if (reviewsQuery.isError || !data) {
    return (
      <section className="reviews">
        <h2>Reviews</h2>
        <p className="feedback error">
          {errorMessage(reviewsQuery.error, "Reviews could not be loaded.")}
        </p>
      </section>
    );
  }

  const { summary, reviews } = data;
  const showForm = editing || data.can_review;

  return (
    <section className="reviews">
      <header className="reviews-header">
        <h2>Reviews</h2>
        <div className="reviews-summary">
          <StarRating value={Number(summary.average_rating ?? 0)} />
          <p>
            {summary.review_count === 0
              ? "No reviews yet. Be the first to review this book."
              : `${summary.average_rating} out of 5 from ${
                  summary.review_count
                } review${summary.review_count === 1 ? "" : "s"}`}
          </p>
        </div>
      </header>

      {summary.review_count > 0 ? (
        <ul className="rating-breakdown">
          {[5, 4, 3, 2, 1].map((score) => {
            const count = summary.rating_counts[String(score)] ?? 0;
            const share = Math.round((count / summary.review_count) * 100);

            return (
              <li key={score}>
                <span className="rating-breakdown-label">{score} ★</span>
                <span className="rating-bar">
                  <span
                    className="rating-bar-fill"
                    style={{ width: `${share}%` }}
                  />
                </span>
                <span className="rating-breakdown-count">{count}</span>
              </li>
            );
          })}
        </ul>
      ) : null}

      {feedback ? (
        <p className="feedback success" role="status">
          {feedback}
        </p>
      ) : null}

      {activeMutation.isError ? (
        <p className="feedback error" role="alert">
          {errorMessage(
            activeMutation.error,
            "Your review could not be saved.",
          )}
        </p>
      ) : null}

      {!isAuthenticated ? (
        <p className="muted">
          <Link className="text-link" to="/login">
            Log in
          </Link>{" "}
          to write a review.
        </p>
      ) : null}

      {showForm ? (
        <form className="review-form" onSubmit={handleSubmit}>
          <h3>{editing ? "Edit your review" : "Write a review"}</h3>

          <StarRating
            value={rating}
            onChange={setRating}
            name={`rating-${bookId}`}
          />
          {fieldError(errors, "rating") ? (
            <p className="field-error">{fieldError(errors, "rating")}</p>
          ) : null}

          <div className="field">
            <label htmlFor="review-title">Title (optional)</label>
            <input
              id="review-title"
              type="text"
              maxLength={120}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
            {fieldError(errors, "title") ? (
              <p className="field-error">{fieldError(errors, "title")}</p>
            ) : null}
          </div>

          <div className="field">
            <label htmlFor="review-comment">Your review (optional)</label>
            <textarea
              id="review-comment"
              rows={4}
              maxLength={2000}
              value={comment}
              onChange={(event) => setComment(event.target.value)}
            />
            {fieldError(errors, "comment") ? (
              <p className="field-error">{fieldError(errors, "comment")}</p>
            ) : null}
          </div>

          <div className="form-actions">
            <button
              type="submit"
              className="button primary"
              disabled={busy || rating === 0}
            >
              {busy
                ? "Saving..."
                : editing
                  ? "Save changes"
                  : "Submit review"}
            </button>
            {editing ? (
              <button
                type="button"
                className="button secondary"
                onClick={resetForm}
                disabled={busy}
              >
                Cancel
              </button>
            ) : null}
          </div>
          {rating === 0 ? (
            <p className="muted">Choose a rating from 1 to 5 to submit.</p>
          ) : null}
        </form>
      ) : null}

      {myReview && !editing ? (
        <div className="own-review">
          <h3>Your review</h3>
          <ReviewCard review={myReview} />
          <div className="form-actions">
            <button
              type="button"
              className="button secondary"
              onClick={() => setEditing(true)}
              disabled={busy}
            >
              Edit
            </button>
            <button
              type="button"
              className="button danger"
              onClick={() => handleDelete(myReview)}
              disabled={busy}
            >
              Delete
            </button>
          </div>
        </div>
      ) : null}

      <ul className="review-list">
        {reviews
          .filter((review) => !review.is_owner)
          .map((review) => (
            <li key={review.id}>
              <ReviewCard review={review} />
              {isStaff ? (
                <button
                  type="button"
                  className="button danger small"
                  onClick={() => handleDelete(review)}
                  disabled={busy}
                >
                  Remove review
                </button>
              ) : null}
            </li>
          ))}
      </ul>
    </section>
  );
}

function ReviewCard({ review }: { review: Review }) {
  return (
    <article className="review-card">
      <header>
        <StarRating value={review.rating} />
        <p className="review-meta">
          <strong>{review.author}</strong> ·{" "}
          {formatDateTime(review.created_at)}
          {review.is_edited ? " · edited" : ""}
        </p>
      </header>
      {review.title ? <h4>{review.title}</h4> : null}
      {review.comment ? <p>{review.comment}</p> : null}
    </article>
  );
}
