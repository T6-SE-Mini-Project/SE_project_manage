import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import BookDetailPage from "./pages/BookDetailPage";
import CartPage from "./pages/CartPage";
import CataloguePage from "./pages/CataloguePage";
import CheckoutPage from "./pages/CheckoutPage";
import NotFoundPage from "./pages/NotFoundPage";
import OrderConfirmationPage from "./pages/OrderConfirmationPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/books" replace />} />
        <Route path="books" element={<CataloguePage />} />
        <Route path="books/:bookId" element={<BookDetailPage />} />
        <Route path="cart" element={<CartPage />} />
        <Route path="checkout" element={<CheckoutPage />} />
        <Route
          path="orders/:orderId/confirmation"
          element={<OrderConfirmationPage />}
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
