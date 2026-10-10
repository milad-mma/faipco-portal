/**
 * کارت یک بخش در صفحه‌های «مرکزی» پرسنل (بیمه تکمیلی، کارتابل درخواست، …): آیکون، عنوان، توضیح کوتاه و فلش.
 * disabled: برچسب «غیرفعال» و کم‌رنگ (ولی هنوز قابل کلیک تا پیام «غیرفعال» صفحه‌ی مقصد دیده شود، مگر onClick نباشد).
 * comingSoon: برچسب «به‌زودی» و غیرقابل کلیک. badge: شمارنده (مثلاً درخواست‌های منتظر تصمیم).
 */
import { Badge, Box, Card, CardActionArea, Chip, Stack, Typography } from "@mui/material";
import ChevronLeftOutlinedIcon from "@mui/icons-material/ChevronLeftOutlined";

export default function HubCard({ icon, title, description, onClick, disabled, comingSoon, badge = 0 }) {
  const inactive = disabled || comingSoon;
  const content = (
    <Stack direction="row" spacing={2} alignItems="flex-start" sx={{ width: "100%" }}>
      <Badge color="warning" badgeContent={badge} invisible={!badge || comingSoon}>
        <Box
          sx={{
            width: 52,
            height: 52,
            borderRadius: 2.5,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            bgcolor: "action.hover",
            color: "primary.main",
            flexShrink: 0,
            "& svg": { fontSize: 30 },
          }}
        >
          {icon}
        </Box>
      </Badge>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 0.5 }} flexWrap="wrap" useFlexGap>
          <Typography fontWeight={800}>{title}</Typography>
          {disabled && !comingSoon && <Chip size="small" label="غیرفعال" sx={{ height: 20, fontSize: 11 }} />}
          {comingSoon && <Chip size="small" label="به‌زودی" sx={{ height: 20, fontSize: 11 }} />}
        </Stack>
        <Typography variant="body2" color="text.secondary">
          {description}
        </Typography>
      </Box>
      {!comingSoon && <ChevronLeftOutlinedIcon color="action" sx={{ alignSelf: "center" }} />}
    </Stack>
  );
  return (
    <Card variant="outlined" sx={{ borderRadius: 3, height: "100%", opacity: inactive ? 0.6 : 1 }}>
      {comingSoon || !onClick ? (
        <Box sx={{ p: 3, height: "100%" }}>{content}</Box>
      ) : (
        <CardActionArea onClick={onClick} sx={{ p: 3, height: "100%", display: "flex", alignItems: "flex-start" }}>
          {content}
        </CardActionArea>
      )}
    </Card>
  );
}
