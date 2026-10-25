import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="status-panel">
      <h1>Page not found</h1>
      <p>The page you requested does not exist.</p>
      <Link className="text-link" to="/books">
        Back to the catalogue
      </Link>
    </div>
  );
}
