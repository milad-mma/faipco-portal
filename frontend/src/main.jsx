import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { CacheProvider } from "@emotion/react";
import { CssBaseline, ThemeProvider } from "@mui/material";
import { rtlCache } from "./rtlCache";
import { theme } from "./theme";
import { AuthProvider } from "./context/AuthContext";
import { registerServiceWorker } from "./utils/serviceWorker";
import "./utils/pwaInstall"; // ثبت زودهنگام listener رویداد beforeinstallprompt
import App from "./App";

registerServiceWorker();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <CacheProvider value={rtlCache}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <BrowserRouter>
          <AuthProvider>
            <App />
          </AuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </CacheProvider>
  </React.StrictMode>
);
