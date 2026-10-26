import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
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
        <Route index element={<Navigate to="/books" replace />} />
        <Route path="books" element={<CataloguePage />} />
        <Route path="books/:bookId" element={<BookDetailPage />} />
        <Route path="cart" element={<CartPage />} />
        <Route path="checkout" element={<CheckoutPage />} />
        <Route path="orders" element={<OrdersPage />} />
        <Route
          path="orders/:orderId/confirmation"
          element={<OrderConfirmationPage />}
        />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />

        {/* Administrator screens. RequireStaff keeps the navigation
            honest; the API enforces is_staff on every request. */}
        <Route path="admin" element={<RequireStaff />}>
          <Route element={<AdminLayout />}>
            <Route index element={<Navigate to="/admin/books" replace />} />
            <Route path="books" element={<AdminBooksPage />} />
            <Route path="orders" element={<AdminOrdersPage />} />
            <Route path="customers" element={<AdminCustomersPage />} />
            <Route path="reports" element={<AdminReportsPage />} />
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
