import { Navigate, Route, Routes } from "react-router-dom";

import Layout from "./components/Layout";
import BookDetailPage from "./pages/BookDetailPage";
import CartPage from "./pages/CartPage";
import CataloguePage from "./pages/CataloguePage";
import NotFoundPage from "./pages/NotFoundPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/books" replace />} />
        <Route path="books" element={<CataloguePage />} />
        <Route path="books/:bookId" element={<BookDetailPage />} />
        <Route path="cart" element={<CartPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
