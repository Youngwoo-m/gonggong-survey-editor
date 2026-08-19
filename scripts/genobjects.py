# -*- coding: utf-8 -*-
"""
규정 본문에 '그림'으로 들어 있는 표·수식을 XML 로 바꾼다.

국가법령정보센터 본문은 표와 수식을 이미지로 넣어 두어 (<img id="…">)
검색도 안 되고 고칠 수도 없다. 원본 HWPX 에는 진짜 표 객체와 수식 스크립트가
들어 있으므로, 그것을 읽어 다루기 쉬운 XML 로 바꾼다.

  · 표   → <table> / <row> / <cell>  (병합·머리행 유지)
  · 수식 → <equation> : 한글 수식 스크립트 + LaTeX 변환 시도

짝짓기: HWPX 를 문서 순서대로 훑으며 '제N조' 를 따라가고,
        그 조 안에서 나온 순서대로 본문의 <img id> 와 하나씩 맞춘다.

사용:  python scripts/genobjects.py <원본.hwpx> [규정id]
출력:  data/objects/<규정id>/<imgId>.xml
       data/objects/<규정id>/index.json
"""
import io, json, os, re, sys, zipfile
import xml.etree.ElementTree as ET

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
HP = "{http://www.hancom.co.kr/hwpml/2011/paragraph}"
JO = re.compile(r"^제\s*(\d+)\s*조")


# ---------- HWPX 읽기 ----------
def sections(path):
    with zipfile.ZipFile(path) as z:
        names = sorted(n for n in z.namelist() if re.match(r"Contents/section\d+\.xml$", n))
        for n in names:
            yield ET.fromstring(z.read(n))


def plain(el):
    """요소 아래 모든 글자 (표 안쪽 포함)"""
    return "".join(t.text or "" for t in el.iter(HP + "t"))


def para_text(p):
    """이 문단 자체의 글자 — 표·수식 안쪽은 빼고 본다"""
    out = []
    for run in p.findall(HP + "run"):
        if run.find(HP + "tbl") is not None or run.find(HP + "equation") is not None:
            continue
        for t in run.findall(HP + "t"):
            out.append(t.text or "")
    return "".join(out)


# ---------- 표 → XML ----------
# ── 원문의 부호 오기 바로잡기 ────────────────────────────────
#    허용오차·확률오차는 '기준값 ± 거리(변수)비례항' 이 옳다. 원문 표에는
#    + 로 적혀 있어 한쪽으로만 벌어지는 것처럼 읽힌다.
#    (개편안 제40조 등 · 개정 사유 '부호 수정')
#
#    '20mm + 4ppm · D' · '10cm + 2cm√N' · '(0.5m+100ppm.D)' 처럼
#    앞항과 뒷항이 모두 단위를 가진 자리의 + 만 바꾼다. 이미 '±(5mm + 1PPM×D)'
#    처럼 통째로 ± 가 붙은 것은 건드리지 아니한다.
UNIT = r"(?:mm|cm|m|km|ppm|PPM|초|″)"
RE_TOL = re.compile(rf"(\d[\d.]*\s*{UNIT}\s*)\+(\s*\d[\d.]*\s*{UNIT})")
cell_fixed = [0]
cell_samples = []


def fix_cell(text):
    s = str(text or "")
    if "±" in s:                       # 이미 부호가 붙어 있다
        return s
    out, n = RE_TOL.subn(r"\1±\2", s)
    if n:
        cell_fixed[0] += n
        if len(cell_samples) < 12:
            cell_samples.append(re.sub(r"\s+", " ", out)[:70])
    return out


def read_table(tbl):
    rows = []
    for tr in tbl.findall(HP + "tr"):
        cells = []
        for tc in tr.findall(HP + "tc"):
            addr = tc.find(HP + "cellAddr")
            span = tc.find(HP + "cellSpan")
            cells.append({
                "col": int(addr.get("colAddr", 0)) if addr is not None else 0,
                "row": int(addr.get("rowAddr", 0)) if addr is not None else 0,
                "colspan": int(span.get("colSpan", 1)) if span is not None else 1,
                "rowspan": int(span.get("rowSpan", 1)) if span is not None else 1,
                "header": tc.get("header", "0") == "1",
                "text": fix_cell("\n".join(
                    x for x in (plain(p).strip() for p in tc.iter(HP + "p")) if x
                )),
            })
        rows.append(cells)
    return {
        "kind": "table",
        "rows": rows,
        "rowCnt": int(tbl.get("rowCnt", len(rows))),
        "colCnt": int(tbl.get("colCnt", max((len(r) for r in rows), default=0))),
    }


# ---------- 수식 → LaTeX / 읽을 수 있는 글 ----------
# 한글 수식 편집기 낱말 → (LaTeX, 사람이 읽는 기호)
SYM = {
    "TIMES": (r"\times", "×"), "CDOT": (r"\cdot", "·"), "DIV": (r"\div", "÷"),
    "PM": (r"\pm", "±"), "MP": (r"\mp", "∓"),
    "LEQ": (r"\leq", "≤"), "GEQ": (r"\geq", "≥"), "NEQ": (r"\neq", "≠"),
    "APPROX": (r"\approx", "≒"), "SIM": (r"\sim", "~"), "PROP": (r"\propto", "∝"),
    "SUM": (r"\sum", "Σ"), "PROD": (r"\prod", "∏"), "INT": (r"\int", "∫"),
    "INF": (r"\infty", "∞"), "PARTIAL": (r"\partial", "∂"),
    "SIGMA": (r"\Sigma", "Σ"), "DELTA": (r"\Delta", "Δ"), "TRIANGLE": (r"\triangle", "Δ"),
    "OMEGA": (r"\Omega", "Ω"), "PI": (r"\pi", "π"), "ALPHA": (r"\alpha", "α"),
    "BETA": (r"\beta", "β"), "GAMMA": (r"\gamma", "γ"), "THETA": (r"\theta", "θ"),
    "LAMBDA": (r"\lambda", "λ"), "MU": (r"\mu", "μ"), "RHO": (r"\rho", "ρ"),
    "TAU": (r"\tau", "τ"), "PHI": (r"\phi", "φ"), "EPSILON": (r"\varepsilon", "ε"),
    "DEG": (r"^{\circ}", "°"), "PRIME": (r"'", "′"),
}
SYM_RE = re.compile(r"\b(" + "|".join(SYM) + r")\b", re.I)


def _pre(script):
    """한글 수식 스크립트의 공통 전처리"""
    s = str(script or "").strip()
    s = s.replace("`", " ").replace("~", " ")             # 백틱·물결 = 자간 조정
    s = re.sub(r"\s+", " ", s)
    return s


def to_latex(script):
    s = _pre(script)
    s = re.sub(r"\bLEFT\s*\|", r"\\left|", s, flags=re.I)
    s = re.sub(r"\bRIGHT\s*\|", r"\\right|", s, flags=re.I)
    s = re.sub(r"\bLEFT\s*([(\[{])", r"\\left\1", s, flags=re.I)
    s = re.sub(r"\bRIGHT\s*([)\]}])", r"\\right\1", s, flags=re.I)
    # eqalign{ a # b # c } → 여러 줄
    def _align(m):
        lines = [x.strip() for x in m.group(1).split("#") if x.strip()]
        return r"\begin{aligned}" + r" \\ ".join(lines) + r"\end{aligned}"
    s = re.sub(r"\beqalign\s*\{(.*?)\}", _align, s, flags=re.I | re.S)
    s = re.sub(r"\{([^{}]*)\}\s*over\s*\{([^{}]*)\}", r"\\frac{\1}{\2}", s, flags=re.I)
    s = re.sub(r"(\S+)\s+over\s+(\S+)", r"\\frac{\1}{\2}", s, flags=re.I)
    s = re.sub(r"\bsqrt\s*\{", r"\\sqrt{", s, flags=re.I)
    s = re.sub(r"\bsqrt\s+(\S+)", r"\\sqrt{\1}", s, flags=re.I)
    s = SYM_RE.sub(lambda m: SYM[m.group(1).upper()][0] + " ", s)
    return re.sub(r"\s+", " ", s).strip()


def to_readable(script):
    """라이브러리 없이 화면에 바로 띄울 수 있는 형태 (기호·분수를 글로)"""
    s = _pre(script)
    s = re.sub(r"\bLEFT\s*\|", "|", s, flags=re.I)
    s = re.sub(r"\bRIGHT\s*\|", "|", s, flags=re.I)
    s = re.sub(r"\bLEFT\s*", "", s, flags=re.I)
    s = re.sub(r"\bRIGHT\s*", "", s, flags=re.I)
    s = re.sub(r"\beqalign\s*\{(.*?)\}", lambda m: m.group(1), s, flags=re.I | re.S)
    s = re.sub(r"\{([^{}]*)\}\s*over\s*\{([^{}]*)\}", r"(\1) / (\2)", s, flags=re.I)
    s = re.sub(r"(\S+)\s+over\s+(\S+)", r"\1 / \2", s, flags=re.I)
    s = re.sub(r"\bsqrt\s*\{([^{}]*)\}", r"√(\1)", s, flags=re.I)
    s = re.sub(r"\bsqrt\s+(\S+)", r"√\1", s, flags=re.I)
    s = SYM_RE.sub(lambda m: SYM[m.group(1).upper()][1], s)
    s = re.sub(r"\s*#\s*", " ; ", s)
    s = s.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


def _script_of(eq):
    sc = eq.find(HP + "script")
    return (sc.text or "").strip() if sc is not None else ""


def make_equation(script, font=""):
    return {"kind": "equation", "script": script,
            "latex": to_latex(script), "readable": to_readable(script),
            "font": font}


def read_equation(eq):
    return make_equation(_script_of(eq), eq.get("font", ""))


def _floating(eq):
    """글자처럼 흐르지 아니하고 좌표로 떠 있는 조각인가"""
    pos = eq.find(HP + "pos")
    return pos is not None and pos.get("treatAsChar") == "0"


def _horz(eq):
    pos = eq.find(HP + "pos")
    return int((pos.get("horzOffset") if pos is not None else "0") or 0)


def plan_equations(root):
    """수식 조각을 무리 지어 합칠 계획을 세운다.

    한글은 여러 조각을 좌표로 나란히 놓아 수식 하나를 만든다.
    (보기: 제57조 — '[ΔN;ΔE;ΔU]' + '=' + '[행렬][ΔX;ΔY;ΔZ]')
    국가법령정보센터는 그 셋을 그림 하나로 찍었으므로 여기서도 하나로 본다.
    글자처럼 흐르는 것(treatAsChar="1")은 저마다 딴 수식이므로 두지 않는다.

    반환: {수식 element: 합친 객체}  — 딸린 조각은 값이 None
    """
    plan = {}
    for p in root.iter(HP + "p"):
        eqs = []
        for run in p.findall(HP + "run"):            # 표 안쪽 문단은 제 차례에 본다
            eqs.extend(run.findall(HP + "equation"))
        floats = [e for e in eqs if _floating(e)]
        for e in eqs:
            if e not in floats:
                plan[e] = read_equation(e)
        if not floats:
            continue
        head = floats[0]                              # 문서에 먼저 나온 조각이 대표
        if len(floats) == 1:
            plan[head] = read_equation(head)
            continue
        joined = " ".join(_script_of(e) for e in sorted(floats, key=_horz))
        plan[head] = make_equation(joined, head.get("font", ""))
        plan[head]["parts"] = len(floats)
        for e in floats[1:]:
            plan[e] = None
    return plan


# ---------- 문서 순서대로 훑기 ----------
TAIL = 400          # 자리를 맞출 때 견주는 앞 글의 길이
norm = lambda s: re.sub(r"\s+", "", str(s or ""))


def scan(root):
    """[(앞 글, 조번호, 객체), …] — 표 안쪽으로는 들어가지 않는다

    '앞 글' 은 그 객체 바로 앞까지 나온 본문이다. 국가법령정보센터 본문의
    <img> 앞 글과 견주어 자리를 맞추는 데 쓴다. 순서만으로 맞추면
    본문이 여러 객체를 그림 하나로 묶어 찍은 데(제29조)에서 어긋난다.
    """
    out, cur, buf = [], None, [""]
    plan = plan_equations(root)

    def emit(o):
        out.append((buf[0][-TAIL:], cur, o))

    def para(p):
        nonlocal cur
        m = JO.match(para_text(p).strip())
        if m:
            cur = int(m.group(1))
        for run in p.findall(HP + "run"):
            for child in run:
                tag = child.tag
                if tag == HP + "t":
                    buf[0] = (buf[0] + (child.text or ""))[-TAIL:]
                elif tag == HP + "tbl":
                    emit(read_table(child))        # 표 안쪽은 표의 일부다
                elif tag == HP + "equation":
                    o = plan.get(child, read_equation(child))
                    if o is not None:              # None 이면 앞 조각에 합쳐진 것이다
                        emit(o)
                else:
                    walk(child)

    def walk(el):
        for child in el:
            if child.tag == HP + "p":
                para(child)
            else:
                walk(child)

    walk(root)
    return out


# ---------- XML 쓰기 ----------
def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def table_xml(obj, img_id, jo, src):
    L = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<table id="{img_id}" article="제{jo}조" rows="{obj["rowCnt"]}" '
         f'cols="{obj["colCnt"]}" source="{esc(src)}">']
    for cells in obj["rows"]:
        L.append("  <row>")
        for c in cells:
            a = f' col="{c["col"]}" row="{c["row"]}"'
            if c["colspan"] != 1:
                a += f' colspan="{c["colspan"]}"'
            if c["rowspan"] != 1:
                a += f' rowspan="{c["rowspan"]}"'
            if c["header"]:
                a += ' header="1"'
            L.append(f"    <cell{a}>{esc(c['text'])}</cell>")
        L.append("  </row>")
    L.append("</table>")
    return "\n".join(L)


def equation_xml(obj, img_id, jo, src):
    return "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<equation id="{img_id}" article="제{jo}조" font="{esc(obj["font"])}" source="{esc(src)}">',
        f'  <script>{esc(obj["script"])}</script>',
        f'  <readable>{esc(obj["readable"])}</readable>',
        f'  <latex>{esc(obj["latex"])}</latex>',
        "</equation>",
    ])


# ---------- 본문의 <img id> ----------
RE_IMG = re.compile(r'<img\s+id="([\w.-]+)"\s*>(?:</img>)?')


def img_ids_by_article(reg):
    """{조번호: [(imgId, 그 앞까지의 본문), …]}"""
    out = {}
    def walk(ns):
        for n in ns:
            body = n.get("body") or ""
            m0 = re.search(r"\d+", n.get("legacyNo") or "")
            if m0 and RE_IMG.search(body):
                jo = int(m0.group())
                for m in RE_IMG.finditer(body):
                    out.setdefault(jo, []).append((m.group(1), body[:m.start()][-TAIL:]))
            walk(n.get("children") or [])
    walk(reg["tree"])
    return out


def common_tail(a, b):
    """두 글이 끝에서부터 몇 자나 같은가 (띄어쓰기는 없앤 뒤에 센다)"""
    a, b = norm(a), norm(b)
    n = min(len(a), len(b), 60)
    k = 0
    while k < n and a[-1 - k] == b[-1 - k]:
        k += 1
    return k


def pair(ids, cand):
    """본문 <img> 와 HWPX 객체를 앞 글로 맞춘다.

    앞 글이 8자 넘게 겹치면 그 자리로 본다. 못 맞춘 것은 앞뒤에 맞춘 자리
    사이에서 순서대로 채운다. 그래도 남으면 짝을 짓지 아니한다.
    """
    n, m = len(ids), len(cand)
    take = [None] * n
    used = set()
    for i, (_, before) in enumerate(ids):
        best, bestk = None, 8
        for j in range(m):
            if j in used:
                continue
            k = common_tail(before, cand[j][0])
            if k > bestk:
                best, bestk = j, k
        if best is not None:
            take[i] = best
            used.add(best)
    # 맞춘 자리 사이는 차례가 어긋나지 아니하도록 순서대로 메운다
    lo = -1
    for i in range(n):
        if take[i] is not None:
            lo = take[i]
            continue
        hi = next((take[x] for x in range(i + 1, n) if take[x] is not None), m)
        j = next((x for x in range(lo + 1, hi) if x not in used), None)
        if j is not None:
            take[i] = j
            used.add(j)
            lo = j
    return take


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    src = sys.argv[1]
    rid = sys.argv[2] if len(sys.argv) > 2 else "reg01"
    srcname = os.path.basename(src)

    objs = []
    for root in sections(src):
        objs.extend(scan(root))

    reg = json.load(io.open(os.path.join(DATA, f"{rid}.json"), encoding="utf-8"))
    imgs = img_ids_by_article(reg)

    # 사이에 글이 끼어 있지 아니한 이웃 객체는 한 덩어리로 찍힌 것이다.
    # (제209조 ⑤ — 좌표변환식 여러 줄이 그림 하나에 들어 있다)
    by_jo = {}
    for before, jo, o in objs:
        lst = by_jo.setdefault(jo, [])
        if (lst and lst[-1][0] == before
                and lst[-1][1]["kind"] == "equation" and o["kind"] == "equation"):
            prev = lst[-1][1]
            lst[-1] = (before, make_equation(f'{prev["script"]} # {o["script"]}',
                                             prev.get("font", "")))
            continue
        lst.append((before, o))

    outdir = os.path.join(DATA, "objects", rid)
    os.makedirs(outdir, exist_ok=True)
    # 이 스크립트가 만든 것만 지운다. 같은 폴더에는 genpics.py 의 그림과
    # genannexxml.py 의 별표 표, draft2025_tables.py 의 보고서 표도 함께 산다.
    for f in os.listdir(outdir):
        if re.fullmatch(r"\d+\.xml", f):
            os.remove(os.path.join(outdir, f))

    # 남의 항목은 그대로 두고 내 것만 갈아 끼운다
    index = {}
    ipath = os.path.join(outdir, "index.json")
    if os.path.exists(ipath):
        index = json.load(io.open(ipath, encoding="utf-8"))
        for k in [k for k in index if re.fullmatch(r"\d+", k)
                  and index[k].get("kind") in ("table", "equation")]:
            del index[k]

    made, miss, extra, unpaired = 0, [], 0, []
    for jo in sorted(imgs):
        ids = imgs[jo]
        cand = by_jo.get(jo, [])
        if len(cand) < len(ids):
            miss.append((jo, len(ids), len(cand)))
        take = pair(ids, cand)
        for k, (img_id, _) in enumerate(ids):
            j = take[k]
            if j is None:
                unpaired.append((jo, img_id))
                continue
            o = cand[j][1]
            if o["kind"] == "table":
                xml = table_xml(o, img_id, jo, srcname)
                meta = {"kind": "table", "article": f"제{jo}조",
                        "rows": o["rowCnt"], "cols": o["colCnt"],
                        "preview": " | ".join(c["text"].replace("\n", " ")
                                              for c in (o["rows"][0] if o["rows"] else []))[:120]}
            else:
                xml = equation_xml(o, img_id, jo, srcname)
                meta = {"kind": "equation", "article": f"제{jo}조",
                        "readable": o["readable"]}
            io.open(os.path.join(outdir, f"{img_id}.xml"), "w", encoding="utf-8").write(xml)
            index[img_id] = meta
            made += 1
        extra += max(0, len(cand) - len(ids))

    with io.open(os.path.join(outdir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    nt = sum(1 for v in index.values() if v["kind"] == "table")
    ne = sum(1 for v in index.values() if v["kind"] == "equation")
    print(f"원본  {srcname}")
    print(f"찾은 객체  표·수식 {len(objs)}개 / 조 {len(by_jo)}개")
    print(f"본문 <img>  {sum(len(v) for v in imgs.values())}개 / 조 {len(imgs)}개")
    print(f"변환 완료  {made}개 (표 {nt} · 수식 {ne}) → {outdir}")
    if cell_fixed[0]:
        print(f"부호 수정  허용오차·확률오차의 + 를 ± 로 바로잡은 자리 {cell_fixed[0]}곳")
        for s in cell_samples:
            print(f"   {s}")
    if miss:
        print(f"\n[짝을 못 채운 조 {len(miss)}개] — 본문 이미지가 HWPX 객체보다 많습니다")
        for jo, a, b in miss[:20]:
            print(f"   제{jo}조  img {a} vs 객체 {b}")
    if unpaired:
        print(f"\n[자리를 못 맞춘 것 {len(unpaired)}개] — 그림 그대로 둡니다")
        for jo, i in unpaired[:20]:
            print(f"   제{jo}조  {i}")
