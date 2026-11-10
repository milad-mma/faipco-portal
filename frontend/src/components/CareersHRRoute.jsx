import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { Alert, CircularProgress, Box } from "@mui/material";
import { apiClient } from "../api/client";

export default function CareersHRRoute({children}) {
  const [allowed,setAllowed] = useState(null);
  useEffect(()=>{let active=true; apiClient.get("/careers/access").then(()=>{if(active)setAllowed(true);}).catch(()=>{if(active)setAllowed(false);});return()=>{active=false;};},[]);
  if(allowed===null)return <Box sx={{p:4,textAlign:"center"}}><CircularProgress/></Box>;
  if(!allowed)return <Navigate to="/my-dashboard" replace/>;
  return children;
}
