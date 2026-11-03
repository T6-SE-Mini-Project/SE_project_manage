import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import {
  useBillingAddresses,
  useCart,
  useCartAvailability,
  usePayOrder,
  usePlaceOrder,
} from "../hooks/useBookStore";
import { ApiError } from "../api";
import {
  EMPTY_BILLING_ADDRESS,
  normalizeBillingAddress,
  validateBillingAddress,
} from "../billingValidation";
import { formatPrice } from "../format";
import type {
  AvailabilityProblem,
  BillingAddress,
  SavedBillingAddress,
} from "../types";

interface CardForm {
  cardNumber: string;
  cvc: string;
  expiryMonth: string;
  expiryYear: string;
}

const EMPTY_FORM: CardForm = {
  cardNumber: "",
  cvc: "",
  expiryMonth: "",
  expiryYear: "",
};

type FieldErrors = Partial<Record<keyof BillingAddress, string>>;

interface AddressField {
  name: keyof BillingAddress;
  label: string;
  placeholder: string;
  autoComplete: string;
  type?: string;
  inputMode?: "numeric";
  maxLength?: number;
  hint?: string;
  fullWidth?: boolean;
  optional?: boolean;
}

const ADDRESS_FIELDS: AddressField[] = [
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

function formatCardError(error: unknown): string {
  if (error instanceof ApiError) {
    const problems = error.body.availability as
      | AvailabilityProblem[]
      | undefined;
    if (problems && problems.length > 0) {
      return problems.map((problem) => problem.reason).join(" ");
    }
    return error.message;
  }
  return error instanceof Error ? error.message : "Payment failed.";
}

/** Per-field messages the server returns for a rejected billing address. */
function serverFieldErrors(error: unknown): FieldErrors {
  if (!(error instanceof ApiError)) {
    return {};
  }

  const raw = error.body.errors;
  if (typeof raw !== "object" || raw === null) {
    return {};
  }

  const result: FieldErrors = {};
  ADDRESS_FIELDS.forEach(({ name }) => {
    const messages = (raw as Record<string, unknown>)[name];
    if (Array.isArray(messages) && typeof messages[0] === "string") {
      result[name] = messages[0];
    } else if (typeof messages === "string") {
      result[name] = messages;
    }
  });
  return result;
}

function describedBy(
  name: string,
  error: string | undefined,
  hint: string | undefined,
): string | undefined {
  const ids: string[] = [];
  if (hint) ids.push(`${name}-hint`);
  if (error) ids.push(`${name}-error`);
  return ids.length > 0 ? ids.join(" ") : undefined;
}

interface BillingFieldProps {
  field: AddressField;
  value: string;
  error: string | undefined;
  disabled: boolean;
  onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
}

function BillingField({
  field,
  value,
  error,
  disabled,
  onChange,
}: BillingFieldProps) {
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
        type={field.type ?? "text"}
        value={value}
        placeholder={field.placeholder}
        autoComplete={field.autoComplete}
        inputMode={field.inputMode}
        maxLength={field.maxLength}
        required={!field.optional}
        disabled={disabled}
        aria-invalid={error ? "true" : "false"}
        aria-describedby={describedBy(field.name, error, field.hint)}
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

  const cartQuery = useCart();
  const availabilityQuery = useCartAvailability();
  const addressesQuery = useBillingAddresses();
  const placeOrderMutation = usePlaceOrder();
  const payMutation = usePayOrder();

  const [form, setForm] = useState<CardForm>(EMPTY_FORM);
  const [billing, setBilling] = useState<BillingAddress>(
    EMPTY_BILLING_ADDRESS,
  );
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [selectedAddressId, setSelectedAddressId] = useState("");
  const [saveAddress, setSaveAddress] = useState(true);
  const [orderId, setOrderId] = useState<number | null>(null);
  const [error, setError] = useState("");

  const cart = cartQuery.data?.cart;
  const availability = availabilityQuery.data;
  const busy = placeOrderMutation.isPending || payMutation.isPending;

  // Saved addresses only load for a signed-in customer; a guest gets a
  // 401, which simply means "no saved addresses, can't save one".
  const isAuthenticated = addressesQuery.isSuccess;
  const savedAddresses: SavedBillingAddress[] =
    addressesQuery.data?.addresses ?? [];
  const billingLocked = orderId !== null;

  const availabilityProblems = availability && !availability.available
    ? availability.problems
    : [];

  function updateField(name: keyof CardForm, value: string) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  function handleBillingChange(event: React.ChangeEvent<HTMLInputElement>) {
    const name = event.target.name as keyof BillingAddress;
    const value = event.target.value;

    setBilling((current) => ({ ...current, [name]: value }));
    setFieldErrors((current) => {
      if (!current[name]) {
        return current;
      }
      const next = { ...current };
      delete next[name];
      return next;
    });
  }

  function handleSavedAddressChange(
    event: React.ChangeEvent<HTMLSelectElement>,
  ) {
    const addressId = event.target.value;
    setSelectedAddressId(addressId);

    if (!addressId) {
      return;
    }

    const address = savedAddresses.find(
      (item) => String(item.id) === addressId,
    );
    if (!address) {
      return;
    }

    setBilling({
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
    setFieldErrors({});
    setSaveAddress(true);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");

    try {
      let currentOrderId = orderId;

      if (currentOrderId === null) {
        // Step 1: check the billing address before anything is created.
        const billingErrors = validateBillingAddress(billing);
        setFieldErrors(billingErrors);

        const firstInvalid = Object.keys(billingErrors)[0];
        if (firstInvalid) {
          document.getElementById(firstInvalid)?.focus();
          return;
        }

        // Step 2: place the order from the cart with its billing address
        // (the server runs the availability check before creating it).
        const placed = await placeOrderMutation.mutateAsync({
          billing_address: normalizeBillingAddress(billing),
          save_address: isAuthenticated && saveAddress,
        });
        currentOrderId = placed.order.id;
        setOrderId(currentOrderId);
      }

      // Step 3: pay the placed order. A declined payment leaves the
      // order pending, so submitting again retries the same order.
      await payMutation.mutateAsync({
        order_id: currentOrderId,
        card_number: form.cardNumber,
        cvc: form.cvc,
        expiry_month: Number(form.expiryMonth),
        expiry_year: Number(form.expiryYear),
      });

      navigate(`/orders/${currentOrderId}/confirmation`);
    } catch (requestError) {
      const serverErrors = serverFieldErrors(requestError);
      setFieldErrors(serverErrors);
      setError(formatCardError(requestError));

      const firstInvalid = Object.keys(serverErrors)[0];
      if (firstInvalid) {
        document.getElementById(firstInvalid)?.focus();
      }
    }
  }

  if (cartQuery.isPending) {
    return <div className="status-panel">Loading checkout...</div>;
  }

  if (cartQuery.isError) {
    return (
      <div className="status-panel">
        <h1>Could not load checkout</h1>
        <p>{cartQuery.error.message}</p>
        <Link className="text-link" to="/cart">
          Back to the cart
        </Link>
      </div>
    );
  }

  if (!cart || cart.items.length === 0) {
    return (
      <div className="status-panel">
        <h1>Nothing to check out</h1>
        <p>Your cart is empty. Add a book before placing an order.</p>
        <Link className="button primary" to="/books">
          Browse books
        </Link>
      </div>
    );
  }

  return (
    <section className="checkout-page">
      <header className="page-heading">
        <div>
          <p className="eyebrow">Checkout</p>
          <h1>Place your order</h1>
          <p className="page-intro">
            Enter your billing address, then pay by card. Availability is
            verified before the order is placed, and payment confirms it.
            Failed payments never appear as successful orders.
          </p>
        </div>
      </header>

      {error ? (
        <div className="alert error" role="alert">
          {error}
        </div>
      ) : null}

      {availabilityProblems.length > 0 ? (
        <div className="alert error" role="alert">
          <strong>Some books are no longer available:</strong>
          <ul>
            {availabilityProblems.map((problem, index) => (
              <li key={index}>{problem.reason}</li>
            ))}
          </ul>
          <p>Update your cart before placing the order.</p>
        </div>
      ) : null}

      <div className="checkout-layout">
        <form className="checkout-form" onSubmit={handleSubmit}>
          <h2>Billing address</h2>
          <p className="muted">
            Fields marked with <span aria-hidden="true">*</span> are
            required.
          </p>

          {isAuthenticated && savedAddresses.length > 0 ? (
            <div className="saved-address-picker">
              <label htmlFor="saved_address">
                Use a saved billing address
              </label>
              <select
                id="saved_address"
                value={selectedAddressId}
                disabled={billingLocked}
                onChange={handleSavedAddressChange}
              >
                <option value="">Enter a new address</option>
                {savedAddresses.map((address) => (
                  <option key={address.id} value={address.id}>
                    {address.full_name} ({address.city},{" "}
                    {address.postal_code})
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
                value={billing[field.name]}
                error={fieldErrors[field.name]}
                disabled={billingLocked}
                onChange={handleBillingChange}
              />
            ))}
          </div>

          <div className="checkbox-block">
            <label
              className={`checkbox-row${isAuthenticated ? "" : " disabled"}`}
            >
              <input
                type="checkbox"
                checked={isAuthenticated && saveAddress}
                disabled={!isAuthenticated || billingLocked}
                onChange={(event) => setSaveAddress(event.target.checked)}
              />
              <span>Save this address for future orders</span>
            </label>

            {isAuthenticated ? (
              <p className="field-hint">
                Saved addresses are available only to your account.
              </p>
            ) : (
              <p className="field-hint">
                <Link to="/login">Sign in</Link> to save this address for
                future orders. You can still place a guest order.
              </p>
            )}
          </div>

          <h2>Card payment</h2>
          <p className="muted">
            {orderId === null
              ? "Your order is placed and then paid in one step."
              : `Retrying payment for order #${orderId}.`}
          </p>

          <div className="field">
            <label htmlFor="card_number">Card number</label>
            <input
              id="card_number"
              name="card_number"
              type="text"
              inputMode="numeric"
              autoComplete="cc-number"
              placeholder="4242 4242 4242 4242"
              value={form.cardNumber}
              onChange={(event) =>
                updateField("cardNumber", event.target.value)
              }
              required
            />
          </div>

          <div className="field-row">
            <div className="field">
              <label htmlFor="expiry_month">Expiry month</label>
              <input
                id="expiry_month"
                name="expiry_month"
                type="number"
                min="1"
                max="12"
                placeholder="MM"
                value={form.expiryMonth}
                onChange={(event) =>
                  updateField("expiryMonth", event.target.value)
                }
                required
              />
            </div>
            <div className="field">
              <label htmlFor="expiry_year">Expiry year</label>
              <input
                id="expiry_year"
                name="expiry_year"
                type="number"
                min="2026"
                placeholder="YYYY"
                value={form.expiryYear}
                onChange={(event) =>
                  updateField("expiryYear", event.target.value)
                }
                required
              />
            </div>
            <div className="field">
              <label htmlFor="cvc">CVC</label>
              <input
                id="cvc"
                name="cvc"
                type="text"
                inputMode="numeric"
                autoComplete="cc-csc"
                placeholder="123"
                value={form.cvc}
                onChange={(event) => updateField("cvc", event.target.value)}
                required
              />
            </div>
          </div>

          <button
            type="submit"
            className="button primary"
            disabled={busy || availabilityProblems.length > 0}
          >
            {busy
              ? "Processing..."
              : orderId === null
                ? `Place order and pay ${formatPrice(cart.total)}`
                : "Retry payment"}
          </button>
        </form>

        <aside className="cart-summary" aria-labelledby="checkout-summary">
          <h2 id="checkout-summary">Order summary</h2>
          <ul className="summary-items">
            {cart.items.map((item) => (
              <li key={item.id} className="summary-item">
                <span>
                  {item.book.title} × {item.quantity}
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
          <Link className="button secondary" to="/cart">
            Back to the cart
          </Link>
        </aside>
      </div>
    </section>
  );
}
