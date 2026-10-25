const API_BASE = "/api";

function readCookie(name) {
  const match = document.cookie.match(
    new RegExp(`(^|;\\s*)${name}=([^;]*)`),
  );
  return match ? decodeURIComponent(match[2]) : "";
}

let csrfPromise = null;

async function ensureCsrfToken() {
  const existing = readCookie("csrftoken");
  if (existing) {
    return existing;
  }

  if (!csrfPromise) {
    csrfPromise = fetch(`${API_BASE}/csrf/`, {
      credentials: "same-origin",
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("Unable to initialize a secure session.");
        }
        const data = await response.json();
        return data.csrfToken || readCookie("csrftoken");
      })
      .finally(() => {
        csrfPromise = null;
      });
  }

  const token = await csrfPromise;
  if (!token) {
    throw new Error("The request token could not be initialized.");
  }
  return token;
}

async function request(path, { method = "GET", body, headers = {} } = {}) {
  const options = {
    method,
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      ...headers,
    },
  };

  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    options.headers["X-CSRFToken"] = await ensureCsrfToken();
  }

  const response = await fetch(`${API_BASE}${path}`, options);
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const error = new Error(
      data.error || `Request failed (${response.status}).`,
    );
    error.status = response.status;
    throw error;
  }

  return data;
}

function queryString(filters) {
  const params = new URLSearchParams();

  Object.entries(filters).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    params.set(key, value);
  });

  const query = params.toString();
  return query ? `?${query}` : "";
}

export function getBooks(filters = {}) {
  return request(`/books/${queryString(filters)}`);
}

export function getCategories() {
  return request("/books/categories/");
}

export function getBook(bookId) {
  return request(`/books/${bookId}/`);
}

export function getCart() {
  return request("/cart/");
}

export function addToCart(bookId, quantity = 1) {
  return request("/cart/items/", {
    method: "POST",
    body: { book_id: bookId, quantity },
  });
}

export function updateCartItem(itemId, quantity) {
  return request(`/cart/items/${itemId}/`, {
    method: "PATCH",
    body: { quantity },
  });
}

export function removeCartItem(itemId) {
  return request(`/cart/items/${itemId}/`, {
    method: "DELETE",
  });
}
