import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="status-panel">
      <h1>Page not found</h1>
      <p>The page you are looking for does not exist.</p>
      <Link className="button primary" to="/books">
        Back to the catalogue
      </Link>
    </div>
  );
}
