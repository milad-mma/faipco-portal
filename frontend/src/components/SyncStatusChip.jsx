import { Box, Chip } from "@mui/material";
import { keyframes } from "@mui/material/styles";

const pulse = keyframes`
  0%   { box-shadow: 0 0 0 0 rgba(233, 156, 44, 0.55); }
  70%  { box-shadow: 0 0 0 8px rgba(233, 156, 44, 0); }
  100% { box-shadow: 0 0 0 0 rgba(233, 156, 44, 0); }
`;

const STATUS_CONFIG = {
  success: { label: "موفق", color: "success", dot: "#2E7D5B" },
  failed: { label: "ناموفق", color: "error", dot: "#C0392B" },
  partial: { label: "ناقص", color: "warning", dot: "#C97A2B" },
  running: { label: "در حال اجرا", color: "warning", dot: "#C97A2B" },
  never: { label: "هرگز اجرا نشده", color: "default", dot: "#9AA5B1" },
};

export default function SyncStatusChip({ status }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.never;
  const isRunning = status === "running";

  return (
    <Chip
      variant="outlined"
      color={config.color === "default" ? undefined : config.color}
      icon={
        <Box
          component="span"
          sx={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            backgroundColor: config.dot,
            display: "inline-block",
            marginInlineStart: "8px",
            animation: isRunning ? `${pulse} 1.4s infinite` : "none",
          }}
        />
      }
      label={config.label}
      size="small"
    />
  );
}
