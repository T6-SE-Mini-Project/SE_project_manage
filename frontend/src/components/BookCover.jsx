import { useState } from "react";

export default function BookCover({ book, className = "book-cover" }) {
  const [failed, setFailed] = useState(false);

  if (!book.cover_image_url || failed) {
    return (
      <div className={`${className} cover-placeholder`} aria-hidden="true">
        <span>No cover</span>
      </div>
    );
  }

  return (
    <img
      className={className}
      src={book.cover_image_url}
      alt={`Cover of ${book.title}`}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}
