import React from "react";
import { Route, Routes, Navigate } from "react-router-dom";
import PricePredictorPage from "./pages/PricePredictorPage";
import "./App.css";
import Navbar from "./components/Navbar"; 
import MobileBottomNavbar from "./components/MobileBottomNavbar"; 
import useMediaQuery from "@mui/material/useMediaQuery";
import { useTheme } from "@mui/material/styles";
import { Box } from "@mui/material"; 

function App() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));

  return (
    <>
      {!isMobile && <Navbar />}
      <Box
        sx={{
          paddingBottom: isMobile ? "80px" : 0,
          paddingTop: !isMobile ? "72px" : 0, 
        }}
      >
        <Routes>
          <Route path="/" element={<Navigate to="/predict-price" replace />} />
          <Route
            path="/predict-price"
            element={<PricePredictorPage />}
          />
        </Routes>
      </Box>
      {isMobile && <MobileBottomNavbar />}
    </>
  );
}

export default App;
