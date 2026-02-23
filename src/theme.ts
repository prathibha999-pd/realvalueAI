import { createTheme } from "@mui/material/styles";

// Define accent color as a constant due to TypeScript limitations with custom palette properties
const accentColor = "#D4AF37"; // Gold

// Consider importing fonts in public/index.html if using non-standard ones
// e.g., <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;700&family=Merriweather:wght@400;700&display=swap" rel="stylesheet">

const theme = createTheme({
  palette: {
    primary: {
      main: "#0A1929", // Deep Navy/Charcoal
    },
    secondary: {
      main: "#D2B48C", // Warm Neutral - Tan
    },
    grey: {
      "50": "#F8F9FA", // Lightest gray for backgrounds - Warm Neutral family
      "100": "#E9ECEF",
      "200": "#DEE2E6",
      "300": "#CED4DA",
      "400": "#ADB5BD",
      "500": "#A9A9A9", // Mid-tone neutral gray (adjust if needed)
      "600": "#808080",
      "700": "#696969", // Darker neutral gray
      "800": "#404040",
      "900": "#212529", // Darkest gray/charcoal
    },
    background: {
      default: "#F8F9FA", // Keep light background
      paper: "#FFFFFF", // White for cards and panels
    },
    text: {
      primary: "#212529", // Dark charcoal text for readability
      secondary: "#696969", // Darker neutral gray for secondary text
    },
  },
  typography: {
    fontFamily: '"Poppins", sans-serif', // Default sans-serif for body
    h1: {
      fontFamily: '"Georgia", serif', // Serif for headings (ensure font is available)
      fontWeight: 700,
    },
    h2: {
      fontFamily: '"Georgia", serif',
      fontWeight: 700,
    },
    h3: {
      fontFamily: '"Georgia", serif',
      fontWeight: 700,
    },
    h4: {
      fontFamily: '"Georgia", serif',
      fontWeight: 700,
    },
    h5: {
      fontFamily: '"Georgia", serif',
      fontWeight: 700,
    },
    h6: {
      fontFamily: '"Georgia", serif',
      fontWeight: 700,
    },
    // Add other typography customizations as needed
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none", // Prevent uppercase text on buttons
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          boxShadow: "0 2px 4px rgba(0,0,0,0.1)", // Subtle default card shadow
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: "#FFFFFF", // White AppBar background
          color: "#212529", // Dark text color
        },
      },
    },
    MuiFab: {
      styleOverrides: {
        root: {
          backgroundColor: "#0A1929", // Dark blue FAB background
          color: "#FFFFFF", // White FAB icon color
          "&:hover": {
            backgroundColor: "#132F4C", // Slightly darker blue on hover
          },
        },
      },
    },
    MuiToggleButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          color: "#495057", // Neutral gray for toggle buttons
          borderColor: "#CED4DA", // Light gray border
          "&.Mui-selected": {
            color: "#0A1929", // Dark blue when selected
            backgroundColor: "#E9ECEF", // Light gray background when selected
            borderColor: "#0A1929",
            "&:hover": {
              backgroundColor: "#DEE2E6", // Slightly darker gray on hover when selected
            },
          },
        },
      },
    },
  },
  // Add more theme customizations (spacing, breakpoints, components, etc.) as needed
});

export default theme;
