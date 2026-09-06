/* ============================================================
   core/xlsx.js — 최소 XLSX 작성기 (외부 라이브러리 없음)
   inlineStr + 런(run) 을 써서 변경 어절에 밑줄·색을 넣는다.
   ============================================================ */
import { createZip } from "./zip.js?v=20260906w";

function esc(s) {
  const str = String(s ?? "");
  let out = "";
  for (let i = 0; i < str.length; i++) {
    const c = str.charCodeAt(i);
    if (c < 32 && c !== 9 && c !== 10 && c !== 13) continue;   // XML 금지 제어문자 제거
    const ch = str[i];
    out += ch === "&" ? "&amp;" : ch === "<" ? "&lt;" : ch === ">" ? "&gt;" : ch === '"' ? "&quot;" : ch;
  }
  return out;
}

const colName = (i) => {
  let s = "", n = i + 1;
  while (n > 0) { const r = (n - 1) % 26; s = String.fromCharCode(65 + r) + s; n = Math.floor((n - 1) / 26); }
  return s;
};

/* ---------- 스타일 ----------
   0 기본 / 1 표머리 / 2 본문(줄바꿈,위정렬) / 3 가운데(작게)
   4 제목 / 5 부제(회색) / 6 구분칸(가운데,굵게)
------------------------------ */
const STYLES = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="6">
<font><sz val="10"/><name val="맑은 고딕"/><family val="2"/></font>
<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/><family val="2"/></font>
<font><b/><sz val="15"/><color rgb="FF1F2C35"/><name val="맑은 고딕"/><family val="2"/></font>
<font><sz val="9"/><color rgb="FF7B8A92"/><name val="맑은 고딕"/><family val="2"/></font>
<font><b/><sz val="10"/><color rgb="FF1F2C35"/><name val="맑은 고딕"/><family val="2"/></font>
<font><sz val="9"/><color rgb="FF44585F"/><name val="맑은 고딕"/><family val="2"/></font>
</fonts>
<fills count="4">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF1F2C35"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEEF2F4"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border>
<left style="thin"><color rgb="FFC7D2D8"/></left><right style="thin"><color rgb="FFC7D2D8"/></right>
<top style="thin"><color rgb="FFC7D2D8"/></top><bottom style="thin"><color rgb="FFC7D2D8"/></bottom><diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="7">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="5" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="3" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="4" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="표준" xfId="0" builtinId="0"/></cellStyles>
<dxfs count="0"/>
<tableStyles count="0" defaultTableStyle="TableStyleMedium2" defaultPivotStyle="PivotStyleLight16"/>
</styleSheet>`;

const RPR_MARK = `<rPr><u/><b/><color rgb="FFC1502E"/><rFont val="맑은 고딕"/><family val="2"/><sz val="10"/></rPr>`;
const RPR_PLAIN = `<rPr><color rgb="FF1F2C35"/><rFont val="맑은 고딕"/><family val="2"/><sz val="10"/></rPr>`;

function cellXml(ref, cell) {
  if (cell === null || cell === undefined) return "";
  const s = typeof cell === "object" ? (cell.s ?? 0) : 0;

  if (typeof cell === "object" && Array.isArray(cell.runs)) {
    const runs = cell.runs.filter((r) => r.s !== "").map((r) =>
      `<r>${r.mark ? RPR_MARK : RPR_PLAIN}<t xml:space="preserve">${esc(r.s)}</t></r>`).join("");
    return `<c r="${ref}" s="${s}" t="inlineStr"><is>${runs || `<r>${RPR_PLAIN}<t/></r>`}</is></c>`;
  }
  const v = typeof cell === "object" ? cell.v : cell;
  if (typeof v === "number") return `<c r="${ref}" s="${s}"><v>${v}</v></c>`;
  if (v === "" || v === null || v === undefined) return `<c r="${ref}" s="${s}"/>`;
  return `<c r="${ref}" s="${s}" t="inlineStr"><is><t xml:space="preserve">${esc(v)}</t></is></c>`;
}

/**
 * @param {object} sheet { name, cols:[{w}], rows:[[cell,...]], rowHeights:{idx:h}, freeze:number }
 * @returns {Blob} xlsx
 */
export function writeXlsx(sheet) {
  const cols = (sheet.cols || []).map((c, i) =>
    `<col min="${i + 1}" max="${i + 1}" width="${c.w}" customWidth="1"/>`).join("");

  const rowsXml = sheet.rows.map((row, ri) => {
    const cells = row.map((c, ci) => cellXml(`${colName(ci)}${ri + 1}`, c)).join("");
    const h = sheet.rowHeights && sheet.rowHeights[ri];
    return `<row r="${ri + 1}"${h ? ` ht="${h}" customHeight="1"` : ""}>${cells}</row>`;
  }).join("");

  const freeze = sheet.freeze
    ? `<sheetView workbookViewId="0" showGridLines="0"><pane ySplit="${sheet.freeze}" topLeftCell="A${sheet.freeze + 1}" activePane="bottomLeft" state="frozen"/></sheetView>`
    : `<sheetView workbookViewId="0" showGridLines="0"/>`;

  const sheetXml = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetViews>${freeze}</sheetViews>
<sheetFormatPr defaultRowHeight="15"/>
${cols ? `<cols>${cols}</cols>` : ""}
<sheetData>${rowsXml}</sheetData>
<pageMargins left="0.4" right="0.4" top="0.6" bottom="0.6" header="0.3" footer="0.3"/>
<pageSetup paperSize="9" orientation="landscape" fitToWidth="1" fitToHeight="0"/>
</worksheet>`;

  const files = [
    { name: "[Content_Types].xml", data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>` },
    { name: "_rels/.rels", data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>` },
    { name: "xl/workbook.xml", data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="${esc(sheet.name || "Sheet1").slice(0, 31)}" sheetId="1" r:id="rId1"/></sheets>
</workbook>` },
    { name: "xl/_rels/workbook.xml.rels", data: `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>` },
    { name: "xl/styles.xml", data: STYLES },
    { name: "xl/worksheets/sheet1.xml", data: sheetXml },
  ];

  return createZip(files, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
}
