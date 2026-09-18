import { useEffect, useState } from "react";
import { Box } from "@mui/material";
import { fetchEmployeePhotoThumbnailBlob } from "../api/employees";
import DefaultPersonAvatar from "./DefaultPersonAvatar";

/**
 * آواتار یک پرسنل - اگر عکسی در کاراوب داشته باشد (که هنگام Sync در
 * photo_thumbnail ذخیره شده) همان نمایش داده می‌شود، وگرنه آیکون پیش‌فرض.
 *
 * ⚠️ مثل داشبورد شخصی، فقط وقتی hasPhoto صریحاً true باشد درخواست تصویر
 * زده می‌شود - وگرنه برای هر نفرِ بدون عکس یک ۴۰۴ اضافه به سرور می‌خورد
 * (در فهرست تبریک‌گویندگان که ممکن است ده‌ها نفر باشند، این مهم است).
 *
 * ⚠️ objectURL در Cleanup آزاد می‌شود تا با باز/بسته شدن مکرر فهرست،
 * حافظه نشت نکند.
 */
export default function EmployeeAvatar({ employeeId, hasPhoto, size = 30 }) {
  const [photoUrl, setPhotoUrl] = useState(null);

  useEffect(() => {
    if (!employeeId || !hasPhoto) {
      setPhotoUrl(null);
      return;
    }
    let objectUrl = null;
    let cancelled = false;
    fetchEmployeePhotoThumbnailBlob(employeeId)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setPhotoUrl(objectUrl);
      })
      .catch(() => setPhotoUrl(null));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [employeeId, hasPhoto]);

  return (
    <Box
      sx={{
        width: size,
        height: size,
        borderRadius: "50%",
        bgcolor: "action.hover",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
        overflow: "hidden",
        color: "text.secondary",
      }}
    >
      {photoUrl ? (
        <Box component="img" src={photoUrl} alt="" sx={{ width: "100%", height: "100%", objectFit: "cover" }} />
      ) : (
        <DefaultPersonAvatar />
      )}
    </Box>
  );
}
