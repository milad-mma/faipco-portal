// Object URL یک Blob از API (مثلاً تصویر امضا)؛ key خالی = بدون درخواست. با تغییر key یا unmount آزاد می‌شود.
import { useEffect, useState } from "react";

export default function useBlobUrl(key, fetcher) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!key) {
      setUrl(null);
      return undefined;
    }
    let u = null;
    let alive = true;
    fetcher()
      .then((blob) => {
        if (!alive) return;
        u = URL.createObjectURL(blob);
        setUrl(u);
      })
      .catch(() => setUrl(null));
    return () => {
      alive = false;
      if (u) URL.revokeObjectURL(u);
    };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return url;
}
