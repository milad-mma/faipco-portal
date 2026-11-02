// چاپ نامه: صفحه‌ها در یک Portal مستقیم زیر body رسم می‌شوند و هنگام چاپ کل برنامه (#root) با display:none کنار می‌رود.
// این‌طور چیدمان صفحه (ستون‌ها، sticky، zoom پیش‌نمایش) روی چاپ اثر ندارد و شکست صفحه در جریان عادی سند درست کار می‌کند.
// روی صفحه‌ی نمایش چیزی دیده نمی‌شود. props: paper، layout، subject، bodyHtml، pages (از پیش‌نمایش)، siteName
import { createPortal } from "react-dom";
import { GlobalStyles } from "@mui/material";
import LetterPreview from "./LetterPreview";

export default function LetterPrint({ paper, layout, subject, bodyHtml, pages, siteName }) {
  return (
    <>
      <GlobalStyles
        styles={{
          ".oa-print-root": { display: "none" },
          "@media print": {
            "@page": { size: `${paper} portrait`, margin: 0 },
            "html, body": { margin: 0, padding: 0, background: "#fff" },
            "body > #root": { display: "none !important" },
            ".oa-print-root": { display: "block !important" },
          },
        }}
      />
      {createPortal(
        <div className="oa-print-root" dir="rtl">
          <LetterPreview paper={paper} layout={layout} subject={subject} bodyHtml={bodyHtml} printOnly forcePages={pages} siteName={siteName} />
        </div>,
        document.body,
      )}
    </>
  );
}
