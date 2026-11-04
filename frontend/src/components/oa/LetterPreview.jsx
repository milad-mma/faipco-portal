// پیش‌نمایش صفحه‌ای نامه روی کاغذ A4/A5 با سربرگ، پابرگ و حاشیه‌ی قالب (اندازه‌ها به میلی‌متر، مثل چاپ).
// متن در یک ظرف پنهان با همان عرض اندازه‌گیری و روی مرز خط‌ها به صفحه‌ها تقسیم می‌شود؛ onPages(تعداد، شکست‌ها) به والد خبر می‌دهد.
// نکته: شکستن صفحه در پیش‌نمایش ساده است (ممکن است یک خط بین دو صفحه نصف شود)؛ نسخه‌ی رسمی PDF از فاز ارسال ساخته می‌شود.
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
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
function BodyContent({ subject, bodyHtml, signatures }) {
  return (
    <>
      {subject ? (
        <div className="oa-letter-subject" style={{ fontWeight: 700, marginBottom: "4mm" }}>
          موضوع: {subject}
        </div>
      ) : null}
      {/* body_html در سرور با فهرست مجاز پاک‌سازی شده است (core/oa_html.py) */}
      <div className="oa-letter-body" dangerouslySetInnerHTML={{ __html: bodyHtml || "" }} />
      {/* امضا: پایین متن، سمت چپ (در صفحه‌ی rtl، flex-end = چپ؛ style درون‌خطی تا افزونه‌ی RTL جابه‌جایش نکند) */}
      {signatures?.length ? (
        // چند امضا (نویسنده و مراحل «امضا»ی گردش تأیید) کنار هم؛ آخرین امضاکننده سمت چپ‌تر
        <div className="oa-letter-signature" style={{ display: "flex", justifyContent: "flex-end", flexWrap: "wrap", gap: "4mm", marginTop: "6mm" }}>
          {signatures.map((sg, i) => (
            <div key={sg.key || i} style={{ width: "50mm", textAlign: "center", lineHeight: 1.6 }}>
              <div style={{ height: "20mm", display: "flex", alignItems: "center", justifyContent: "center" }}>
                {sg.imageUrl ? <img src={sg.imageUrl} alt="" style={{ maxHeight: "20mm", maxWidth: "46mm", objectFit: "contain" }} /> : null}
              </div>
              <div style={{ fontWeight: 700 }}>{faDigits(sg.name || "")}</div>
              {sg.title ? <div style={{ fontSize: "0.9em" }}>{faDigits(sg.title)}</div> : null}
            </div>
          ))}
        </div>
      ) : null}
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

// همه‌ی اعداد داخل نامه فارسی نمایش داده می‌شوند (متن، موضوع، سربرگ، پابرگ، شماره و صفحه) — فقط در نمایش/چاپ؛ متن ذخیره‌شده دست نمی‌خورد
const FA = "۰۱۲۳۴۵۶۷۸۹";
export const faDigits = (v) => String(v ?? "").replace(/[0-9]/g, (d) => FA[d]);
// فقط متن بین برچسب‌ها؛ ویژگی‌ها (src، style، …) و موجودیت‌های HTML مثل &#39; تغییر نمی‌کنند
export function faDigitsHtml(html) {
  return String(html || "").replace(/(<[^>]*>)|(&#?\w+;)|([0-9]+)/g, (all, tag, ent, num) => (num ? faDigits(num) : all));
}

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
          __html: faDigitsHtml(fillTemplate(logoUrl ? h.html : h.html.replace(/<img [^>]*src="\{\{logo\}\}"[^>]*>/g, ""), { ...values, logo: logoUrl || "" })),
        }}
      />
    );
  }
  const field = (label, value) => (
    <div style={{ whiteSpace: "nowrap" }}>
      {label}:{" "}
      {value && !/^\.+$/.test(value) ? <bdi dir="ltr">{faDigits(value)}</bdi> : <span style={{ color: "#999" }}>..............</span>}
    </div>
  );
  return (
    <div style={{ height: `${h.height_mm}mm`, display: "flex", alignItems: "center", gap: "4mm", borderBottom: "0.3mm solid #999", boxSizing: "border-box", flex: "none" }}>
      <div style={{ width: "28%", height: "100%", display: "flex", alignItems: "center" }}>
        {logoUrl ? <img src={logoUrl} alt="" style={{ maxHeight: "85%", maxWidth: "100%", objectFit: "contain" }} /> : null}
      </div>
      <div style={{ flex: 1, textAlign: "center" }}>
        {h.title ? <div style={{ fontWeight: 700, fontSize: "1.25em" }}>{faDigits(h.title)}</div> : null}
        {h.subtitle ? <div style={{ fontSize: "0.9em", color: "#444" }}>{faDigits(h.subtitle)}</div> : null}
      </div>
      <div style={{ width: "28%", fontSize: "0.85em", lineHeight: 1.7 }}>
        {h.show_number ? field("شماره", values.number) : null}
        {h.show_date ? field("تاریخ", values.date) : null}
        {h.show_attachment ? field("پیوست", values.attachment) : null}
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
        dangerouslySetInnerHTML={{ __html: faDigitsHtml(fillTemplate(f.html, { ...values, page: pageIndex + 1, pages })) }}
      />
    );
  }
  return (
    <div style={{ height: `${f.height_mm}mm`, borderTop: "0.3mm solid #999", fontSize: "0.8em", display: "flex", alignItems: "center", justifyContent: "space-between", color: "#333", flex: "none" }}>
      <span>{faDigits(f.text)}</span>
      {pages > 1 ? <span>صفحه {faDigits(pageIndex + 1)} از {faDigits(pages)}</span> : null}
    </div>
  );
}

/**
 * شکستن صفحه روی مرز خط: همه‌ی خط‌های متن (مستطیل‌های Range روی هر گره‌ی متنی) و انتهای بلوک‌ها نقطه‌ی شکست مجازند.
 * هر صفحه تا آخرین خطی که کامل جا می‌شود می‌رود و صفحه‌ی بعد درست از همان‌جا شروع می‌شود — هیچ خطی نصف نمی‌شود.
 * خروجی: [{start, height}] به px (CSS px، همان واحد mm در چاپ).
 */
function computeSegments(container, pagePx) {
  const top0 = container.getBoundingClientRect().top;
  const total = container.scrollHeight;
  const lines = []; // [top, bottom] هر خط متن
  const blocks = []; // [top, bottom] هر بلوک (پاراگراف، ردیف جدول، …)
  const walker = document.createTreeWalker(container, 4 /* NodeFilter.SHOW_TEXT */);
  const range = document.createRange();
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (!node.textContent.trim()) continue;
    range.selectNodeContents(node);
    for (const r of range.getClientRects()) {
      if (r.height > 0) lines.push([r.top - top0, r.bottom - top0]);
    }
  }
  container.querySelectorAll("p, h2, h3, li, tr, blockquote, table, .oa-letter-subject").forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.height > 0) blocks.push([r.top - top0, r.bottom - top0]);
  });
  const atoms = [];
  container.querySelectorAll(".oa-letter-signature").forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.height > 0) {
      atoms.push([r.top - top0, r.bottom - top0]);
      blocks.push([r.top - top0, r.bottom - top0]);
    }
  });
  const spans = lines.concat(blocks);
  const segments = [];
  let start = 0;
  let guard = 0;
  while (start < total - 1 && guard < 200) {
    guard += 1;
    const limit = start + pagePx;
    if (limit >= total) {
      segments.push({ start, height: total - start });
      break;
    }
    // انتهای خط/بلوکی که کامل داخل [start, limit] است؛ بزرگ‌ترینش
    let cut = start;
    for (const [t, b] of spans) {
      if (t >= start - 0.5 && b <= limit + 0.5 && b > cut) cut = b;
    }
    // آیا خطی هست که روی cut قطع شود؟ (خط بعدی زودتر از cut شروع شده) → cut را تا شروع آن خط عقب ببر
    for (const [t, b] of lines) {
      if (t < cut - 0.5 && b > cut + 0.5 && t > start + 0.5) cut = Math.min(cut, t);
    }
    // بلوک امضا نصف نمی‌شود: اگر برش داخلش افتاد، کل امضا به صفحه‌ی بعد می‌رود
    for (const [t, b] of atoms) {
      if (t < cut - 0.5 && b > cut + 0.5 && t > start + 0.5) cut = Math.min(cut, t);
    }
    if (cut <= start + 1) cut = limit; // خط/بلوکی بلندتر از یک صفحه: ناچار برش
    segments.push({ start, height: cut - start });
    start = cut;
  }
  return segments.length ? segments : [{ start: 0, height: Math.min(total, pagePx) }];
}

// ابعاد و حاشیه‌ها در style درون‌خطی‌اند، نه sx: افزونه‌ی RTL برنامه (rtlCache) چپ/راستِ sx را جابه‌جا می‌کند و
// حاشیه‌ی راست/چپ کاغذ باید همان جهت فیزیکی بماند.
function Page({ paper, layout, logoUrl, pageIndex, pages, subject, bodyHtml, bodyHmm, values, segment, signatures, cancelled }) {
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
        position: "relative",
        ...bodyStyles,
      }}
    >
      {/* نشان «ابطال» روی هر صفحه‌ی نامه‌ی باطل‌شده (نمایش و چاپ) */}
      {cancelled ? (
        <div
          aria-hidden
          style={{
            position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center",
            pointerEvents: "none", zIndex: 2,
          }}
        >
          <div style={{ transform: "rotate(-30deg)", border: "1.5mm solid rgba(200,0,0,0.55)", color: "rgba(200,0,0,0.55)", fontSize: "34pt", fontWeight: 900, padding: "2mm 10mm", borderRadius: "3mm" }}>
            ابطال
          </div>
        </div>
      ) : null}
      <Header layout={layout} logoUrl={logoUrl} values={values} />
      <div style={{ height: `${bodyHmm}mm`, position: "relative", flex: "none" }}>
        {/* پنجره‌ی همین صفحه: دقیقاً از ابتدای خط اول تا انتهای خط آخر این صفحه */}
        <div style={{ position: "absolute", left: 0, right: 0, top: `${GAP_TOP_MM}mm`, height: segment ? `${segment.height}px` : `calc(100% - ${GAP_TOP_MM + GAP_BOTTOM_MM}mm)`, overflow: "hidden" }}>
          <div style={{ position: "absolute", left: 0, right: 0, display: "flow-root", top: segment ? `-${segment.start}px` : `-${pageIndex * (bodyHmm - GAP_TOP_MM - GAP_BOTTOM_MM)}mm` }}>
            <BodyContent subject={subject} bodyHtml={bodyHtml} signatures={signatures} />
          </div>
        </div>
      </div>
      <Footer layout={layout} values={values} pageIndex={pageIndex} pages={pages} />
    </Box>
  );
}

/**
 * props: paper ("A4"|"A5")، layout (چیدمان همان اندازه)، subject، bodyHtml، scale (نمایش؛ ۱ = اندازه‌ی واقعی)،
 * fit (هم‌عرض ظرف)، siteName (برای {{site}})، onPages(n, segments)، printOnly (فقط برای چاپ: بدون scale، صفحه‌ها پشت هم با شکست صفحه)،
 * forceSegments (شکست صفحه‌های ازپیش‌محاسبه‌شده‌ی پیش‌نمایش)، meta ({number, date, attachment} رسمی بعد از ارسال)،
 * signature ({name, title, imageUrl} — پایین متن سمت چپ)
 */
export default function LetterPreview({ paper = "A4", layout, subject: rawSubject, bodyHtml: rawBody, scale = 0.6, fit = false, onPages, printOnly = false, forceSegments, siteName, meta, signature, signatures: signaturesProp, cancelled = false }) {
  const signatures = signaturesProp || (signature ? [signature] : null);
  const subject = useMemo(() => (rawSubject ? faDigits(rawSubject) : rawSubject), [rawSubject]);
  const bodyHtml = useMemo(() => faDigitsHtml(rawBody), [rawBody]);
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
  const [measured, setSegments] = useState(null);
  const segments = forceSegments || measured; // نسخه‌ی چاپ (پنهان روی صفحه) شکست صفحه‌ها را از پیش‌نمایش می‌گیرد
  const pages = segments?.length || 1;
  const [w, h] = PAPER[paper] || PAPER.A4;
  const m = layout.margins_mm;
  const bodyWmm = w - m.left - m.right;
  const bodyHmm = h - m.top - m.bottom - layout.header.height_mm - layout.footer.height_mm;

  useLayoutEffect(() => {
    const el = measureRef.current;
    const unit = unitRef.current;
    if (!el || !unit || forceSegments) return undefined;
    let alive = true;
    const run = () => {
      if (!alive) return;
      const pagePx = unit.getBoundingClientRect().height || 1;
      const segs = computeSegments(el, pagePx);
      setSegments(segs);
      onPages?.(segs.length, segs);
    };
    run();
    // قلم‌ها دیر بارگذاری می‌شوند و اندازه‌ی خط‌ها را عوض می‌کنند
    document.fonts?.ready?.then(run).catch(() => {});
    return () => {
      alive = false;
    };
  }, [subject, bodyHtml, paper, bodyWmm, bodyHmm, layout.font_size_pt, onPages, forceSegments, (signatures || []).map((sg) => `${sg.name}|${sg.title}`).join(",")]);

  const values = {
    title: layout.header.title,
    subtitle: layout.header.subtitle,
    site: siteName || "",
    // شماره/تاریخ/پیوست رسمی بعد از ارسال (meta)؛ پیش‌نویس نقطه‌چین
    number: meta?.number || "..........",
    date: meta?.date || "..........",
    attachment: meta?.attachment || "..........",
  };
  // کوچک‌نمایی با zoom (نه transform): اندازه‌ی واقعی در چیدمان حساب می‌شود و اسکرول/جهت RTL به هم نمی‌ریزد
  const pageList = Array.from({ length: pages }, (_, i) => (
    <Box key={i} sx={printOnly ? (i < pages - 1 ? { breakAfter: "page", pageBreakAfter: "always" } : {}) : { boxShadow: 3, flex: "none", lineHeight: 0 }} style={printOnly ? undefined : { zoom }}>
      <Page paper={paper} layout={layout} logoUrl={logoUrl} pageIndex={i} pages={pages} subject={subject} bodyHtml={bodyHtml} bodyHmm={bodyHmm} values={values} segment={segments?.[i]} signatures={signatures} cancelled={cancelled} />
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
          sx={{ display: "flow-root", width: `${bodyWmm}mm`, fontSize: `${layout.font_size_pt}pt`, lineHeight: 1.8, fontFamily: "Vazirmatn, Tahoma, sans-serif", ...bodyStyles }}
        >
          <BodyContent subject={subject} bodyHtml={bodyHtml} signatures={signatures} />
        </Box>
      </Box>
      {printOnly ? pageList : <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>{pageList}</Box>}
    </Box>
  );
}
