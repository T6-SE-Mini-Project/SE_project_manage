import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  getBillingAddresses,
  getCart,
  getSession,
  placeOrder,
} from "../api";
import {
  EMPTY_BILLING_ADDRESS,
  normalizeBillingAddress,
  validateBillingAddress,
} from "../billingValidation";
import { formatPrice } from "../format";

const ADDRESS_FIELDS = [
  {
    name: "full_name",
    label: "Full name",
    placeholder: "e.g. Ananya Sharma",
    autoComplete: "name",
    fullWidth: true,
  },
  {
    name: "phone_number",
    label: "Phone number",
    placeholder: "10-digit mobile number",
    autoComplete: "tel",
    inputMode: "numeric",
    maxLength: 14,
    hint: "Enter exactly 10 digits. Spaces and hyphens are removed.",
  },
  {
    name: "email",
    label: "Email address",
    placeholder: "you@example.com",
    autoComplete: "email",
    type: "email",
  },
  {
    name: "address_line1",
    label: "Address line 1",
    placeholder: "House number, street and area",
    autoComplete: "address-line1",
    fullWidth: true,
  },
  {
    name: "address_line2",
    label: "Address line 2 (optional)",
    placeholder: "Apartment, landmark or locality",
    autoComplete: "address-line2",
    fullWidth: true,
    optional: true,
  },
  {
    name: "city",
    label: "City",
    placeholder: "e.g. Bengaluru",
    autoComplete: "address-level2",
  },
  {
    name: "state",
    label: "State",
    placeholder: "e.g. Karnataka",
    autoComplete: "address-level1",
  },
  {
    name: "postal_code",
    label: "PIN code",
    placeholder: "6-digit PIN code",
    autoComplete: "postal-code",
    inputMode: "numeric",
    maxLength: 6,
    hint: "Enter exactly 6 digits.",
  },
  {
    name: "country",
    label: "Country",
    placeholder: "India",
    autoComplete: "country-name",
    fullWidth: true,
  },
];

function fieldDescription(fieldName, error, hint) {
  const ids = [];
  if (hint) ids.push(`${fieldName}-hint`);
  if (error) ids.push(`${fieldName}-error`);
  return ids.length ? ids.join(" ") : undefined;
}

function BillingField({ field, value, error, onChange }) {
  const describedBy = fieldDescription(field.name, error, field.hint);

  return (
    <div className={`field${field.fullWidth ? " field-full" : ""}`}>
      <label htmlFor={field.name}>
        {field.label}
        {field.optional ? null : (
          <span className="required-mark" aria-hidden="true">
            {" "}
            *
          </span>
        )}
      </label>
      <input
        id={field.name}
        name={field.name}
        type={field.type || "text"}
        value={value}
        placeholder={field.placeholder}
        autoComplete={field.autoComplete}
        inputMode={field.inputMode}
        maxLength={field.maxLength}
        required={!field.optional}
        aria-invalid={error ? "true" : "false"}
        aria-describedby={describedBy}
        onChange={onChange}
      />
      {field.hint ? (
        <p className="field-hint" id={`${field.name}-hint`}>
          {field.hint}
        </p>
      ) : null}
      {error ? (
        <p className="field-error" id={`${field.name}-error`} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export default function CheckoutPage() {
  const navigate = useNavigate();
  const [cart, setCart] = useState(null);
  const [session, setSession] = useState({
    authenticated: false,
    user: null,
  });
  const [addresses, setAddresses] = useState([]);
  const [selectedAddressId, setSelectedAddressId] = useState("");
  const [form, setForm] = useState(EMPTY_BILLING_ADDRESS);
  const [errors, setErrors] = useState({});
  const [saveAddress, setSaveAddress] = useState(true);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadCheckout() {
      try {
        const [cartData, sessionData] = await Promise.all([
          getCart(),
          getSession(),
        ]);

        if (!active) {
          return;
        }

        setCart(cartData.cart);
        setSession(sessionData);

        if (sessionData.authenticated) {
          setForm((current) => ({
            ...current,
            email: current.email || sessionData.user?.email || "",
          }));
          setSaveAddress(true);

          try {
            const addressData = await getBillingAddresses();
            if (active) {
              setAddresses(addressData.addresses);
            }
          } catch {
            // The form is still usable if saved addresses cannot be loaded.
          }
        }
      } catch (requestError) {
        if (active) {
          setError(requestError.message);
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    loadCheckout();

    return () => {
      active = false;
    };
  }, []);

  function handleFieldChange(event) {
    const { name, value } = event.target;

    setForm((current) => ({ ...current, [name]: value }));
    setErrors((current) => {
      if (!current[name]) {
        return current;
      }

      const next = { ...current };
      delete next[name];
      return next;
    });
  }

  function handleSavedAddressChange(event) {
    const addressId = event.target.value;
    setSelectedAddressId(addressId);

    if (!addressId) {
      return;
    }

    const address = addresses.find(
      (item) => String(item.id) === addressId,
    );

    if (!address) {
      return;
    }

    setForm({
      full_name: address.full_name,
      phone_number: address.phone_number,
      email: address.email,
      address_line1: address.address_line1,
      address_line2: address.address_line2,
      city: address.city,
      state: address.state,
      postal_code: address.postal_code,
      country: address.country,
    });
    setErrors({});
    setSaveAddress(true);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    const nextErrors = validateBillingAddress(form);
    setErrors(nextErrors);

    if (Object.keys(nextErrors).length > 0) {
      const firstField = Object.keys(nextErrors)[0];
      document.getElementById(firstField)?.focus();
      return;
    }

    setSubmitting(true);

    try {
      const data = await placeOrder(
        normalizeBillingAddress(form),
        session.authenticated && saveAddress,
      );

      navigate(`/checkout/success/${data.order.id}`, {
        state: {
          order: data.order,
          addressSaved: data.address_saved,
          authenticated: session.authenticated,
        },
      });
    } catch (requestError) {
      const fieldErrors = requestError.errors || {};
      const nextFieldErrors = {};

      Object.entries(fieldErrors).forEach(([field, messages]) => {
        if (Array.isArray(messages) && messages.length > 0) {
          nextFieldErrors[field] = messages[0];
        } else if (typeof messages === "string") {
          nextFieldErrors[field] = messages;
        }
      });

      setErrors(nextFieldErrors);
      setError(requestError.message);

      const firstField = Object.keys(nextFieldErrors)[0];
      if (firstField) {
        document.getElementById(firstField)?.focus();
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return <div className="status-panel">Loading checkout...</div>;
  }

  if (error && !cart) {
    return (
      <div className="status-panel">
        <h1>Could not load checkout</h1>
        <p>{error}</p>
        <Link className="text-link" to="/cart">
          Back to your cart
        </Link>
      </div>
    );
  }

  if (cart && cart.items.length === 0) {
    return (
      <section className="checkout-page">
        <div className="empty-state">
          <h1>Your cart is empty</h1>
          <p>Add a book before entering billing details.</p>
          <Link className="button primary" to="/books">
            Browse books
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="checkout-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Checkout</p>
          <h1>Billing address</h1>
          <p className="page-intro">
            Enter the details that should appear on this order. No payment
            card information is collected here.
          </p>
        </div>
      </header>

      <ol className="checkout-steps" aria-label="Checkout progress">
        <li>
          <Link to="/cart">Cart</Link>
        </li>
        <li className="current" aria-current="step">
          Billing address
        </li>
        <li>Confirmation</li>
      </ol>

      {error ? (
        <div className="alert error" role="alert">
          {error}
        </div>
      ) : null}

      <div className="checkout-layout">
        <form className="checkout-card" onSubmit={handleSubmit} noValidate>
          <div className="checkout-card-heading">
            <h2>Billing details</h2>
            <p className="muted">
              Fields marked with <span aria-hidden="true">*</span> are
              required.
            </p>
          </div>

          {session.authenticated && addresses.length > 0 ? (
            <div className="saved-address-picker">
              <label htmlFor="saved_address">
                Use a saved billing address
              </label>
              <select
                id="saved_address"
                value={selectedAddressId}
                onChange={handleSavedAddressChange}
              >
                <option value="">Enter a new address</option>
                {addresses.map((address) => (
                  <option key={address.id} value={address.id}>
                    {address.full_name} — {address.city},{" "}
                    {address.postal_code}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          <div className="checkout-form-grid">
            {ADDRESS_FIELDS.map((field) => (
              <BillingField
                key={field.name}
                field={field}
                value={form[field.name]}
                error={errors[field.name]}
                onChange={handleFieldChange}
              />
            ))}
          </div>

          <div className="checkbox-block">
            <label
              className={`checkbox-row${
                session.authenticated ? "" : " disabled"
              }`}
            >
              <input
                type="checkbox"
                checked={session.authenticated && saveAddress}
                disabled={!session.authenticated}
                onChange={(event) => setSaveAddress(event.target.checked)}
              />
              <span>Save this address for future orders</span>
            </label>

            {session.authenticated ? (
              <p className="field-hint">
                Saved addresses are available only to your account.
              </p>
            ) : (
              <p className="field-hint">
                <a href="/login/?next=/checkout">Sign in</a> to save this
                address for future orders. You can still place a guest order.
              </p>
            )}
          </div>

          <div className="checkout-actions">
            <button
              type="submit"
              className="button primary checkout-submit"
              disabled={submitting}
            >
              {submitting ? "Placing order..." : "Place order"}
            </button>
            <Link className="button secondary" to="/cart">
              Back to cart
            </Link>
          </div>
        </form>

        <aside className="cart-summary checkout-summary">
          <h2>Order summary</h2>
          <ul className="checkout-items">
            {cart.items.map((item) => (
              <li key={item.id}>
                <span>
                  {item.quantity} × {item.book.title}
                </span>
                <span>{formatPrice(item.subtotal)}</span>
              </li>
            ))}
          </ul>
          <div className="summary-row">
            <span>Items</span>
            <span>{cart.item_count}</span>
          </div>
          <div className="summary-row total">
            <span>Total</span>
            <strong>{formatPrice(cart.total)}</strong>
          </div>
          <p className="notice">
            Payment is not connected in this milestone. Placing the order
            records it as awaiting payment and does not charge you.
          </p>
        </aside>
      </div>
    </section>
  );
}
