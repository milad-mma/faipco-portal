import { fetchReceiptPrintData } from '../api/receiptPrint';
import { lightTheme, darkTheme } from '../theme';

// All receipt values are escaped: this window contains confidential employee data.
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const show = (v) => escapeHtml(v).replace(/\n/g, '<br>');
const sectionsFixed = ['وام', 'کسور', 'مزایا', 'سایر'];
const weights = { 'وام': 19, 'کسور': 24, 'مزایا': 24, 'سایر': 33 };
const footerPositions = { 'جمع مزایا': 0, 'جمع کسور': 0, 'جمع اقساط وام': 0, 'شماره حساب': 1, 'خالص پرداختی': 1 };

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
  // Match ReportLab: one grid row for totals and a second row for net pay/account.
  // A column can contain a value on either row independently of the input order.
  const footer = footers.length ? `<div class="summary" style="grid-template-columns:${grid}">${[0, 1].map((rowIdx) =>
    cols.map((s) => {
      const f = footers.find((x) => (cols.includes(x.column) ? x.column : cols[0]) === s && (footerPositions[x.label] ?? 0) === rowIdx);
      return `<div class="summary-row">${f ? `<span>${show(f.value)}</span><span>${show(f.label)}</span>` : '&nbsp;'}</div>`;
    }).join('')
  ).join('')}</div>` : '';
  return `<div class="payroll"><div class="pay-title">${show(reportTitle || data.site_name || data.notice_title || 'فیش حقوقی')}</div>${month || year ? `<div class="pay-subtitle">فیش حقوق ${show(month)} ماه سال ${show(year)}</div>` : ''}${infoHtml}<div class="pay-head" style="grid-template-columns:${grid}">${cols.map((s) => `<div>${show(s)}</div>`).join('')}</div>${rows ? `<div class="pay-body">${rows}</div>` : ''}${footer}</div>`;
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

// Only the preview UI is screen-responsive; the printed document always uses A4.
// The print template is intentionally kept separate from the existing server PDF.
const printCss = `
@page{size:A4 portrait;margin:0}
.receipt-preview-overlay,.receipt-preview-overlay *{box-sizing:border-box}
/* Preview chrome follows portal theme. The A4 document MUST keep its own light ink palette. */
.receipt-preview-overlay{position:fixed;inset:0;z-index:2147483000;display:flex;flex-direction:column;background:var(--receipt-surface);color:var(--receipt-text);font-family:'Vazirmatn',Tahoma,sans-serif;direction:rtl}
.receipt-preview-toolbar{flex-shrink:0;display:flex;align-items:center;justify-content:space-between;gap:16px;min-height:64px;padding:10px max(16px,env(safe-area-inset-right)) 10px max(16px,env(safe-area-inset-left));padding-top:calc(10px + env(safe-area-inset-top,0px));background:var(--receipt-paper);color:var(--receipt-text);border-bottom:1px solid var(--receipt-divider);font-family:'Vazirmatn',Tahoma,sans-serif;box-shadow:none}
.receipt-preview-toolbar-title{font-size:16px;font-weight:700;line-height:1.5;color:var(--receipt-text)}
.receipt-preview-controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.receipt-preview-button{appearance:none;display:inline-flex;justify-content:center;align-items:center;gap:8px;font-family:inherit;color:var(--receipt-on-primary);border:1px solid var(--receipt-primary);border-radius:6px;padding:8px 16px;cursor:pointer;background:var(--receipt-primary);font-size:13px;font-weight:600;line-height:1.5;min-height:38px;touch-action:manipulation;transition:background-color .15s ease,border-color .15s ease}
.receipt-preview-button:hover:not(:disabled){filter:brightness(.94)}
.receipt-preview-button:disabled{opacity:.55;cursor:wait}
.receipt-preview-close{background:transparent;color:var(--receipt-text);border-color:var(--receipt-divider)}
.receipt-preview-close:hover{background:var(--receipt-surface)}
.receipt-preview-button:focus-visible{outline:3px solid var(--receipt-primary);outline-offset:2px}
.receipt-preview-scroll{flex:1;min-height:0;overflow:auto;overscroll-behavior:contain;padding:14px 8px 25px}
.receipt-preview-loading{text-align:center;padding:24px;color:var(--receipt-text)}
.receipt-preview-frame{margin:0 auto;position:relative}
/* The portal dark theme sets white text on the overlay. Never inherit it into the white A4 sheet. */
.receipt-preview-sheet{position:absolute;top:0;left:0;transform-origin:top left;background:#fff!important;color:#171717!important;color-scheme:light;width:210mm;min-height:297mm;box-shadow:0 2px 15px #0002;direction:rtl;font-family:Tahoma,'DejaVu Sans',sans-serif}
.receipt-preview-sheet .payroll,.receipt-preview-sheet .pay-title,.receipt-preview-sheet .pay-subtitle,.receipt-preview-sheet .info,.receipt-preview-sheet .pay-head,.receipt-preview-sheet .pay-row,.receipt-preview-sheet .pay-cell,.receipt-preview-sheet .summary,.receipt-preview-sheet .summary-row,.receipt-preview-sheet .att-value{color:#171717!important}
.receipt-preview-sheet .att-label,.receipt-preview-sheet .att-title{color:#2b3990!important}
.receipt-preview-sheet .att-subtitle{color:#333!important}
.receipt-preview-overlay .payroll{padding:8mm;font-size:8pt}
.receipt-preview-overlay .pay-title{text-align:center;font-size:12pt;font-weight:bold;margin-bottom:4pt}
.receipt-preview-overlay .pay-subtitle{text-align:center;font-size:10pt;font-weight:bold;margin-bottom:6pt}
.receipt-preview-overlay .info{display:grid;direction:ltr;background:#d3d3d3;border:.7pt solid black;margin-bottom:1.5mm}
.receipt-preview-overlay .info>div{direction:rtl;text-align:right;border-right:.5pt solid black;padding:2pt 3pt;font-size:9pt;min-width:0}
.receipt-preview-overlay .info>div:last-child{border-right:0}
.receipt-preview-overlay .pay-head,.receipt-preview-overlay .pay-row,.receipt-preview-overlay .summary{display:grid;direction:ltr}
.receipt-preview-overlay .pay-head{background:#d3d3d3;border:.7pt solid black;font-size:9pt;text-align:center;font-weight:bold}
.receipt-preview-overlay .pay-head>div{padding:3pt 2pt;border-right:.7pt solid black}
.receipt-preview-overlay .pay-head>div:last-child{border-right:0}
.receipt-preview-overlay .pay-row{border-left:.7pt solid black;border-right:.7pt solid black;break-inside:avoid}
.receipt-preview-overlay .pay-body{border-bottom:.7pt solid black}
.receipt-preview-overlay .pay-cell{display:flex;direction:ltr;min-height:12pt;align-items:flex-start;padding:1.5pt 2pt;line-height:1.15;border-right:.7pt solid black;break-inside:avoid;font-size:8pt}
.receipt-preview-overlay .pay-cell:last-child{border-right:0}
.receipt-preview-overlay .pay-cell .val{width:40%;text-align:right;direction:rtl;overflow-wrap:anywhere}
.receipt-preview-overlay .pay-cell .lbl{width:60%;text-align:right;direction:rtl;overflow-wrap:anywhere}
.receipt-preview-overlay .summary{background:#d3d3d3;border:.6pt solid black;margin-top:1mm}
.receipt-preview-overlay .summary-row{border-right:.5pt solid black;border-bottom:.5pt solid black;padding:2pt 3pt;font-size:8pt;display:flex;min-height:17pt;align-items:center;direction:ltr}
.receipt-preview-overlay .summary-row:nth-child(4n){border-right:0}
.receipt-preview-overlay .summary-row:nth-last-child(-n+4){border-bottom:0}
.receipt-preview-overlay .summary-row span:first-child{width:58%;text-align:right;direction:rtl;overflow-wrap:anywhere}
.receipt-preview-overlay .summary-row span:last-child{width:42%;text-align:right;direction:rtl;overflow-wrap:anywhere}
.receipt-preview-overlay .attendance{padding:25mm 20mm;font-size:9.5pt}
.receipt-preview-overlay .att-top{position:relative;text-align:center;line-height:1.2}
.receipt-preview-overlay .att-top img{position:absolute;left:0;top:-6mm;width:26mm;height:26mm;object-fit:contain}
.receipt-preview-overlay .att-title{font-size:15pt;font-weight:400;color:#2b3990;line-height:19pt}
.receipt-preview-overlay .att-subtitle{font-size:10.5pt;font-weight:400;color:#333;line-height:14pt}
.receipt-preview-overlay .att-table{margin-top:4mm;border:1.5pt solid #2b3990}
.receipt-preview-overlay .att-row{display:grid;grid-template-columns:22.115% 27.885% 22.115% 27.885%;direction:ltr;break-inside:avoid}
.receipt-preview-overlay .att-row>div{padding:4.5pt 4pt;min-height:25pt;display:flex;align-items:center;border-right:.5pt solid #c7cbe0;border-bottom:.5pt solid #c7cbe0}
.receipt-preview-overlay .att-row:last-child>div{border-bottom:0}
.receipt-preview-overlay .att-row>div:last-child{border-right:0}
.receipt-preview-overlay .att-label{background:#fafbfd;font-weight:400;color:#2b3990;direction:rtl;text-align:right}
.receipt-preview-overlay .att-value{font-weight:400;direction:rtl;justify-content:center;text-align:center;overflow-wrap:anywhere}
.receipt-preview-overlay .hilite{background:#fafbfd}
@media(max-width:600px){.receipt-preview-toolbar{padding:calc(10px + env(safe-area-inset-top,0px)) 12px 10px;flex-wrap:wrap;gap:8px}.receipt-preview-toolbar-title{width:100%;text-align:right;font-size:15px}.receipt-preview-controls{width:100%;justify-content:stretch}.receipt-preview-button{flex:1;min-height:42px}.receipt-preview-scroll{padding:10px 4px 20px}}
@media print{
  body > :not(.receipt-preview-overlay){display:none!important}
  html,body{margin:0!important;padding:0!important;background:#fff!important;overflow:visible!important}
  .receipt-preview-overlay{position:static!important;display:block!important;background:#fff!important;inset:auto!important;overflow:visible!important}
  .receipt-preview-toolbar,.receipt-preview-loading{display:none!important}
  .receipt-preview-scroll{overflow:visible!important;padding:0!important;display:block!important}
  .receipt-preview-frame{width:210mm!important;height:auto!important;margin:0!important}
  .receipt-preview-sheet{position:static!important;transform:none!important;width:210mm!important;min-height:0!important;box-shadow:none!important;background:#fff!important;color:#171717!important;color-scheme:light}
  .receipt-preview-overlay *{print-color-adjust:exact;-webkit-print-color-adjust:exact}
}
`;

let closeCurrentPreview = null;

/** Display a responsive preview in this tab; printing is triggered by a real button click. */
export async function openReceiptBrowserPrint(noticeId, kind) {
  if (closeCurrentPreview) closeCurrentPreview();
  const previousFocus = document.activeElement;
  const previousOverflow = document.body.style.overflow;
  const style = document.createElement('style');
  style.textContent = printCss;
  style.dataset.faipcoReceiptPreview = '1';
  // Toolbar follows the actual portal theme. A4 content is separately locked to print colors.
  const savedMode = window.localStorage.getItem('faipco_theme_mode');
  const darkMode = savedMode === 'dark' || (savedMode !== 'light' && window.matchMedia?.('(prefers-color-scheme: dark)').matches);
  const palette = (darkMode ? darkTheme : lightTheme).palette;
  const overlay = document.createElement('section');
  overlay.style.setProperty('--receipt-surface', palette.background.default);
  overlay.style.setProperty('--receipt-paper', palette.background.paper);
  overlay.style.setProperty('--receipt-text', palette.text.primary);
  overlay.style.setProperty('--receipt-primary', palette.primary.main);
  overlay.style.setProperty('--receipt-on-primary', palette.primary.contrastText);
  overlay.style.setProperty('--receipt-divider', palette.divider);
  overlay.className = 'receipt-preview-overlay';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-label', kind === 'payroll' ? 'پیش‌نمایش فیش حقوقی' : 'پیش‌نمایش فیش کارکرد');
  const toolbar = document.createElement('header');
  toolbar.className = 'receipt-preview-toolbar';
  const title = document.createElement('div');
  title.className = 'receipt-preview-toolbar-title';
  title.textContent = kind === 'payroll' ? 'پیش‌نمایش فیش حقوقی' : 'پیش‌نمایش فیش کارکرد';
  const controls = document.createElement('div');
  controls.className = 'receipt-preview-controls';
  const printButton = document.createElement('button');
  printButton.type = 'button';
  printButton.className = 'receipt-preview-button';
  printButton.textContent = 'چاپ / ذخیره PDF';
  printButton.disabled = true;
  const closeButton = document.createElement('button');
  closeButton.type = 'button';
  closeButton.className = 'receipt-preview-button receipt-preview-close';
  closeButton.textContent = 'بستن';
  controls.append(printButton, closeButton);
  toolbar.append(title, controls);
  const scroll = document.createElement('main');
  scroll.className = 'receipt-preview-scroll';
  const loading = document.createElement('div');
  loading.className = 'receipt-preview-loading';
  loading.textContent = 'در حال آماده‌سازی پیش‌نمایش فیش...';
  scroll.append(loading);
  overlay.append(toolbar, scroll);

  let closed = false;
  let resizeObserver;
  let frame;
  let sheet;
  const onKey = (event) => {
    if (event.key === 'Escape') close();
    if (event.key === 'Tab') {
      const buttons = [printButton, closeButton].filter((button) => !button.disabled);
      if (event.shiftKey && document.activeElement === buttons[0]) { event.preventDefault(); buttons[buttons.length - 1].focus(); }
      else if (!event.shiftKey && document.activeElement === buttons[buttons.length - 1]) { event.preventDefault(); buttons[0].focus(); }
    }
  };
  function updateScale() {
    if (!frame || !sheet || closed) return;
    const nativeWidth = sheet.offsetWidth;
    const availableWidth = scroll.clientWidth - 8;
    if (!nativeWidth || availableWidth <= 0) return;
    const scale = Math.min(1, availableWidth / nativeWidth);
    sheet.style.transform = `scale(${scale})`;
    frame.style.width = `${nativeWidth * scale}px`;
    frame.style.height = `${sheet.scrollHeight * scale}px`;
  }
  function close() {
    if (closed) return;
    closed = true;
    resizeObserver?.disconnect();
    window.removeEventListener('resize', updateScale);
    document.removeEventListener('keydown', onKey, true);
    overlay.remove();
    style.remove();
    document.body.style.overflow = previousOverflow;
    if (closeCurrentPreview === close) closeCurrentPreview = null;
    if (previousFocus?.isConnected) previousFocus.focus();
  }
  closeCurrentPreview = close;
  closeButton.addEventListener('click', close);
  // Same-document print works directly from the user's click and avoids popup blockers.
  printButton.addEventListener('click', () => {
    if (!closed && !printButton.disabled) window.print();
  });
  document.head.append(style);
  document.body.append(overlay);
  document.body.style.overflow = 'hidden';
  document.addEventListener('keydown', onKey, true);
  closeButton.focus();
  try {
    const data = await fetchReceiptPrintData(noticeId, kind);
    if (closed) return;
    const html = kind === 'payroll' ? payrollHtml(data) : attendanceHtml(data);
    frame = document.createElement('div');
    frame.className = 'receipt-preview-frame';
    sheet = document.createElement('div');
    sheet.className = 'receipt-preview-sheet';
    sheet.innerHTML = html; // Every field interpolated by the renderers is escaped.
    frame.append(sheet);
    loading.replaceWith(frame);
    printButton.disabled = false;
    resizeObserver = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(updateScale) : null;
    resizeObserver?.observe(scroll);
    window.addEventListener('resize', updateScale);
    updateScale();
  } catch (error) {
    close();
    throw error;
  }
}
