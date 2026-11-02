// پیش‌نمایش صفحه‌ای نامه روی کاغذ A4/A5 با سربرگ، پابرگ و حاشیه‌ی قالب (اندازه‌ها به میلی‌متر، مثل چاپ).
// متن در یک ظرف پنهان با همان عرض اندازه‌گیری و به تعداد صفحه تقسیم می‌شود؛ onPages(تعداد) به والد خبر می‌دهد.
// نکته: شکستن صفحه در پیش‌نمایش ساده است (ممکن است یک خط بین دو صفحه نصف شود)؛ نسخه‌ی رسمی PDF از فاز ارسال ساخته می‌شود.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Box } from "@mui/material";
import { fetchLogoBlob } from "../../api/automationLetters";

const PAPER = { A4: [210, 297], A5: [148, 210] };
// فاصله‌ی متن از خط سربرگ و از پابرگ (میلی‌متر) — از ارتفاع ناحیه‌ی متن هر صفحه کم می‌شود
const GAP_TOP_MM = 5;
const GAP_BOTTOM_MM = 2;

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
  // مثل ویرایشگر: فاصله‌های پشت‌سرهم حفظ شوند و پاراگراف خالی (Enter) یک خط جا بگیرد
  "& .oa-letter-body": { whiteSpace: "pre-wrap", overflowWrap: "anywhere" },
  "& .oa-letter-body p": { margin: "0 0 2mm", minHeight: "1.8em" },
  "& .oa-letter-body h2": { fontSize: "1.3em", margin: "3mm 0 2mm" },
  "& .oa-letter-body h3": { fontSize: "1.15em", margin: "3mm 0 2mm" },
  "& .oa-letter-body ul, & .oa-letter-body ol": { margin: "0 0 2mm", paddingInlineStart: "7mm" },
  "& .oa-letter-body table": { borderCollapse: "collapse", width: "100%", margin: "2mm 0" },
  "& .oa-letter-body td, & .oa-letter-body th": { border: "0.3mm solid #444", padding: "1mm 2mm", verticalAlign: "top" },
  "& .oa-letter-body th": { background: "#f2f2f2" },
  "& .oa-letter-body td p, & .oa-letter-body th p": { margin: 0 },
  "& .oa-letter-body blockquote": { borderInlineStart: "1mm solid #bbb", margin: "2mm 0", paddingInlineStart: "3mm", color: "#444" },
};

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// جای‌نگهدارهای HTML قالب ({{title}}، {{page}}، …) با مقدار escape‌شده؛ HTML خود قالب در سرور پاک‌سازی شده است
// (core/oa_template_html.py). شماره/تاریخ/پیوست تا ارسال نامه نقطه‌چین است.
export function fillTemplate(html, values) {
  return (html || "").replace(/\{\{\s*(\w+)\s*\}\}/g, (all, key) => (key in values ? esc(values[key]) : all));
}

function Header({ layout, logoUrl, values }) {
  const h = layout.header;
  if (h.html) {
    return (
      <div
        style={{ height: `${h.height_mm}mm`, overflow: "hidden", boxSizing: "border-box", flex: "none" }}
        dangerouslySetInnerHTML={{
          __html: fillTemplate(logoUrl ? h.html : h.html.replace(/<img [^>]*src="\{\{logo\}\}"[^>]*>/g, ""), { ...values, logo: logoUrl || "" }),
        }}
      />
    );
  }
  const field = (label) => (
    <div style={{ whiteSpace: "nowrap" }}>
      {label}: <span style={{ color: "#999" }}>..............</span>
    </div>
  );
  return (
    <div style={{ height: `${h.height_mm}mm`, display: "flex", alignItems: "center", gap: "4mm", borderBottom: "0.3mm solid #999", boxSizing: "border-box", flex: "none" }}>
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

function Footer({ layout, values, pageIndex, pages }) {
  const f = layout.footer;
  if (!(f.height_mm > 0)) return null;
  if (f.html) {
    return (
      <div
        style={{ height: `${f.height_mm}mm`, overflow: "hidden", boxSizing: "border-box", flex: "none" }}
        dangerouslySetInnerHTML={{ __html: fillTemplate(f.html, { ...values, page: pageIndex + 1, pages }) }}
      />
    );
  }
  return (
    <div style={{ height: `${f.height_mm}mm`, borderTop: "0.3mm solid #999", fontSize: "0.8em", display: "flex", alignItems: "center", justifyContent: "space-between", color: "#333", flex: "none" }}>
      <span>{f.text}</span>
      {pages > 1 ? <span>صفحه {pageIndex + 1} از {pages}</span> : null}
    </div>
  );
}

// ابعاد و حاشیه‌ها در style درون‌خطی‌اند، نه sx: افزونه‌ی RTL برنامه (rtlCache) چپ/راستِ sx را جابه‌جا می‌کند و
// حاشیه‌ی راست/چپ کاغذ باید همان جهت فیزیکی بماند.
function Page({ paper, layout, logoUrl, pageIndex, pages, subject, bodyHtml, bodyHmm, values }) {
  const [w, h] = PAPER[paper];
  const m = layout.margins_mm;
  return (
    <Box
      className="oa-page"
      style={{
        width: `${w}mm`,
        height: `${h}mm`,
        boxSizing: "border-box",
        paddingTop: `${m.top}mm`,
        paddingRight: `${m.right}mm`,
        paddingBottom: `${m.bottom}mm`,
        paddingLeft: `${m.left}mm`,
        direction: "rtl", // درون‌خطی: افزونه‌ی RTL مقدار direction داخل sx را برعکس (ltr) می‌کند
      }}
      dir="rtl"
      sx={{
        background: "#fff",
        color: "#000",
        fontFamily: "Vazirmatn, Tahoma, sans-serif",
        fontSize: `${layout.font_size_pt}pt`,
        lineHeight: 1.8,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        ...bodyStyles,
      }}
    >
      <Header layout={layout} logoUrl={logoUrl} values={values} />
      <div style={{ height: `${bodyHmm}mm`, position: "relative", flex: "none" }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: `${GAP_TOP_MM}mm`, bottom: `${GAP_BOTTOM_MM}mm`, overflow: "hidden" }}>
          <div style={{ position: "absolute", left: 0, right: 0, top: `-${pageIndex * (bodyHmm - GAP_TOP_MM - GAP_BOTTOM_MM)}mm` }}>
            <BodyContent subject={subject} bodyHtml={bodyHtml} />
          </div>
        </div>
      </div>
      <Footer layout={layout} values={values} pageIndex={pageIndex} pages={pages} />
    </Box>
  );
}

/**
 * props: paper ("A4"|"A5")، layout (چیدمان همان اندازه)، subject، bodyHtml، scale (نمایش؛ ۱ = اندازه‌ی واقعی)،
 * fit (هم‌عرض ظرف)، siteName (برای {{site}})، onPages(n)، printOnly (فقط برای چاپ: بدون scale، صفحه‌ها پشت هم با شکست صفحه)، forcePages (تعداد صفحه‌ی ازپیش‌محاسبه)
 */
export default function LetterPreview({ paper = "A4", layout, subject, bodyHtml, scale = 0.6, fit = false, onPages, printOnly = false, forcePages, siteName }) {
  // fit: کوچک‌نمایی به اندازه‌ی عرض ظرف (مثلاً نیمی از صفحه در دسکتاپ)؛ وگرنه scale ثابت
  const boxRef = useRef(null);
  const [fitScale, setFitScale] = useState(null);
  useEffect(() => {
    if (!fit || printOnly || !boxRef.current) return undefined;
    const el = boxRef.current;
    const [pw, ph] = PAPER[paper] || PAPER.A4;
    const pageW = (pw * 96) / 25.4;
    const pageH = (ph * 96) / 25.4;
    // عرض ظرف، ولی نه بلندتر از ارتفاع پنجره (تا یک صفحه‌ی کامل بدون اسکرول زیاد دیده شود)
    const measure = () => {
      const byWidth = (el.clientWidth - 8) / pageW;
      const byHeight = (window.innerHeight - 140) / pageH;
      setFitScale(Math.max(0.3, Math.min(1, byWidth, byHeight)));
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    window.addEventListener("resize", measure);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [fit, printOnly, paper]);
  const zoom = fit && fitScale ? fitScale : scale;
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

  const values = {
    title: layout.header.title,
    subtitle: layout.header.subtitle,
    site: siteName || "",
    number: "..........",
    date: "..........",
    attachment: "..........",
  };
  // کوچک‌نمایی با zoom (نه transform): اندازه‌ی واقعی در چیدمان حساب می‌شود و اسکرول/جهت RTL به هم نمی‌ریزد
  const pageList = Array.from({ length: pages }, (_, i) => (
    <Box key={i} sx={printOnly ? (i < pages - 1 ? { breakAfter: "page", pageBreakAfter: "always" } : {}) : { boxShadow: 3, flex: "none", lineHeight: 0 }} style={printOnly ? undefined : { zoom }}>
      <Page paper={paper} layout={layout} logoUrl={logoUrl} pageIndex={i} pages={pages} subject={subject} bodyHtml={bodyHtml} bodyHmm={bodyHmm} values={values} />
    </Box>
  ));

  return (
    <Box ref={boxRef} sx={{ position: "relative", width: fit ? "100%" : undefined }}>
      {/* اندازه‌گیری: همان عرض، قلم و استایل متن، بیرون از دید */}
      <Box sx={{ position: "fixed", visibility: "hidden", pointerEvents: "none", left: 0, top: 0, zIndex: -1, "@media print": { display: "none" } }} aria-hidden>
        <div ref={unitRef} style={{ height: `${bodyHmm - GAP_TOP_MM - GAP_BOTTOM_MM}mm` }} />
        <Box
          ref={measureRef}
          dir="rtl"
          style={{ direction: "rtl" }}
          sx={{ width: `${bodyWmm}mm`, fontSize: `${layout.font_size_pt}pt`, lineHeight: 1.8, fontFamily: "Vazirmatn, Tahoma, sans-serif", ...bodyStyles }}
        >
          <BodyContent subject={subject} bodyHtml={bodyHtml} />
        </Box>
      </Box>
      {printOnly ? pageList : <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>{pageList}</Box>}
    </Box>
  );
}
