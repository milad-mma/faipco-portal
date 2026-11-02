// چاپ نامه: صفحه‌ها در یک Portal مستقیم زیر body رسم می‌شوند و هنگام چاپ کل برنامه (#root) با display:none کنار می‌رود.
// قاعده‌های چاپ (از جمله @page با اندازه‌ی کاغذ) با یک <style media="print"> ساده در head گذاشته می‌شوند، نه از مسیر
// emotion/افزونه‌ی RTL — تا مرورگر اندازه‌ی کاغذ (A4/A5) را حتماً تشخیص دهد. ظرف چاپ ltr و هم‌عرض کاغذ است تا برگه
// به چپ نرود و نصفه نشود؛ خود صفحه‌ها rtl‌اند. props: paper، layout، subject، bodyHtml، pages (از پیش‌نمایش)، siteName
import { useEffect } from "react";
import { createPortal } from "react-dom";
import LetterPreview from "./LetterPreview";

const PAPER_MM = { A4: [210, 297], A5: [148, 210] };

export default function LetterPrint({ paper, layout, subject, bodyHtml, pages, siteName }) {
  const [w] = PAPER_MM[paper] || PAPER_MM.A4;

  useEffect(() => {
    const style = document.createElement("style");
    style.setAttribute("data-oa-print", "1");
    style.textContent = `
      .oa-print-root { display: none; }
      @media print {
        @page { size: ${paper} portrait; margin: 0; }
        html, body { margin: 0 !important; padding: 0 !important; background: #fff !important; width: auto !important; }
        body > *:not(.oa-print-root) { display: none !important; }
        .oa-print-root { display: block !important; direction: ltr; width: ${w}mm; margin: 0; padding: 0; }
        .oa-print-root * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
      }
    `;
    document.head.appendChild(style);
    return () => style.remove();
  }, [paper, w]);

  return createPortal(
    <div className="oa-print-root">
      <LetterPreview paper={paper} layout={layout} subject={subject} bodyHtml={bodyHtml} printOnly forcePages={pages} siteName={siteName} />
    </div>,
    document.body,
  );
}
