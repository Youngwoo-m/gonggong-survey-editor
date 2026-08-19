# -*- coding: utf-8 -*-
"""
뉴질랜드 지적측량규칙 2021 (Cadastral Survey Rules 2021, LI 2021/95) 을 색인한다.

뉴질랜드 법령 누리집(legislation.govt.nz)은 사람 확인 절차를 두어 기계가
받아 올 수 없다. 그래서 인터넷 아카이브(web.archive.org)에 갈무리된 같은
쪽을 받아 조문 단위로 세운다. 2024년 7월 1일 판(개정 2023 반영)이다.

  편 = Part / 별표(Schedule)
  장 = Subpart
  조 = rule (조문 번호와 제목)

본문의 산식(0.025 + (dist × 0.00005) m …)은 글줄로 살려 싣고, 표와 그림은
우리 앱의 표·수식 저장소에 넣은 뒤 본문에 <img id="…"> 자리표시를 둔다.
제목은 한국어 대역을 붙이고, 본문 대역은 옮긴 데까지 붙인다.

사용:  python scripts/genintl_csr2021.py
출력:  data/loc27.json · data/objects/loc27/* · library.json 갱신
"""
import io, json, os, re, sys, urllib.request

from bs4 import BeautifulSoup

import genintl_csr2021_ko as KOTBL
import genintl_csr2021_tr as TR

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
DOC_ID = "loc27"
OBJ = os.path.join(DATA, "objects", DOC_ID)
SNAP = ("http://web.archive.org/web/20251007072455/"
        "https://www.legislation.govt.nz/regulation/public/2021/0095/latest/whole.html")
ARCH = "http://web.archive.org"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch(url=SNAP):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=180).read()


def clean(t):
    """줄 바꿈 없는 빈칸(U+00A0)을 보통 빈칸으로 되돌린다"""
    t = re.sub(r"\s+", " ", str(t or "").replace(" ", " ")).strip()
    return re.sub(r"^[—–-]\s*", "", t)      # 절 제목 앞의 붙임표를 뗀다


def esc(t):
    return (str(t or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ───────────── 본문 뽑기 ─────────────

def body_of(el, objs, tag):
    """조문 한 덩이를 글로 뽑는다.

    p.text  는 보통 글줄, p.eqn-line 은 산식 글줄이다. 표와 그림은 저장소로
    빼고 그 자리에 <img id="…"> 를 남긴다 — 앱이 진짜 표를 그려 준다."""
    out, cap = [], ""

    def rec(node):
        nonlocal cap
        for ch in getattr(node, "children", []):
            if not getattr(ch, "name", None):
                continue
            cls = ch.get("class") or []
            if ch.name == "div" and "table" in cls and ch.find("table"):
                oid = f"{tag}t{sum(1 for o in objs if o['kind'] == 'table') + 1}"
                objs.append({"kind": "table", "id": oid, "el": ch.find("table"),
                             "caption": cap})
                out.append(f'<img id="{oid}">')
                cap = ""
                continue
            if ch.name == "div" and "graphic" in cls and ch.find("img"):
                src = ch.find("img").get("src") or ""
                oid = f"{tag}g{sum(1 for o in objs if o['kind'] == 'image') + 1}"
                objs.append({"kind": "image", "id": oid, "src": src,
                             "alt": clean(ch.find("img").get("alt"))})
                out.append(f'<img id="{oid}">')
                continue
            if ch.name in ("h6", "h5") and "table" in cls:
                cap = clean(ch.get_text(" ", strip=True))
                if cap:
                    out.append(cap)
                continue
            if ch.name == "p" and ("text" in cls or "eqn-line" in cls):
                t = clean(ch.get_text(" ", strip=True))
                if t:
                    out.append(t)
                continue
            if ch.name == "p" and "subprov" in cls:
                lab = clean(ch.get_text(" ", strip=True))
                if lab:
                    out.append(lab)
                continue
            if ch.name in ("div", "p", "blockquote"):
                rec(ch)
    rec(el)

    # '(1)' 처럼 번호만 있는 줄은 다음 글줄에 붙인다
    merged = []
    for line in out:
        if merged and re.fullmatch(r"\(\w{1,3}\)", merged[-1]):
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return "\n".join(merged).strip()


# ───────────── 표 → XML ─────────────

def table_xml(tab, oid, article, caption):
    """HTML 표를 우리 앱이 읽는 XML 로 바꾼다 (병합칸까지 살린다)"""
    grid, rows = {}, []
    for r, tr in enumerate(tab.find_all("tr")):
        cells = []
        col = 0
        for td in tr.find_all(["td", "th"]):
            while (r, col) in grid:
                col += 1
            cs = int(td.get("colspan") or 1)
            rs = int(td.get("rowspan") or 1)
            for dr in range(rs):
                for dc in range(cs):
                    grid[(r + dr, col + dc)] = True
            cells.append({"col": col, "row": r, "colspan": cs, "rowspan": rs,
                          "header": td.name == "th",
                          "text": clean(td.get_text(" ", strip=True))})
            col += cs
        if cells:
            rows.append(cells)
    ncol = max((c["col"] + c["colspan"] for row in rows for c in row), default=0)

    xml = [f'<?xml version="1.0" encoding="UTF-8"?>',
           f'<table id="{esc(oid)}" article="{esc(article)}" rows="{len(rows)}"'
           f' cols="{ncol}" source="{esc(caption or "Cadastral Survey Rules 2021")}">']
    for row in rows:
        xml.append("  <row>")
        for c in row:
            at = f'col="{c["col"]}" row="{c["row"]}"'
            if c["colspan"] > 1:
                at += f' colspan="{c["colspan"]}"'
            if c["rowspan"] > 1:
                at += f' rowspan="{c["rowspan"]}"'
            if c["header"]:
                at += ' header="1"'
            xml.append(f'    <cell {at}>{esc(c["text"])}</cell>')
        xml.append("  </row>")
    xml.append("</table>")
    preview = " | ".join(c["text"] for c in (rows[0] if rows else []))[:120]
    return "\n".join(xml), {"kind": "table", "article": article,
                            "rows": len(rows), "cols": ncol, "preview": preview}


# ───────────── 마디 만들기 ─────────────

RE_KONUM = re.compile(r"^(제\s*\d+\s*[편장절]|별표\s*\d+)\s*")
HEADKO = None


def hkey(t):
    return re.sub(r"\s+", " ", re.sub(r"[—–-]", " ", str(t or ""))).strip()


def head_ko(full):
    global HEADKO
    if HEADKO is None:
        HEADKO = {hkey(k): v for k, v in KOTBL.HEAD.items()}
    return HEADKO.get(hkey(full), "")


def bare(tt):
    """번호는 왼쪽 칸에 따로 보이므로 대역 제목에서는 뗀다"""
    return RE_KONUM.sub("", tt or "").strip()


def node(level, no, title, body, tt, nid):
    return {"id": nid, "level": level, "no": no, "branch": 0,
            "title": title, "body": body, "status": "유지", "legacyNo": "",
            "reason": "", "sourceRef": None, "history": [], "children": [],
            "collapsed": level != "편",
            "origTitle": title, "origBody": body,
            "transTitle": tt or "", "transBody": ""}


def head_of(el, sel):
    h = el.select_one(sel)
    if not h:
        return "", ""
    lab = h.select_one("span.label")
    label = lab.get_text(" ", strip=True) if lab else ""
    if lab:
        lab.extract()
    return clean(label), clean(h.get_text(" ", strip=True))


def tr_chars(ns):
    """대역을 붙인 조문의 원문 글자 수 — 얼마나 옮겼는지 셈한다"""
    n = 0
    for x in ns:
        if (x.get("transBody") or "").strip():
            n += len(x.get("body") or "")
        n += tr_chars(x["children"])
    return n


def main():
    soup = BeautifulSoup(fetch().decode("utf-8", "replace"), "html.parser")
    body = soup.select_one("div.body") or soup
    tree, pno, ano, objs = [], 0, 0, []
    cur_part = None

    def new_part(title, tt):
        nonlocal pno, cur_part
        pno += 1
        cur_part = node("편", pno, title, "", tt, f"i{DOC_ID}-p{pno}")
        tree.append(cur_part)
        return cur_part

    def add_rule(host, label, title, scope=""):
        """scope 는 별표 안의 조항을 가리킬 때 쓴다 — 규칙 번호와 겹치지 않게"""
        nonlocal ano
        ano += 1
        key = f"{scope}:{label}" if scope else str(label)
        tt = (KOTBL.RULE.get(key) or KOTBL.TERM.get(str(label))
              or KOTBL.CLAUSE.get(title, ""))
        n = node("조", ano, title, "", tt, f"i{DOC_ID}-a{ano}")
        n["legacyNo"] = label
        n["outlineNo"] = label
        n["transBody"] = TR.BODY.get(key, "")
        host["children"].append(n)
        return n

    head = new_part("Title and commencement", "제목과 시행일")
    head["outlineNo"] = "Rules"

    for el in body.find_all(["div"], recursive=True):
        cls = el.get("class") or []
        if "part" in cls and el.name == "div":
            label, title = head_of(el, "h2.part")
            full = f"{label} {title}".strip()
            p = new_part(title or full, bare(head_ko(full)))
            p["outlineNo"] = label
        elif "subpart" in cls:
            label, title = head_of(el, "h2.subpart, h3.subpart")
            if cur_part is not None:
                full = f"{label} {title}".strip()
                sub = node("장", len(cur_part["children"]) + 1,
                           title or full, "", bare(head_ko(full)),
                           f"i{DOC_ID}-s{pno}-{len(cur_part['children'])+1}")
                sub["outlineNo"] = label
                cur_part["children"].append(sub)
        elif "prov" in cls and "prov-body" not in cls:
            label, title = head_of(el, "h5.prov, h4.prov, h3.prov")
            host = cur_part or head
            if host["children"] and host["children"][-1]["level"] == "장":
                host = host["children"][-1]
            n = add_rule(host, label, title)
            pb = el.select_one("div.prov-body")
            mine = []
            n["body"] = body_of(pb, mine, f"r{label}") if pb else ""
            for o in mine:
                o["article"] = f"rule {label} {title}"
            objs.extend(mine)
            n["origBody"] = n["body"]

    # 별표(Schedule)
    for sc in soup.select("div.schedule"):
        label, title = head_of(sc, "h2.schedule, h1.schedule")
        full = f"{label} {title}".strip()
        p = new_part(title or full, bare(head_ko(full)))
        p["outlineNo"] = label
        p["isAnnex"] = True
        defs = sc.select(".def-term")
        if defs:                        # 별표 2 사전 — 낱말 하나를 조 하나로 세운다
            for t in defs:
                host = t.find_parent(["div", "p"])
                term = t.get_text(" ", strip=True)
                n = add_rule(p, term, term)
                # 정의가 '다음을 말한다—' 로 이어지면 뒤따르는 각 호까지 함께 담는다
                lines = [clean(host.get_text(" ", strip=True))]
                sib = host.find_next_sibling()
                while sib is not None:
                    cls = sib.get("class") or []
                    if sib.select_one(".def-term") or not (
                            "label-para" in cls or "def-para" in cls or "para" in cls):
                        break
                    got = clean(sib.get_text(" ", strip=True))
                    if got:
                        lines.append(got)
                    sib = sib.find_next_sibling()
                n["body"] = "\n".join(lines)
                n["origBody"] = n["body"]
            continue
        tag = "s" + re.sub(r"\D", "", label or "0")
        for el in sc.select("div.prov, div.clause"):
            lb, tt = head_of(el, "h5.prov, h4.prov, h5.clause, h4.clause")
            n = add_rule(p, lb, tt, scope=label)
            pb = el.select_one("div.prov-body, div.clause-body") or el
            mine = []
            n["body"] = body_of(pb, mine, f"{tag}c{lb}")
            for o in mine:
                o["article"] = f"{label} {tt}".strip()
            objs.extend(mine)
            n["origBody"] = n["body"]
        if not p["children"]:
            mine = []
            p["body"] = body_of(sc, mine, tag)
            for o in mine:
                o["article"] = full
            objs.extend(mine)
            p["transBody"] = TR.SCHED.get(label, "")

    tree[:] = [t for t in tree if t["children"] or t["body"]]
    for i, t in enumerate(tree, start=1):
        t["no"] = i

    # ── 표·그림을 저장소에 넣는다
    os.makedirs(OBJ, exist_ok=True)
    index, pics = {}, 0
    for o in objs:
        if o["kind"] == "table":
            xml, meta = table_xml(o["el"], o["id"], o.get("article", ""),
                                  o.get("caption", ""))
            io.open(os.path.join(OBJ, o["id"] + ".xml"), "w",
                    encoding="utf-8").write(xml)
            index[o["id"]] = meta
        else:
            url = o["src"]
            if url.startswith("/"):
                url = ARCH + url
            ext = os.path.splitext(url.split("?")[0])[1].lower() or ".jpg"
            fn = o["id"] + ext
            path = os.path.join(OBJ, fn)
            if not os.path.exists(path) or os.path.getsize(path) < 512:
                raw = None
                # 갈무리 시각을 콕 집으면 막힐 때가 있어 해(年)만 주고 다시 청한다
                for u in (url, re.sub(r"/web/\d+im_/", "/web/2021im_/", url)):
                    try:
                        raw = fetch(u)
                        if raw and len(raw) > 512:
                            break
                    except Exception:
                        raw = None
                if not raw:
                    print(f"   [그림 못 받음] {o['id']}")
                    continue
                io.open(path, "wb").write(raw)
            pics += 1
            index[o["id"]] = {"kind": "image", "file": fn,
                              "article": o.get("article", ""),
                              "preview": o.get("alt", "")}
    with io.open(os.path.join(OBJ, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    if not os.path.exists(os.path.join(OBJ, "annex-index.json")):
        io.open(os.path.join(OBJ, "annex-index.json"), "w",
                encoding="utf-8").write("{}")

    def cnt(ns, lv):
        c = 0
        for x in ns:
            if x["level"] == lv:
                c += 1
            c += cnt(x["children"], lv)
        return c

    def chs(ns):
        n = 0
        for x in ns:
            n += len(x["body"] or "")
            n += chs(x["children"])
        return n

    chars = chs(tree)
    stats = {k: cnt(tree, k) for k in ("편", "장", "절", "관", "조")}
    stats.update({"별표": sum(1 for t in tree if t.get("isAnnex")), "별지": 0, "변경": 0})

    doc = {
        "id": DOC_ID,
        "name": "Cadastral Survey Rules 2021 (LI 2021/95, LINZ)",
        "org": "LINZ (Surveyor-General)", "kind": "규칙", "no": "LI 2021/95",
        "promulgated": "20210726", "effective": "20240701", "lang": "en",
        "category": "intl",
        "source": ("https://www.legislation.govt.nz/regulation/public/2021/0095/latest/whole.html"
                   " — 사람 확인 절차 때문에 기계로 받을 수 없어, 인터넷 아카이브에"
                   f" 갈무리된 2025.10.07 판을 옮겼습니다: {SNAP}"),
        "stats": stats, "annex": [], "annexTree": [],
        "indexMode": "조문", "localFile": "",
        "tree": tree,
    }
    done = tr_chars(tree)
    doc["translated"] = {
        "lang": "en", "coverage": round(done / chars, 3) if chars else 0.0,
        "by": f"사람이 옮김 — 제목 전부, 본문 {done:,}/{chars:,}자",
    }
    with io.open(os.path.join(DATA, DOC_ID + ".json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))

    lp = os.path.join(DATA, "library.json")
    lib = json.load(io.open(lp, encoding="utf-8"))
    lib["regulations"] = [r for r in lib["regulations"] if r["id"] != DOC_ID]
    e = {k: doc[k] for k in ("id", "name", "org", "kind", "no", "effective",
                             "lang", "category", "source", "stats")}
    e.update(file=DOC_ID + ".json", hasFullText=True, annexCount=0,
             indexMode="조문", translated=doc["translated"])
    lib["regulations"].append(e)
    with io.open(lp, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)

    ntab = sum(1 for v in index.values() if v["kind"] == "table")
    print(f"OK  {DOC_ID}  편 {stats['편']} · 장 {stats['장']} · 조 {stats['조']}"
          f" · 본문 {chars:,}자 · 표 {ntab} · 그림 {pics}")
    print(f"    대역 {doc['translated']['by']}")


if __name__ == "__main__":
    main()
