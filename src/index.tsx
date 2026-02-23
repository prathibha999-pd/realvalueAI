import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";
import reportWebVitals from "./reportWebVitals";
import { BrowserRouter } from "react-router-dom";
import { ThemeProvider } from "@mui/material/styles"; // Import ThemeProvider
import CssBaseline from "@mui/material/CssBaseline"; // Import CssBaseline for global resets
import theme from "./theme"; // Import the custom theme
// import { LandingPageFilterProvider } from "./context/LandingPageFilterContext"; // Removed

// Attempt to unregister any service workers.
if ("serviceWorker" in navigator) {
  navigator.serviceWorker
    .getRegistrations()
    .then(function (registrations) {
      for (let registration of registrations) {
        registration
          .unregister()
          .then(function () {
            console.log(
              "Service Worker unregistered successfully:",
              registration.scope
            );
          })
          .catch(function (error) {
            console.error("Service Worker unregistration failed:", error);
          });
      }
    })
    .catch(function (error) {
      console.error("Error getting service worker registrations:", error);
    });
}

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement
);
root.render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {/* <LandingPageFilterProvider> */} {/* Removed */}
      <BrowserRouter>
        <App />
      </BrowserRouter>
      {/* </LandingPageFilterProvider> */} {/* Removed */}
    </ThemeProvider>
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
