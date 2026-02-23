import "@mui/material/styles";
import { PaletteColorOptions, PaletteColor } from "@mui/material/styles";

declare module "@mui/material/styles" {
  // Allow configuration using `createTheme`
  interface PaletteOptions {
    accent?: PaletteColorOptions;
  }

  // Allow usage in components
  interface Palette {
    accent: PaletteColor;
  }
}

// You also might need to augment PaletteColorOptions if you want simple strings like '#D4AF37'
// instead of the full { main: '#D4AF37' } structure, but using the object structure is safer.
// Example for simple string (use cautiously):
/*
declare module '@mui/material/styles/createPalette' {
  interface PaletteColorOptions {
    main?: string; // Allow simple string assignment
  }
}
*/

// If using custom colors in Button, Chip, etc., you might need to augment their props interfaces too.
// Example for Button:
/*
declare module '@mui/material/Button' {
  interface ButtonPropsColorOverrides {
    accent: true;
  }
}
*/
