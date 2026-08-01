import { Box, Button, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 2,
      }}
    >
      <Typography variant="h2" fontWeight={800} color="primary.main">
        ۴۰۴
      </Typography>
      <Typography variant="body1" color="text.secondary">
        صفحه مورد نظر یافت نشد.
      </Typography>
      <Button component={RouterLink} to="/" variant="contained">
        بازگشت به داشبورد
      </Button>
    </Box>
  );
}
