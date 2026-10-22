/* SPDX-License-Identifier: AGPL-3.0-only */
/**
 * Mount the document assistant; StrictMode also exercises lifecycle cleanup in development.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./style.css";
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
