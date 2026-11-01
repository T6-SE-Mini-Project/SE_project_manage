export const EMPTY_BILLING_ADDRESS = {
  full_name: "",
  phone_number: "",
  email: "",
  address_line1: "",
  address_line2: "",
  city: "",
  state: "",
  postal_code: "",
  country: "India",
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function compactPhone(value) {
  return value.replace(/[\s-]/g, "");
}

function compactPin(value) {
  return value.replace(/\s/g, "");
}

export function normalizeBillingAddress(values) {
  return {
    full_name: values.full_name.trim().replace(/\s+/g, " "),
    phone_number: compactPhone(values.phone_number.trim()),
    email: values.email.trim().toLowerCase(),
    address_line1: values.address_line1.trim().replace(/\s+/g, " "),
    address_line2: values.address_line2.trim().replace(/\s+/g, " "),
    city: values.city.trim().replace(/\s+/g, " "),
    state: values.state.trim().replace(/\s+/g, " "),
    postal_code: compactPin(values.postal_code.trim()),
    country: values.country.trim().replace(/\s+/g, " "),
  };
}

export function validateBillingAddress(values) {
  const errors = {};

  if (!values.full_name.trim()) {
    errors.full_name = "Full name is required.";
  }

  const phone = compactPhone(values.phone_number.trim());
  if (!phone) {
    errors.phone_number = "Phone number is required.";
  } else if (!/^\d{10}$/.test(phone)) {
    errors.phone_number = "Phone number must be exactly 10 digits.";
  }

  const email = values.email.trim();
  if (!email) {
    errors.email = "Email address is required.";
  } else if (!EMAIL_PATTERN.test(email)) {
    errors.email = "Enter a valid email address.";
  }

  if (!values.address_line1.trim()) {
    errors.address_line1 = "Address line 1 is required.";
  }

  if (!values.city.trim()) {
    errors.city = "City is required.";
  }

  if (!values.state.trim()) {
    errors.state = "State is required.";
  }

  const pin = compactPin(values.postal_code.trim());
  if (!pin) {
    errors.postal_code = "PIN code is required.";
  } else if (!/^\d{6}$/.test(pin)) {
    errors.postal_code = "PIN code must be exactly 6 digits.";
  }

  if (!values.country.trim()) {
    errors.country = "Country is required.";
  }

  return errors;
}
