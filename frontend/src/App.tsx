
import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import RequireAuth from "./components/RequireAuth";
import RequireStaff from "./components/RequireStaff";
import BookDetailPage from "./pages/BookDetailPage";
import CartPage from "./pages/CartPage";
import CataloguePage from "./pages/CataloguePage";
import CheckoutPage from "./pages/CheckoutPage";
import LoginPage from "./pages/LoginPage";
import NotFoundPage from "./pages/NotFoundPage";
import OrderConfirmationPage from "./pages/OrderConfirmationPage";
import OrdersPage from "./pages/OrdersPage";
import RegisterPage from "./pages/RegisterPage";
import AdminBooksPage from "./pages/admin/AdminBooksPage";
import AdminCustomersPage from "./pages/admin/AdminCustomersPage";
import AdminLayout from "./pages/admin/AdminLayout";
import AdminOrdersPage from "./pages/admin/AdminOrdersPage";
import AdminReportsPage from "./pages/admin/AdminReportsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* The catalogue is the home page. RequireAuth sends anyone who
            is not signed in to /login, remembering where they meant to
            go. */}
        <Route index element={<Navigate to="/books" replace />} />

        <Route path="register" element={<RegisterPage />} />
        <Route path="login" element={<LoginPage />} />

        <Route element={<RequireAuth />}>
          <Route path="books" element={<CataloguePage />} />
          <Route path="books/:bookId" element={<BookDetailPage />} />
          <Route path="cart" element={<CartPage />} />
          <Route path="checkout" element={<CheckoutPage />} />
          <Route path="orders" element={<OrdersPage />} />
          <Route
            path="orders/:orderId/confirmation"
            element={<OrderConfirmationPage />}
          />

          <Route path="admin" element={<RequireStaff />}>
            <Route element={<AdminLayout />}>
              <Route
                index
                element={<Navigate to="/admin/books" replace />}
              />
              <Route path="books" element={<AdminBooksPage />} />
              <Route path="orders" element={<AdminOrdersPage />} />
              <Route path="customers" element={<AdminCustomersPage />} />
              <Route path="reports" element={<AdminReportsPage />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
