const priceFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export function formatPrice(value: string | number): string {
  const amount = Number(value);

  if (Number.isNaN(amount)) {
    return String(value);
  }

  return priceFormatter.format(amount);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "Not specified";
  }

  const date = new Date(`${value}T00:00:00`);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}
