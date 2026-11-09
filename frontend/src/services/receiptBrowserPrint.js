import { fetchReceiptPrintData } from '../api/receiptPrint';

// All receipt values are escaped: this window contains confidential employee data.
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const show = (v) => escapeHtml(v).replace(/\n/g, '<br>');
const sectionsFixed = ['وام', 'کسور', 'مزایا', 'سایر'];
const weights = { 'وام': 19, 'کسور': 24, 'مزایا': 24, 'سایر': 33 };
const footerPositions = { 'شماره حساب': 1, 'خالص پرداختی': 1 };

function payrollHtml(data) {
  const infos = [], footers = [], sections = new Map();
  let reportTitle = '';
  for (const f of data.fields || []) {
    if (f.section === '__meta__' && f.label === '__report_title__') reportTitle = f.value;
    else if (f.section === '__footer__') footers.push(f);
    else if (!f.section) infos.push(f);
    else { if (!sections.has(f.section)) sections.set(f.section, []); sections.get(f.section).push(f); }
  }
  function takeInfo(s) { const i = infos.findIndex((f) => String(f.label).includes(s)); return i < 0 ? '' : infos.splice(i, 1)[0].value; }
  const year = takeInfo('سال'), month = takeInfo('ماه');
  const cols = [...sectionsFixed, ...[...sections.keys()].filter((s) => !sectionsFixed.includes(s))];
  const total = cols.reduce((n, s) => n + (weights[s] || 25), 0);
  const grid = cols.map((s) => (100 * (weights[s] || 25) / total) + '%').join(' ');
  const infoWidths = infos.map((f) => String(f.label).includes('کد پرسنلی') ? '.6fr' : (String(f.label).includes('نام') && !String(f.label).includes('کد')) ? '1.4fr' : '1fr').join(' ');
  const infoHtml = infos.length ? `<div class="info" style="grid-template-columns:${infoWidths}">${infos.map((f) => `<div><b>${show(f.label)}:</b> ${show(f.value)}</div>`).join('')}</div>` : '';
  const maxRows = Math.max(0, ...cols.map((s) => (sections.get(s) || []).length));
  const rows = Array.from({ length: maxRows }, (_, i) => `<div class="pay-row" style="grid-template-columns:${grid}">${cols.map((s) => {
    const f = (sections.get(s) || [])[i];
    return `<div class="pay-cell">${f ? `<span class="val">${show(f.value)}</span><span class="lbl">${show(f.label)}</span>` : ''}</div>`;
  }).join('')}</div>`).join('');
  const footer = footers.length ? `<div class="summary" style="grid-template-columns:${grid}">${cols.map((s) => {
    const items = footers.filter((f) => (cols.includes(f.column) ? f.column : cols[0]) === s);
    return `<div>${[0, 1].map((idx) => {
      const f = items.find((x) => (footerPositions[x.label] || 0) === idx);
      return `<div class="summary-row">${f ? `<span>${show(f.value)}</span><span>${show(f.label)}</span>` : '&nbsp;'}</div>`;
    }).join('')}</div>`;
  }).join('')}</div>` : '';
  return `<div class="payroll"><div class="pay-title">${show(reportTitle || data.site_name || data.notice_title || 'فیش حقوقی')}</div>${month || year ? `<div class="pay-subtitle">فیش حقوق ${show(month)} ماه سال ${show(year)}</div>` : ''}${infoHtml}<div class="pay-head" style="grid-template-columns:${grid}">${cols.map((s) => `<div>${show(s)}</div>`).join('')}</div>${rows}${footer}</div>`;
}

const keys = ['name','code','totalWork','nightDays','overtime','fridayHours','leaveUsed','sickLeave','socialSick','unpaidLeave','bonusLeave','absence','deduction','dailyMission','unit','remainLeave'];
const right = ['name','totalWork','nightDays','absence','unpaidLeave','deduction','dailyMission','unit'];
const left = ['code','overtime','fridayHours','sickLeave','socialSick','bonusLeave','leaveUsed','remainLeave'];
function attendanceHtml(data) {
  const byKey = Object.fromEntries((data.fields || []).slice(0, 16).map((f, i) => [keys[i], f]));
  const pair = (k) => {
    const f = byKey[k];
    return `<div class="att-value ${k === 'name' || k === 'code' ? 'hilite' : ''}">${f ? show(f.value) : ''}</div><div class="att-label">${f ? show(f.label) : ''}</div>`;
  };
  return `<div class="attendance"><div class="att-top"><img src="/faipco-logo.png" alt=""><div class="att-title">فیش کارکرد</div><div class="att-subtitle">${show(data.month_year)}</div></div><div class="att-table">${right.map((k,i) => `<div class="att-row">${pair(left[i])}${pair(k)}</div>`).join('')}</div></div>`;
}

const printCss = `
@page{size:A4 portrait;margin:0}
*{box-sizing:border-box}
html,body{margin:0;background:#eee;color:#111;font-family:Tahoma,'DejaVu Sans',sans-serif}
.toolbar{background:#252225;padding:12px;text-align:center;position:sticky;top:0}
.toolbar button{font-family:inherit;background:#985a65;color:#fff;border:0;border-radius:5px;padding:10px 24px;cursor:pointer}
.sheet{background:#fff;width:210mm;min-height:297mm;margin:14px auto}
.payroll{padding:8mm;font-size:8pt}
.pay-title{text-align:center;font-size:12pt;font-weight:bold;margin-bottom:4pt}
.pay-subtitle{text-align:center;font-size:10pt;font-weight:bold;margin-bottom:6pt}
.info{display:grid;direction:ltr;background:#d3d3d3;border:.7pt solid black;margin-bottom:1.5mm}
.info>div{direction:rtl;text-align:right;border-right:.5pt solid black;padding:2pt 3pt;font-size:9pt;min-width:0}
.info>div:last-child{border-right:0}
.pay-head,.pay-row,.summary{display:grid;direction:ltr}
.pay-head{background:#d3d3d3;border:.7pt solid black;font-size:9pt;text-align:center;font-weight:bold}
.pay-head>div{padding:3pt 2pt;border-right:.7pt solid black}
.pay-head>div:last-child{border-right:0}
.pay-row{border-left:.7pt solid black;border-right:.7pt solid black;break-inside:avoid}
.pay-row:last-of-type{border-bottom:.7pt solid black}
.pay-cell{display:flex;direction:ltr;min-height:12pt;align-items:flex-start;padding:1.5pt 2pt;line-height:1.15;border-right:.7pt solid black;break-inside:avoid;font-size:8pt}
.pay-cell:last-child{border-right:0}
.pay-cell .val{width:40%;text-align:right;direction:rtl;overflow-wrap:anywhere}
.pay-cell .lbl{width:60%;text-align:right;direction:rtl;overflow-wrap:anywhere}
.summary{background:#d3d3d3;border:.6pt solid black;margin-top:1mm}
.summary>div{border-right:.5pt solid black;padding:2pt 3pt;font-size:8pt}
.summary>div:last-child{border-right:0}
.summary-row{display:flex;min-height:13pt;align-items:center;direction:ltr}
.summary-row span:first-child{width:58%;text-align:right;direction:rtl;overflow-wrap:anywhere}
.summary-row span:last-child{width:42%;text-align:right;direction:rtl;overflow-wrap:anywhere}
.attendance{padding:25mm 20mm;font-size:9.5pt}
.att-top{min-height:37mm;position:relative;text-align:center}
.att-top img{position:absolute;left:0;top:-6mm;width:26mm;height:26mm;object-fit:contain}
.att-title{font-size:15pt;font-weight:bold;color:#2b3990;line-height:19pt}
.att-subtitle{font-size:10.5pt;color:#333}
.att-table{margin-top:4mm;border:1.5pt solid #2b3990}
.att-row{display:grid;grid-template-columns:22.115% 27.885% 22.115% 27.885%;direction:ltr;break-inside:avoid}
.att-row>div{padding:4.5pt 4pt;min-height:25pt;display:flex;align-items:center;border-right:.5pt solid #c7cbe0;border-bottom:.5pt solid #c7cbe0}
.att-row:last-child>div{border-bottom:0}
.att-row>div:last-child{border-right:0}
.att-label{background:#fafbfd;font-weight:bold;color:#2b3990;direction:rtl;text-align:right}
.att-value{font-weight:bold;direction:rtl;justify-content:center;text-align:center;overflow-wrap:anywhere}
.hilite{background:#fafbfd}
@media print{html,body{margin:0!important;background:#fff!important}.toolbar{display:none!important}.sheet{margin:0;width:210mm;min-height:0}*{print-color-adjust:exact;-webkit-print-color-adjust:exact}}
`;

/** Called directly on click so that Safari can open the preview before any await. */
export async function openReceiptBrowserPrint(noticeId, kind) {
  const popup = window.open('', '_blank');
  if (!popup) throw new Error('POPUP_BLOCKED');
  popup.document.body.textContent = 'در حال دریافت فیش...';
  try {
    const data = await fetchReceiptPrintData(noticeId, kind);
    if (popup.closed) return;
    const html = kind === 'payroll' ? payrollHtml(data) : attendanceHtml(data);
    popup.document.open();
    popup.document.write(`<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${kind === 'payroll' ? 'فیش حقوقی' : 'فیش کارکرد'}</title><style>${printCss}</style></head><body><div class="toolbar"><button onclick="window.print()">چاپ / ذخیره PDF</button></div><div class="sheet">${html}</div></body></html>`);
    popup.document.close();
  } catch (error) {
    if (!popup.closed) popup.document.body.textContent = 'دریافت فیش با خطا مواجه شد. پنجره را ببندید و مجدداً تلاش کنید.';
    throw error;
  }
}
