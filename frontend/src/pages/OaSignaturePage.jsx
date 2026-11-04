// «امضای من» زیر منوی اتوماسیون اداری (/automation/signature)
import { Box } from "@mui/material";
import MySignatureDialog from "../components/oa/MySignatureDialog";

export default function OaSignaturePage() {
  return (
    <Box sx={{ maxWidth: 640, mx: "auto" }}>
      <MySignatureDialog open inline />
    </Box>
  );
}
