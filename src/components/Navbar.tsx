import React from "react";
import { AppBar, Toolbar, Typography, Box } from "@mui/material";
import { Layers } from "lucide-react";
import { Link } from "react-router-dom";

const Navbar: React.FC = () => {
  return (
    <AppBar 
      position="fixed" 
      elevation={0}
      sx={{ 
        bgcolor: 'rgba(255, 255, 255, 0.9)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid #e2e8f0'
      }}
    >
      <Toolbar sx={{ justifyContent: "space-between", py: 1 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          <Box sx={{ 
            p: 1, 
            borderRadius: 2, 
            bgcolor: 'rgba(0, 128, 0, 0.08)',
            display: 'flex',
            alignItems: 'center'
          }}>
            <Layers color="#008000" size={26} />
          </Box>
          <Typography
            variant="h6"
            component={Link}
            to="/"
            sx={{
              fontWeight: 800,
              color: "#0f172a",
              textDecoration: "none",
              letterSpacing: 1.5,
              fontSize: '1.25rem',
              display: "flex",
              alignItems: "center"
            }}
          >
          REALVALUE_<span style={{ color: '#008000', fontWeight: 900 }}>AI</span>
          </Typography>
        </Box>

        <Box sx={{ display: { xs: "none", md: "flex" } }}>
          <Box 
            sx={{ 
              px: 3, 
              py: 1, 
              borderRadius: 6, 
              bgcolor: 'rgba(0, 128, 0, 0.06)',
              border: '1px solid rgba(0, 128, 0, 0.15)',
              color: '#006600',
              fontWeight: 600,
              fontSize: '0.9rem',
              letterSpacing: 0.5
            }}
          >
            P A DASANAYAKA | 214043D | Machine Learning Assignment
          </Box>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;
