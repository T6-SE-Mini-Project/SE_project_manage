/**
 * Star rating, for display or as an input (issue #11).
 *
 * With `onChange` it renders radio inputs, so a rating can be chosen and
 * submitted with the keyboard as well as the mouse; without it, it is a
 * read-only summary with an accessible text label.
 */
const STARS = [1, 2, 3, 4, 5];

interface StarRatingProps {
  /** Current rating, 0 or null meaning unrated. */
  value: number | null;
  onChange?: (rating: number) => void;
  /** Identifies the radio group when several ratings share a page. */
  name?: string;
  label?: string;
}

export default function StarRating({
  value,
  onChange,
  name = "rating",
  label,
}: StarRatingProps) {
  const rating = value ?? 0;

  if (!onChange) {
    return (
      <span className="star-rating" role="img" aria-label={
        rating > 0 ? `${rating} out of 5 stars` : "Not rated yet"
      }>
        {STARS.map((star) => (
          <span
            key={star}
            aria-hidden="true"
            className={star <= Math.round(rating) ? "star filled" : "star"}
          >
            ★
          </span>
        ))}
      </span>
    );
  }

  return (
    <fieldset className="star-input">
      <legend>{label ?? "Your rating"}</legend>
      {STARS.map((star) => (
        <label key={star} className="star-choice">
          <input
            type="radio"
            name={name}
            value={star}
            checked={rating === star}
            onChange={() => onChange(star)}
          />
          <span aria-hidden="true" className={star <= rating ? "star filled" : "star"}>
            ★
          </span>
          <span className="visually-hidden">
            {star} star{star === 1 ? "" : "s"}
          </span>
        </label>
      ))}
    </fieldset>
  );
}
