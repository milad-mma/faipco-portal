// پیش‌نمایش صفحه‌ای نامه روی کاغذ A4/A5 با سربرگ، پابرگ و حاشیه‌ی قالب (اندازه‌ها به میلی‌متر، مثل چاپ).
// متن در یک ظرف پنهان با همان عرض اندازه‌گیری و به تعداد صفحه تقسیم می‌شود؛ onPages(تعداد) به والد خبر می‌دهد.
// نکته: شکستن صفحه در پیش‌نمایش ساده است (ممکن است یک خط بین دو صفحه نصف شود)؛ نسخه‌ی رسمی PDF از فاز ارسال ساخته می‌شود.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Box } from "@mui/material";
import { fetchLogoBlob } from "../../api/automationLetters";

const PAPER = { A4: [210, 297], A5: [148, 210] };

// آدرس blob: لوگو (img معمولی توکن نمی‌فرستد)
export function useLogoUrl(fileId) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!fileId) {
      setUrl(null);
      return undefined;
    }
    let alive = true;
    let objectUrl = null;
    fetchLogoBlob(fileId)
      .then((blob) => {
        if (!alive) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => alive && setUrl(null));
    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [fileId]);
  return url;
}

// محتوای متن نامه (موضوع + بدنه) با استایل یکسان در اندازه‌گیری و نمایش
function BodyContent({ subject, bodyHtml }) {
  return (
    <>
      {subject ? (
        <div style={{ fontWeight: 700, marginBottom: "4mm" }}>
          موضوع: {subject}
        </div>
      ) : null}
      {/* body_html در سرور با فهرست مجاز پاک‌سازی شده است (core/oa_html.py) */}
      <div className="oa-letter-body" dangerouslySetInnerHTML={{ __html: bodyHtml || "" }} />
    </>
  );
}

const bodyStyles = {
  "& .oa-letter-body p": { margin: "0 0 2mm" },
  "& .oa-letter-body h2": { fontSize: "1.3em", margin: "3mm 0 2mm" },
  "& .oa-letter-body h3": { fontSize: "1.15em", margin: "3mm 0 2mm" },
  "& .oa-letter-body ul, & .oa-letter-body ol": { margin: "0 0 2mm", paddingInlineStart: "7mm" },
  "& .oa-letter-body table": { borderCollapse: "collapse", width: "100%", margin: "2mm 0" },
  "& .oa-letter-body td, & .oa-letter-body th": { border: "0.3mm solid #444", padding: "1mm 2mm", verticalAlign: "top" },
  "& .oa-letter-body th": { background: "#f2f2f2" },
  "& .oa-letter-body td p, & .oa-letter-body th p": { margin: 0 },
  "& .oa-letter-body blockquote": { borderInlineStart: "1mm solid #bbb", margin: "2mm 0", paddingInlineStart: "3mm", color: "#444" },
};

function Header({ layout, logoUrl }) {
  const h = layout.header;
  const field = (label) => (
    <div style={{ whiteSpace: "nowrap" }}>
      {label}: <span style={{ color: "#999" }}>..............</span>
    </div>
  );
  return (
    <div style={{ height: `${h.height_mm}mm`, display: "flex", alignItems: "center", gap: "4mm", borderBottom: "0.3mm solid #999", boxSizing: "border-box" }}>
      <div style={{ width: "28%", height: "100%", display: "flex", alignItems: "center" }}>
        {logoUrl ? <img src={logoUrl} alt="" style={{ maxHeight: "85%", maxWidth: "100%", objectFit: "contain" }} /> : null}
      </div>
      <div style={{ flex: 1, textAlign: "center" }}>
        {h.title ? <div style={{ fontWeight: 700, fontSize: "1.25em" }}>{h.title}</div> : null}
        {h.subtitle ? <div style={{ fontSize: "0.9em", color: "#444" }}>{h.subtitle}</div> : null}
      </div>
      <div style={{ width: "28%", fontSize: "0.85em", lineHeight: 1.7 }}>
        {h.show_number ? field("شماره") : null}
        {h.show_date ? field("تاریخ") : null}
        {h.show_attachment ? field("پیوست") : null}
      </div>
    </div>
  );
}

function Page({ paper, layout, logoUrl, pageIndex, pages, subject, bodyHtml, bodyHmm }) {
  const [w, h] = PAPER[paper];
  const m = layout.margins_mm;
  return (
    <Box
      className="oa-page"
      sx={{
        width: `${w}mm`,
        height: `${h}mm`,
        boxSizing: "border-box",
        padding: `${m.top}mm ${m.right}mm ${m.bottom}mm ${m.left}mm`,
        background: "#fff",
        color: "#000",
        fontFamily: "Vazirmatn, Tahoma, sans-serif",
        fontSize: `${layout.font_size_pt}pt`,
        lineHeight: 1.8,
        direction: "rtl",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        ...bodyStyles,
      }}
    >
      <Header layout={layout} logoUrl={logoUrl} />
      <div style={{ height: `${bodyHmm}mm`, overflow: "hidden", position: "relative", flex: "none", paddingTop: 0 }}>
        <div style={{ position: "absolute", insetInline: 0, top: `-${pageIndex * bodyHmm}mm` }}>
          <BodyContent subject={subject} bodyHtml={bodyHtml} />
        </div>
      </div>
      {layout.footer.height_mm > 0 && (
        <div style={{ height: `${layout.footer.height_mm}mm`, borderTop: "0.3mm solid #999", fontSize: "0.8em", display: "flex", alignItems: "center", justifyContent: "space-between", color: "#333" }}>
          <span>{layout.footer.text}</span>
          {pages > 1 ? <span>صفحه {pageIndex + 1} از {pages}</span> : null}
        </div>
      )}
    </Box>
  );
}

/**
 * props: paper ("A4"|"A5")، layout (چیدمان همان اندازه)، subject، bodyHtml، scale (نمایش؛ ۱ = اندازه‌ی واقعی)،
 * onPages(n)، printOnly (فقط برای چاپ: بدون scale، صفحه‌ها پشت هم با شکست صفحه)، forcePages (تعداد صفحه‌ی ازپیش‌محاسبه)
 */
export default function LetterPreview({ paper = "A4", layout, subject, bodyHtml, scale = 0.6, onPages, printOnly = false, forcePages }) {
  const logoUrl = useLogoUrl(layout?.header?.logo_file_id);
  const measureRef = useRef(null);
  const unitRef = useRef(null);
  const [measured, setPages] = useState(1);
  const pages = forcePages || measured; // نسخه‌ی چاپ (پنهان روی صفحه) تعداد را از پیش‌نمایش می‌گیرد
  const [w, h] = PAPER[paper] || PAPER.A4;
  const m = layout.margins_mm;
  const bodyWmm = w - m.left - m.right;
  const bodyHmm = h - m.top - m.bottom - layout.header.height_mm - layout.footer.height_mm;

  useLayoutEffect(() => {
    const el = measureRef.current;
    const unit = unitRef.current;
    if (!el || !unit || forcePages) return;
    const pagePx = unit.getBoundingClientRect().height || 1;
    const n = Math.max(1, Math.ceil((el.scrollHeight - 1) / pagePx));
    setPages(n);
    onPages?.(n);
  }, [subject, bodyHtml, paper, bodyWmm, bodyHmm, layout.font_size_pt, onPages, forcePages]);

  const pageList = Array.from({ length: pages }, (_, i) => (
    <Box key={i} sx={printOnly ? { breakAfter: "page", pageBreakAfter: "always" } : { width: `${w * scale}mm`, height: `${h * scale}mm`, boxShadow: 3, flex: "none" }}>
      <Box sx={printOnly ? {} : { transform: `scale(${scale})`, transformOrigin: "top right" }}>
        <Page paper={paper} layout={layout} logoUrl={logoUrl} pageIndex={i} pages={pages} subject={subject} bodyHtml={bodyHtml} bodyHmm={bodyHmm} />
      </Box>
    </Box>
  ));

  return (
    <Box sx={{ position: "relative" }}>
      {/* اندازه‌گیری: همان عرض، قلم و استایل متن، بیرون از دید */}
      <Box sx={{ position: "fixed", visibility: "hidden", pointerEvents: "none", left: 0, top: 0, zIndex: -1, "@media print": { display: "none" } }} aria-hidden>
        <div ref={unitRef} style={{ height: `${bodyHmm}mm` }} />
        <Box
          ref={measureRef}
          sx={{ width: `${bodyWmm}mm`, fontSize: `${layout.font_size_pt}pt`, lineHeight: 1.8, fontFamily: "Vazirmatn, Tahoma, sans-serif", direction: "rtl", ...bodyStyles }}
        >
          <BodyContent subject={subject} bodyHtml={bodyHtml} />
        </Box>
      </Box>
      {printOnly ? pageList : <Box sx={{ display: "flex", flexWrap: "wrap", gap: 2, justifyContent: "center" }}>{pageList}</Box>}
    </Box>
  );
}
