import { useEffect, useRef, useState } from "react";
import { Box } from "@mui/material";
import { fetchBirthdayPhotoThumbnailBlob } from "../api/employees";
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
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!employeeId || !hasPhoto) {
      setPhotoUrl(null);
      return;
    }
    let objectUrl = null;
    let cancelled = false;
    fetchBirthdayPhotoThumbnailBlob(employeeId)
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

  // ⚠️ نقاشی روی Canvas پس از آماده‌شدن تصویر. بعد از کشیدن، خودِ
  // objectURL آزاد می‌شود تا حتی از طریق حافظه هم لینک قابل‌استفاده‌ای
  // باقی نماند.
  useEffect(() => {
    if (!photoUrl || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const img = new Image();
    img.onload = () => {
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext("2d");
      ctx?.drawImage(img, 0, 0);
    };
    img.src = photoUrl;
  }, [photoUrl]);

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
      {/* ⚠️ عمداً <img> استفاده نمی‌شود: با Canvas، «ذخیره تصویر» راست‌کلیک
          کار نمی‌کند و هیچ src قابل‌کپی در DOM نمی‌ماند. این جلوی کاربر
          عادی را می‌گیرد، ولی جلوگیری کامل ممکن نیست (اسکرین‌شات و تب
          Network همیشه در دسترس‌اند) - لایه اصلی محافظت، واترمارکِ
          شناسه بیننده است که سمت سرور روی تصویر حک می‌شود. */}
      <Box
        component="canvas"
        ref={canvasRef}
        onContextMenu={(e) => e.preventDefault()}
        onDragStart={(e) => e.preventDefault()}
        sx={{
          width: "100%",
          height: "100%",
          display: photoUrl ? "block" : "none",
          objectFit: "cover",
          userSelect: "none",
          WebkitUserSelect: "none",
          WebkitTouchCallout: "none",
          pointerEvents: "none",
        }}
      />
      {!photoUrl && <DefaultPersonAvatar />}
    </Box>
  );
}
