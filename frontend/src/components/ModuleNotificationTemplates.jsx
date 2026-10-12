/**
 * بخش جمع‌شونده‌ی «متن اعلان‌ها» برای صفحه‌ی مدیریت یک ماژول سراسری (متن مشترک همه‌ی سایت‌ها).
 * ورودی: module (notices | evaluation | birthday | feedback | login_security | family)، title و sx.
 * فقط برای کسی نمایش داده می‌شود که مجوز همان ماژول را برای همه‌ی سایت‌ها دارد
 * (user.notification_template_modules از /auth/me). محتوا فقط با باز شدن بارگذاری می‌شود.
 */
import { useCallback, useState } from "react";
import { Accordion, AccordionDetails, AccordionSummary, Box, Typography } from "@mui/material";
import ExpandMoreOutlinedIcon from "@mui/icons-material/ExpandMoreOutlined";
import NotificationTemplatesEditor from "./NotificationTemplatesEditor";
import { useAuth } from "../context/AuthContext";
import { fetchNotificationTemplates, saveNotificationTemplates } from "../api/notificationTemplates";

export default function ModuleNotificationTemplates({ module, title = "متن اعلان‌ها", sx }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const load = useCallback(() => fetchNotificationTemplates(module), [module]);
  const save = useCallback((texts) => saveNotificationTemplates(module, texts), [module]);
  if (!user?.notification_template_modules?.includes(module)) return null;
  return (
    <Box sx={{ mt: 3, ...sx }}>
      <Accordion variant="outlined" expanded={open} onChange={(_, v) => setOpen(v)}>
        <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
          <Typography fontWeight={700}>{title}</Typography>
        </AccordionSummary>
        <AccordionDetails>{open && <NotificationTemplatesEditor load={load} save={save} />}</AccordionDetails>
      </Accordion>
    </Box>
  );
}
