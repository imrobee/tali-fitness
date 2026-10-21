import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import App from "./App.tsx";
import { ApiError } from "./api/client";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Refetch when the app comes back into view: "today" and the greeting may have
      // changed while it was in the background (UI_SPEC.md 5.1).
      refetchOnWindowFocus: true,
      // Retry network trouble once; an answer from the API (401, 422) will not change.
      retry: (failureCount, error) => !(error instanceof ApiError) && failureCount < 1,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
