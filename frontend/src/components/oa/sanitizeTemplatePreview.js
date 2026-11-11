// Live preview must never inject raw, unsaved template HTML into the portal DOM.
// Only pre-approved structure, text, inline safe styles and local {{logo}} image survive.
const TAGS = new Set("div span p h1 h2 h3 strong b em i u small br hr table thead tbody tr th td img".split(" "));
const DROP = new Set("script style iframe object embed noscript template svg math head title xml select textarea button form canvas video audio link meta".split(" "));
const CSS = new Set(`text-align vertical-align font-size font-weight font-style color background-color border border-top border-right border-bottom border-left border-color border-width border-style border-radius border-collapse border-spacing padding padding-top padding-right padding-bottom padding-left margin margin-top margin-right margin-bottom margin-left width height max-width max-height min-width min-height display flex flex-direction flex-wrap justify-content align-items align-self gap line-height letter-spacing direction white-space object-fit text-decoration box-sizing table-layout overflow`.split(" "));
const displays = new Set("block inline inline-block flex inline-flex table table-row table-cell none".split(" "));
const risky = /url\s*\(|expression|javascript|vbscript|@import|\\|<|>|\/\*|\*\/|behavior|binding/i;
const safe = /^[\w\s#%.,()\-+'"!؀-ۿ]*$/u;
function styleClean(raw) {
  return String(raw || "").split(";").map((decl) => {
    const i = decl.indexOf(":");
    if (i < 0) return null;
    const key = decl.slice(0, i).trim().toLowerCase();
    const val = decl.slice(i + 1).trim();
    if (!CSS.has(key) || !val || val.length > 200 || risky.test(val) || !safe.test(val)) return null;
    if (key === "display" && !displays.has(val.toLowerCase())) return null;
    return `${key}: ${val}`;
  }).filter(Boolean).join("; ");
}
export function sanitizeTemplatePreview(raw) {
  if (!raw || typeof document === "undefined") return "";
  // Parse into an inert template; never append the unsanitized nodes to the active DOM.
  const template = document.createElement("template");
  template.innerHTML = String(raw).slice(0, 50000);
  const clean = document.createElement("div");
  function visit(node, parent, depth = 0) {
    if (depth > 40) return;
    if (node.nodeType === 3) { parent.appendChild(document.createTextNode(node.nodeValue)); return; }
    if (node.nodeType !== 1) return;
    const tag = node.tagName.toLowerCase();
    if (DROP.has(tag)) return;
    if (!TAGS.has(tag)) { Array.from(node.childNodes).forEach((child) => visit(child, parent, depth + 1)); return; }
    if (tag === "img" && (node.getAttribute("src") || "").replace(/\s/g, "") !== "{{logo}}") return;
    const element = document.createElement(tag);
    for (const attr of Array.from(node.attributes)) {
      const name = attr.name.toLowerCase();
      const value = attr.value.trim();
      if (name === "style") {
        const cleaned = styleClean(value);
        if (cleaned) element.setAttribute("style", cleaned);
      } else if (name === "dir" && ["ltr", "rtl", "auto"].includes(value.toLowerCase())) element.setAttribute("dir", value);
      else if (["colspan", "rowspan"].includes(name) && ["th", "td"].includes(tag) && /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 50) element.setAttribute(name, String(Number(value)));
      else if (tag === "img" && name === "src") element.setAttribute("src", "{{logo}}");
      else if (tag === "img" && name === "alt") element.setAttribute("alt", value.slice(0, 100));
      else if (tag === "img" && ["width", "height"].includes(name) && /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 2000) element.setAttribute(name, String(Number(value)));
    }
    parent.appendChild(element);
    if (!["br", "hr", "img"].includes(tag)) Array.from(node.childNodes).forEach((child) => visit(child, element, depth + 1));
  }
  Array.from(template.content.childNodes).forEach((node) => visit(node, clean));
  return clean.innerHTML;
}
export function safePreviewLayouts(layouts) {
  return Object.fromEntries(Object.entries(layouts || {}).map(([size, layout]) => [size, {
    ...layout,
    header: { ...layout.header, html: sanitizeTemplatePreview(layout.header?.html) },
    footer: { ...layout.footer, html: sanitizeTemplatePreview(layout.footer?.html) },
  }]));
}
