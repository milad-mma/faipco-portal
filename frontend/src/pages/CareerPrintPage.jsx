import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Alert, Box, Button, CircularProgress, Stack, Typography } from "@mui/material";
import { apiClient } from "../api/client";
import CareerPrintDocument from "./CareerPrintDocument";

export default function CareerPrintPage() {
 const {id} = useParams(); const [item,setItem] = useState(null); const [error,setError] = useState("");
 useEffect(()=>{apiClient.get(`/careers/applications/${id}`).then(r=>setItem(r.data)).catch(()=>setError("دریافت پرونده امکان‌پذیر نبود."));},[id]);
 return <Box dir="rtl" sx={{p:2,backgroundColor:"#eee",minHeight:"100vh"}}>
  <Stack className="print-toolbar" direction="row" spacing={1} useFlexGap mb={2} alignItems="center"><Button variant="contained" disabled={!item} onClick={()=>window.print()}>چاپ / ذخیره PDF</Button><Button onClick={()=>window.close()}>بستن</Button><Typography variant="caption">پیش‌نمایش چاپ A4 پرسشنامه استخدامی؛ انتخاب چاپگر یا ذخیره PDF</Typography></Stack>
  {error?<Alert severity="error">{error}</Alert>:!item?<CircularProgress/>:<CareerPrintDocument record={item}/>}
 </Box>;
}
