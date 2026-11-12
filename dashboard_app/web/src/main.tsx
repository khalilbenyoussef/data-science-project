import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { initPreferences } from "./preferences";
import "./styles.css";
import "./signature.css";

initPreferences();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
