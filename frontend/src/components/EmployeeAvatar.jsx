import { useEffect, useRef, useState } from "react";
import { Box } from "@mui/material";
import { fetchBirthdayPhotoThumbnailBlob } from "../api/employees";
import { swr } from "../api/swrCache";
import DefaultPersonAvatar from "./DefaultPersonAvatar";

/**
 * آواتار دایره‌ای یک پرسنل: عکس بندانگشتی (photo_thumbnail که هنگام Sync از کاراوب ذخیره شده)
 * یا آیکون پیش‌فرض در صورت نبود عکس.
 * ورودی: employeeId، hasPhoto (فقط اگر true باشد تصویر درخواست می‌شود تا برای افراد بدون عکس
 * درخواست ۴۰۴ اضافه زده نشود) و size (قطر به px، پیش‌فرض 30).
 * خروجی: کادر دایره‌ای شامل Canvas تصویر یا DefaultPersonAvatar.
 */
export default function EmployeeAvatar({ employeeId, hasPhoto, size = 30 }) {
  const [photoUrl, setPhotoUrl] = useState(null); // object URL تصویر دریافت‌شده؛ null = نمایش آیکون پیش‌فرض
  const canvasRef = useRef(null);

  // دریافت blob تصویر و ساخت object URL؛ در cleanup درخواست لغو‌شده نادیده گرفته
  // و object URL آزاد می‌شود تا با باز/بسته شدن مکرر فهرست‌ها حافظه نشت نکند
  useEffect(() => {
    if (!employeeId || !hasPhoto) {
      setPhotoUrl(null);
      return;
    }
    // Blob تصویر (با واترمارک همین بیننده) ۱۰ دقیقه در Cache حافظه می‌ماند تا با برگشت به صفحه
    // یا باز شدن دوباره‌ی فهرست، عکس‌ها فوراً نمایش داده شوند
    const urls = [];
    let cancelled = false;
    let lastBlob = null;
    swr(
      `birthdayPhoto:${employeeId}`,
      () => fetchBirthdayPhotoThumbnailBlob(employeeId),
      (blob) => {
        if (cancelled || blob === lastBlob) return;
        lastBlob = blob;
        const url = URL.createObjectURL(blob);
        urls.push(url);
        setPhotoUrl(url);
      },
      { maxAgeMs: 10 * 60 * 1000 }
    ).catch(() => {
      if (!cancelled && !lastBlob) setPhotoUrl(null);
    });
    return () => {
      cancelled = true;
      urls.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [employeeId, hasPhoto]);

  // کشیدن تصویر روی Canvas با ابعاد اصلی آن، پس از آماده شدن object URL
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
      {/* به‌جای <img> از Canvas استفاده می‌شود تا «ذخیره تصویر» با راست‌کلیک کار نکند و src قابل‌کپی
          در DOM نماند؛ منوی راست‌کلیک، کشیدن و انتخاب هم غیرفعال است. این محافظت کامل نیست
          (اسکرین‌شات و تب Network)؛ لایه‌ی اصلی محافظت، واترمارک شناسه‌ی بیننده است که سمت سرور روی تصویر حک می‌شود. */}
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
      {/* آیکون پیش‌فرض تا زمانی که تصویری در دست نیست */}
      {!photoUrl && <DefaultPersonAvatar />}
    </Box>
  );
}
