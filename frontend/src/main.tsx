import React from "react";
import ReactDOM from "react-dom/client";

import { AppProviders } from "./app/providers";
import { AppRouter } from "./app/router";
import { SystemStatusBar } from "./components/system/system-status-bar";
import "./global.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <AppProviders>
      <SystemStatusBar />
      <AppRouter />
    </AppProviders>
  </React.StrictMode>
);
