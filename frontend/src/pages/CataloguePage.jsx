import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { getBooks, getCategories } from "../api";
import BookCard from "../components/BookCard";

const EMPTY_FILTERS = {
  q: "",
  category: "",
  author: "",
  min_price: "",
  max_price: "",
  available: "",
};

function readFilters(params) {
  return Object.fromEntries(
    Object.keys(EMPTY_FILTERS).map((key) => [key, params.get(key) || ""]),
  );
}

export default function CataloguePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryString = searchParams.toString();

  const [draft, setDraft] = useState(() => readFilters(searchParams));
  const [books, setBooks] = useState([]);
  const [count, setCount] = useState(0);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setDraft(readFilters(new URLSearchParams(queryString)));
  }, [queryString]);

  useEffect(() => {
    let active = true;

    getCategories()
      .then((data) => {
        if (active) {
          setCategories(data.categories);
        }
      })
      .catch(() => {
        // The catalogue still works without the category suggestions.
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    const filters = Object.fromEntries(
      new URLSearchParams(queryString).entries(),
    );

    setLoading(true);
    setError("");

    getBooks(filters)
      .then((data) => {
        if (active) {
          setBooks(data.books);
          setCount(data.count);
        }
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message);
          setBooks([]);
          setCount(0);
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [queryString]);

  function handleChange(event) {
    const { name, value } = event.target;
    setDraft((current) => ({ ...current, [name]: value }));
  }

  function handleSubmit(event) {
    event.preventDefault();

    const next = new URLSearchParams();
    Object.entries(draft).forEach(([key, value]) => {
      const trimmed = value.trim();
      if (trimmed) {
        next.set(key, trimmed);
      }
    });

    setSearchParams(next);
  }

  function handleReset() {
    setDraft(EMPTY_FILTERS);
    setSearchParams(new URLSearchParams());
  }

  return (
    <section className="catalogue-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Book catalogue</p>
          <h1>Find your next read</h1>
          <p className="page-intro">
            Search by title, author, ISBN or keyword, then narrow the results
            with the filters below.
          </p>
        </div>
      </header>

      <form className="filter-panel" onSubmit={handleSubmit}>
        <div className="field field-search">
          <label htmlFor="q">Search</label>
          <input
            id="q"
            name="q"
            type="search"
            placeholder="Title, author, ISBN or keyword"
            value={draft.q}
            onChange={handleChange}
          />
        </div>

        <div className="field">
          <label htmlFor="category">Category</label>
          <select
            id="category"
            name="category"
            value={draft.category}
            onChange={handleChange}
          >
            <option value="">All categories</option>
            {categories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="author">Author</label>
          <input
            id="author"
            name="author"
            type="text"
            placeholder="Any author"
            value={draft.author}
            onChange={handleChange}
          />
        </div>

        <div className="field field-price">
          <label htmlFor="min_price">Min price</label>
          <input
            id="min_price"
            name="min_price"
            type="number"
            min="0"
            step="0.01"
            placeholder="0.00"
            value={draft.min_price}
            onChange={handleChange}
          />
        </div>

        <div className="field field-price">
          <label htmlFor="max_price">Max price</label>
          <input
            id="max_price"
            name="max_price"
            type="number"
            min="0"
            step="0.01"
            placeholder="No limit"
            value={draft.max_price}
            onChange={handleChange}
          />
        </div>

        <div className="field">
          <label htmlFor="available">Availability</label>
          <select
            id="available"
            name="available"
            value={draft.available}
            onChange={handleChange}
          >
            <option value="">Any availability</option>
            <option value="true">In stock</option>
            <option value="false">Out of stock</option>
          </select>
        </div>

        <div className="filter-actions">
          <button type="submit" className="button primary">
            Apply filters
          </button>
          <button
            type="button"
            className="button secondary"
            onClick={handleReset}
          >
            Reset
          </button>
        </div>
      </form>

      <div className="results-heading" role="status" aria-live="polite">
        {loading
          ? "Loading books..."
          : `${count} book${count === 1 ? "" : "s"} found`}
      </div>

      {error ? (
        <div className="alert error" role="alert">
          {error}
        </div>
      ) : null}

      {!loading && !error && books.length === 0 ? (
        <div className="empty-state">
          <h2>No books match those filters</h2>
          <p>Try a broader search or reset the filters to see the catalogue.</p>
          <button type="button" className="button secondary" onClick={handleReset}>
            Reset filters
          </button>
        </div>
      ) : null}

      <div className="book-grid">
        {books.map((book) => (
          <BookCard key={book.id} book={book} />
        ))}
      </div>
    </section>
  );
}
