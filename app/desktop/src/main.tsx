import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./styles.css";
import "./styles/workspace.css";
import "./styles/sidebar.css";
import "./styles/conversation.css";
import "./styles/dialogs.css";
import "./styles/responsive.css";
import "./styles/document.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("找不到桌面應用程式的根節點。");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
