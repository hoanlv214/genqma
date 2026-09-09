import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./app/App";
import "./styles/styles.css";
import "./styles/index.css";
import "./styles/app.css";
import "./styles/marketplace.css";
import "./styles/user.css";
import "./styles/global-header.css";



ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
