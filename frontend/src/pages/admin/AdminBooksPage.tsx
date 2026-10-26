/**
 * Administrator catalogue management (issue #12, OBS-F-017).
 *
 * Adds books, edits stock and pricing, and withdraws titles. Validation
 * messages come from the server's form, so the rules shown here are the
 * same ones the API enforces.
 */
import { useState } from "react";

import {
  useAdminBooks,
  useCreateBook,
  useDeleteBook,
  useUpdateBook,
} from "../../hooks/useAdmin";
import { errorMessage, fieldError, fieldErrors } from "../../errors";
import { formatPrice } from "../../format";
import type { BookDetail, BookInput } from "../../types";

const EMPTY_BOOK: BookInput = {
  title: "",
  author: "",
  isbn: "",
  description: "",
  category: "",
  price: "",
  stock_quantity: 0,
  cover_image_url: "",
  publisher: "",
  publication_date: null,
};

function bookToInput(book: BookDetail): BookInput {
  return {
    title: book.title,
    author: book.author,
    isbn: book.isbn,
    description: book.description,
    category: book.category,
    price: book.price,
    stock_quantity: book.stock_quantity,
    cover_image_url: book.cover_image_url,
    publisher: book.publisher,
    publication_date: book.publication_date,
  };
}

export default function AdminBooksPage() {
  const [search, setSearch] = useState("");
  const [lowStockOnly, setLowStockOnly] = useState(false);

  const booksQuery = useAdminBooks({
    q: search || undefined,
    // "Low stock" is anything with three copies or fewer left.
    low_stock: lowStockOnly ? "3" : undefined,
  });
  const createMutation = useCreateBook();
  const updateMutation = useUpdateBook();
  const deleteMutation = useDeleteBook();

  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<BookInput>(EMPTY_BOOK);
  const [notice, setNotice] = useState("");
  const [failure, setFailure] = useState("");

  const activeMutation = editingId === null ? createMutation : updateMutation;
  const errors = fieldErrors(activeMutation.error);
  const busy =
    createMutation.isPending ||
    updateMutation.isPending ||
    deleteMutation.isPending;

  function updateField(name: keyof BookInput, value: string | number | null) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  function startCreate() {
    setEditingId(null);
    setForm(EMPTY_BOOK);
    setNotice("");
    setFailure("");
  }

  function startEdit(book: BookDetail) {
    setEditingId(book.id);
    setForm(bookToInput(book));
    setNotice("");
    setFailure("");
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setNotice("");
    setFailure("");

    try {
      if (editingId === null) {
        await createMutation.mutateAsync(form);
        setNotice(`"${form.title}" has been added to the catalogue.`);
      } else {
        await updateMutation.mutateAsync({ bookId: editingId, input: form });
        setNotice(`"${form.title}" has been updated.`);
      }
      startCreate();
    } catch {
      // Per-field errors are rendered beside the inputs below.
    }
  }

  async function handleDelete(book: BookDetail) {
    setNotice("");
    setFailure("");

    try {
      await deleteMutation.mutateAsync(book.id);
      setNotice(`"${book.title}" has been removed from the catalogue.`);
      if (editingId === book.id) {
        startCreate();
      }
    } catch (error) {
      // A book that appears on an order is protected; the server
      // explains that stock should be set to 0 instead.
      setFailure(errorMessage(error, "The book could not be deleted."));
    }
  }

  const books = booksQuery.data?.books ?? [];

  return (
    <div className="admin-section">
      <div className="admin-toolbar">
        <div className="field">
          <label htmlFor="book-search">Search title, author or ISBN</label>
          <input
            id="book-search"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={lowStockOnly}
            onChange={(event) => setLowStockOnly(event.target.checked)}
          />
          Low stock only (3 or fewer)
        </label>
      </div>

      {notice ? (
        <div className="alert success" role="status">
          {notice}
        </div>
      ) : null}
      {failure ? (
        <div className="alert error" role="alert">
          {failure}
        </div>
      ) : null}
      {activeMutation.isError ? (
        <div className="alert error" role="alert">
          {errorMessage(activeMutation.error, "The book could not be saved.")}
        </div>
      ) : null}

      <form className="admin-form" onSubmit={handleSubmit}>
        <h2>{editingId === null ? "Add a book" : `Edit book #${editingId}`}</h2>

        <div className="field-row">
          <div className="field">
            <label htmlFor="book-title">Title</label>
            <input
              id="book-title"
              type="text"
              value={form.title}
              onChange={(event) => updateField("title", event.target.value)}
              required
            />
            {fieldError(errors, "title") ? (
              <p className="field-error">{fieldError(errors, "title")}</p>
            ) : null}
          </div>
          <div className="field">
            <label htmlFor="book-author">Author</label>
            <input
              id="book-author"
              type="text"
              value={form.author}
              onChange={(event) => updateField("author", event.target.value)}
              required
            />
            {fieldError(errors, "author") ? (
              <p className="field-error">{fieldError(errors, "author")}</p>
            ) : null}
          </div>
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="book-isbn">ISBN</label>
            <input
              id="book-isbn"
              type="text"
              value={form.isbn}
              onChange={(event) => updateField("isbn", event.target.value)}
              placeholder="978-0132350884"
              required
            />
            {fieldError(errors, "isbn") ? (
              <p className="field-error">{fieldError(errors, "isbn")}</p>
            ) : null}
          </div>
          <div className="field">
            <label htmlFor="book-category">Category</label>
            <input
              id="book-category"
              type="text"
              value={form.category}
              onChange={(event) => updateField("category", event.target.value)}
              required
            />
            {fieldError(errors, "category") ? (
              <p className="field-error">{fieldError(errors, "category")}</p>
            ) : null}
          </div>
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="book-price">Price</label>
            <input
              id="book-price"
              type="number"
              step="0.01"
              min="0"
              value={form.price}
              onChange={(event) => updateField("price", event.target.value)}
              required
            />
            {fieldError(errors, "price") ? (
              <p className="field-error">{fieldError(errors, "price")}</p>
            ) : null}
          </div>
          <div className="field">
            <label htmlFor="book-stock">Stock quantity</label>
            <input
              id="book-stock"
              type="number"
              min="0"
              value={form.stock_quantity}
              onChange={(event) =>
                updateField("stock_quantity", Number(event.target.value))
              }
              required
            />
            {fieldError(errors, "stock_quantity") ? (
              <p className="field-error">
                {fieldError(errors, "stock_quantity")}
              </p>
            ) : null}
          </div>
          <div className="field">
            <label htmlFor="book-published">Publication date</label>
            <input
              id="book-published"
              type="date"
              value={form.publication_date ?? ""}
              onChange={(event) =>
                updateField("publication_date", event.target.value || null)
              }
            />
            {fieldError(errors, "publication_date") ? (
              <p className="field-error">
                {fieldError(errors, "publication_date")}
              </p>
            ) : null}
          </div>
        </div>

        <div className="field-row">
          <div className="field">
            <label htmlFor="book-publisher">Publisher</label>
            <input
              id="book-publisher"
              type="text"
              value={form.publisher}
              onChange={(event) => updateField("publisher", event.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="book-cover">Cover image URL</label>
            <input
              id="book-cover"
              type="url"
              value={form.cover_image_url}
              onChange={(event) =>
                updateField("cover_image_url", event.target.value)
              }
            />
            {fieldError(errors, "cover_image_url") ? (
              <p className="field-error">
                {fieldError(errors, "cover_image_url")}
              </p>
            ) : null}
          </div>
        </div>

        <div className="field">
          <label htmlFor="book-description">Description</label>
          <textarea
            id="book-description"
            rows={3}
            value={form.description}
            onChange={(event) => updateField("description", event.target.value)}
          />
        </div>

        <div className="form-actions">
          <button type="submit" className="button primary" disabled={busy}>
            {busy
              ? "Saving..."
              : editingId === null
                ? "Add book"
                : "Save changes"}
          </button>
          {editingId !== null ? (
            <button
              type="button"
              className="button secondary"
              onClick={startCreate}
              disabled={busy}
            >
              Cancel edit
            </button>
          ) : null}
        </div>
      </form>

      <h2>Catalogue ({booksQuery.data?.count ?? 0})</h2>

      {booksQuery.isPending ? (
        <p className="muted">Loading the catalogue...</p>
      ) : booksQuery.isError ? (
        <p className="feedback error">
          {errorMessage(booksQuery.error, "The catalogue could not be loaded.")}
        </p>
      ) : books.length === 0 ? (
        <p className="muted">No books match the current filters.</p>
      ) : (
        <div className="table-scroll">
          <table className="admin-table">
            <thead>
              <tr>
                <th scope="col">Title</th>
                <th scope="col">Author</th>
                <th scope="col">ISBN</th>
                <th scope="col">Category</th>
                <th scope="col">Price</th>
                <th scope="col">Stock</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {books.map((book) => (
                <tr key={book.id}>
                  <td>{book.title}</td>
                  <td>{book.author}</td>
                  <td>{book.isbn}</td>
                  <td>{book.category}</td>
                  <td>{formatPrice(book.price)}</td>
                  <td>
                    <span
                      className={
                        book.stock_quantity === 0
                          ? "badge muted"
                          : book.stock_quantity <= 3
                            ? "badge warning"
                            : "badge success"
                      }
                    >
                      {book.stock_quantity}
                    </span>
                  </td>
                  <td className="table-actions">
                    <button
                      type="button"
                      className="button secondary small"
                      onClick={() => startEdit(book)}
                      disabled={busy}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      className="button danger small"
                      onClick={() => handleDelete(book)}
                      disabled={busy}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
