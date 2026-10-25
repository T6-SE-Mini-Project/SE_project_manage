export default function AddToCartButton({ onAdd, busy = false, disabled = false }) {
  return (
    <button
      type="button"
      className="button primary add-to-cart"
      onClick={onAdd}
      disabled={busy || disabled}
    >
      {busy ? "Adding..." : "Add to cart"}
    </button>
  );
}
