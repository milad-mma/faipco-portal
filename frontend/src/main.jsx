import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { CacheProvider } from "@emotion/react";
import { rtlCache } from "./rtlCache";
import { ThemeModeProvider } from "./context/ThemeModeContext";
import { AuthProvider } from "./context/AuthContext";
import { registerServiceWorker } from "./utils/serviceWorker";
import "./utils/pwaInstall"; // ثبت زودهنگام listener رویداد beforeinstallprompt
import App from "./App";

registerServiceWorker();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <CacheProvider value={rtlCache}>
      <ThemeModeProvider>
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </ThemeModeProvider>
    </CacheProvider>
  </React.StrictMode>
);
