import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { ApiClient } from "./core/api/client";
import { webStorage } from "./core/storage";
import "./styles.css";

const client = new ApiClient(import.meta.env.VITE_API_BASE_URL ?? "", webStorage());

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App client={client} />
  </StrictMode>,
);
