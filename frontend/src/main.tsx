import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import App from "./App";
import { FirebaseAuthProvider } from "./hooks/useAuth";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* Inside the query client: the provider refetches the session
          when the Firebase account changes. */}
      <FirebaseAuthProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </FirebaseAuthProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
