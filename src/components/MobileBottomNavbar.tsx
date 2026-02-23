import React from "react";
import { Box, Button} from "@mui/material";
import { Link } from "react-router-dom";
import AutoGraphIcon from "@mui/icons-material/AutoGraph";

const MobileBottomNavbar: React.FC = () => {
  return (
    <Box
      sx={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        backgroundColor: "primary.main", // Use a suitable color
        display: { xs: "flex", md: "none" },
        justifyContent: "space-around",
        padding: "10px 0",
        backdropFilter: "none", // Remove blur effect if background is solid
        zIndex: 1100, // Ensure it's above other content
      }}
    >
      {/* Navigation links with icons */}
      <Button
        component={Link}
        to="/predict-price"
        sx={{ color: "white", flexDirection: "column" }}
      >
        <AutoGraphIcon />
        Predict
      </Button>
    </Box>
  );
};

export default MobileBottomNavbar;
