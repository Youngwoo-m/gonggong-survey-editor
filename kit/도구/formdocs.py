# -*- coding: utf-8 -*-
r"""개정(안)과 신구대조표를 Form 폴더의 양식에 얹어 짓는다.

여태는 HTML 을 지어 한/글에게 넘겼다. 그러면 서식이 한/글의 짐작이 된다.
여기서는 양식 파일의 문단과 표 칸을 본으로 삼아 복제하며 글만 채운다.

  개정(안)      Form\01.개정안\[양식] 규정 개정(안).hwpx
  신구대조표     Form\02.신구대조표\[양식] 규정.신구대조표.hwpx

양식을 뜯어 보니 문단 종류마다 문단모양이 정해져 있었다.

    고시번호  paraPr 3   ← 첫 문단이라 쪽 설정(secPr)을 이고 있다
    제목      paraPr 29
    장 제목   paraPr 1
    조문      paraPr 25  ← 조 제목과 첫 문장이 한 줄
    호(1. 2.) paraPr 8
    항(① ②)  paraPr 31
    부칙      paraPr 1

그래서 종류마다 본을 하나씩 떠 두고 조 수만큼 복제한다. 규정이 달라져도
조 수만 달라질 뿐 서식은 양식 그대로다.
"""
import difflib
import io
import os
import re

import formfill as FF

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BASE = os.path.dirname(os.path.dirname(ROOT))          # …\2026.공공측량.품관원

# 양식과 자료가 어디 있는지. 이 컴퓨터에서는 Form 폴더와 data 폴더지만, 웹에서
# 받은 꾸러미 안에서 돌 때에는 꾸러미가 제 안의 자리를 알려 준다.
FORM = os.environ.get("FORM_DIR") or os.path.join(BASE, "Form")
DATA = os.environ.get("DATA_DIR") or os.path.join(ROOT, "data")


def _tpl(sub, name):
    """양식 파일 찾기 — 하위 폴더에 있어도, 바로 밑에 있어도 찾는다"""
    p = os.path.join(FORM, sub, name)
    if os.path.exists(p):
        return p
    flat = os.path.join(FORM, name)
    return flat if os.path.exists(flat) else p


TPL_DRAFT = _tpl("01.개정안", "[양식] 규정 개정(안).hwpx")
TPL_COMPARE = _tpl("02.신구대조표", "[양식] 규정.신구대조표.hwpx")
TPL_REASON = _tpl("03.개정사유서", "[양식] 작업규정 개정안_개정사유서.hwpx")

RE_IMG = re.compile(r"<img\s+id=\"([^\"]+)\">\s*</img>|<img\s+id=\"([^\"]+)\"\s*/?>")
RE_PROV = re.compile(r"<prov[^>]*>.*?</prov>", re.S)

RE_CHAP = re.compile(r"^제\d+장")
RE_ART = re.compile(r"^제\d+조")
RE_ITEM = re.compile(r"^\d+\.")
RE_CLAUSE = re.compile(r"^[①-⑳]")


# ────────────────────────────────── 갈래 나누기
def top_paras(f):
    """맨 바깥 문단만 — 표 안의 문단은 빼고"""
    out, last = [], -1
    for p in f.paras():
        if p[0] >= last:
            out.append(p)
            last = p[1]
    return out


def protos(f):
    """양식에서 종류마다 본을 하나씩 뜬다"""
    tops = top_paras(f)
    P = {"tops": tops, "head": tops[0][5]}
    for _s, _e, _pp, _cp, t, blk, nested in tops:
        if nested and "tbl" not in P:
            P["tbl"] = blk
        if not t and "blank" not in P:
            P["blank"] = blk
        if RE_CHAP.match(t) and "chap" not in P:
            P["chap"] = blk
        elif RE_ART.match(t) and "art" not in P:
            P["art"] = blk
        elif RE_ITEM.match(t) and "item" not in P:
            P["item"] = blk
        elif RE_CLAUSE.match(t) and "clause" not in P:
            P["clause"] = blk
        elif t == "부칙" and "supp" not in P:
            P["supp"] = blk
    P.setdefault("clause", P.get("item"))
    P.setdefault("item", P.get("art"))
    P.setdefault("blank", P.get("item"))
    P.setdefault("supp", P.get("chap"))
    # 제목은 첫 문단 다음의 글 있는 문단 가운데 장ㆍ조가 아닌 것
    for _s, _e, _pp, _cp, t, blk, nested in tops[1:]:
        if t and not nested and not RE_CHAP.match(t) and not RE_ART.match(t):
            P["title"] = blk
            break
    return P


def body_lines(text):
    """조문 본문 → [줄] · 표 자리는 ('tbl', id) 로"""
    t = RE_PROV.sub("", str(text or ""))
    out, last = [], 0
    for m in RE_IMG.finditer(t):
        for s in t[last:m.start()].split("\n"):
            if s.strip():
                out.append(s.strip())
        out.append(("tbl", m.group(1) or m.group(2)))
        last = m.end()
    for s in t[last:].split("\n"):
        if s.strip():
            out.append(s.strip())
    return out


def line_proto(P, s):
    if RE_CLAUSE.match(s):
        return P["clause"]
    if RE_ITEM.match(s):
        return P["item"]
    return P["item"]


# ────────────────────────────────── 본문 속 개체 (표ㆍ수식)
#
# 조문 본문에는 <img id="…"> 로 개체 자리가 박혀 있고, 실제 내용은 objects\
# 에 XML 로 있다. 두 가지다.
#
#     <table>     263개   행과 칸
#     <equation>    9개   한/글 수식 script 가 그대로 들어 있다
#
# 여태 표만 되살리고 수식은 말없이 빠뜨렸다. 수식은 아래 본을 써서 한/글
# 수식 개체로 되살린다.

def object_src(oid, regid):
    """개체 XML 을 찾아 읽는다 — 못 찾으면 None"""
    cand = [os.path.join(DATA, "objects", rid, oid + ".xml")
            for rid in (regid, "draftUav", "draft2025", "reg01", "reg12")]
    cand.append(os.path.join(DATA, "objects", oid + ".xml"))   # 꾸러미는 평평하다
    for p in cand:
        if os.path.exists(p):
            return io.open(p, encoding="utf-8").read()
    return None


# 한/글 수식 개체의 본. Form\09.현행원본\공공측량 작업규정(2025).hwpx 에서
# 그대로 떠 왔다 — 그 파일이 이 수식들의 출처다. script 만 갈아 끼운다.
EQ_PROTO = (
    '<hp:equation id="{id}" zOrder="{z}" numberingType="EQUATION"'
    ' textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0"'
    ' dropcapstyle="None" version="Equation Version 60" baseLine="66"'
    ' textColor="#000000" baseUnit="1000" lineMode="CHAR" font="HYhwpEQ">'
    '<hp:sz width="{w}" widthRelTo="ABSOLUTE" height="2250"'
    ' heightRelTo="ABSOLUTE" protect="0"/>'
    '<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1"'
    ' allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" horzRelTo="PARA"'
    ' vertAlign="TOP" horzAlign="LEFT" vertOffset="0" horzOffset="0"/>'
    '<hp:outMargin left="56" right="56" top="0" bottom="0"/>'
    "<hp:shapeComment>수식입니다.</hp:shapeComment>"
    "<hp:script>{s}</hp:script></hp:equation>")

_eq_no = [0]


def object_equation(P, oid, regid):
    """objects 의 <equation> → 한/글 수식을 담은 <hp:p>. 못 만들면 None"""
    src = object_src(oid, regid)
    if not src or "<equation" not in src:
        return None
    m = re.search(r"<script>(.*?)</script>", src, re.S)
    if not m:
        m = re.search(r"<readable>(.*?)</readable>", src, re.S)
    if not m:
        return None
    script = m.group(1).strip()
    _eq_no[0] += 1
    # 폭은 글자 수로 어림한다 — 한/글이 열 때 다시 잰다
    eq = EQ_PROTO.format(id=1990000000 + _eq_no[0], z=100 + _eq_no[0],
                         w=max(2000, len(script) * 500), s=script)
    proto = FF.strip_seg(P["item"])
    i = proto.find(">") + 1
    r = re.search(r"<hp:run\b[^>]*?/?>", proto)
    run = r.group(0) if r else '<hp:run charPrIDRef="0">'
    if run.endswith("/>"):
        run = run[:-2] + ">"
    return proto[:i] + run + eq + "</hp:run></hp:p>"


def object_table(P, oid, regid):
    """objects 에 담아 둔 표 → 양식의 표를 본으로 삼은 <hp:p>"""
    src = object_src(oid, regid)
    if src is None or "<table" not in src or "tbl" not in P:
        return None
    rows = [re.findall(r"<cell[^>]*>([^<]*)</cell>", r)
            for r in re.findall(r"<row>(.*?)</row>", src, re.S)]
    if not rows:
        return None

    blk = P["tbl"]
    span = FF.table_span(blk)
    if not span:
        return None
    tbl = blk[span[0]:span[1]]
    trs = FF.top_rows(tbl)
    head_proto = FF.RowProto(trs[0])
    data_proto = FF.RowProto(trs[1] if len(trs) > 1 else trs[0])

    made = []
    for ri, cells in enumerate(rows):
        pr = head_proto if ri == 0 else data_proto
        cols = [FF.remake(pr.para_proto(ci), [(None, c)])
                for ci, c in enumerate(cells)]
        made.append(pr.make(ri, cols))
    return blk[:span[0]] + FF.retable(tbl, "".join(made), len(rows)) + blk[span[1]:]


# ────────────────────────────────── 개정(안)
def build_draft(dst, tree, regname, regid, meta, supp=None, walk=None):
    """조문 전문을 양식에 얹는다 → 만든 파일 길"""
    f = FF.Form(TPL_DRAFT)
    P = protos(f)
    org = (meta or {}).get("org") or "국토지리정보원"
    kind = (meta or {}).get("kind") or "고시"

    # 첫 문단은 쪽 설정(secPr)을 이고 있으므로 글자만 바꾼다
    out = [FF.retext(P["head"], "%s %s 제○○○○-○○○○호" % (org, kind)),
           FF.remake(P["blank"], []),
           FF.remake(P["title"], [(None, "%s 개정(안)" % regname)])]

    # 조문 본문에 쓸 보통 글씨 — 호(1. 2. …) 문단의 글자모양을 가져다 쓴다
    m = re.search(r'charPrIDRef="(\d+)"', P.get("item") or "")
    body_char = m.group(1) if m else None

    only_annex = set()
    for _d, x in walk(tree):
        ch = x.get("children") or []
        if ch and all(c.get("annexRef") for c in ch):
            only_annex.add(id(x))

    for _d, x in walk(tree):
        if x.get("isDeleted") or x.get("status") == "삭제" or x.get("annexRef"):
            continue
        if id(x) in only_annex:
            continue
        lv, no, ti = x.get("level"), x.get("no"), x.get("title") or ""
        if lv in ("편", "장", "절", "관"):
            out.append(FF.remake(P["chap"], [(None, "제%s%s %s" % (no, lv, ti))]))
            continue
        if lv != "조":
            continue
        br = "의%s" % x["branch"] if x.get("branch") else ""
        lead = "제%s조%s(%s)" % (no, br, ti)
        lines = body_lines(x.get("body"))
        # 조 제목 뒤에 첫 줄을 이어 붙인다 — 고시의 꼴이다
        first = ""
        if lines and not isinstance(lines[0], tuple):
            first = lines.pop(0)
        # 굵게 하는 것은 조 번호와 제목까지다. 이어 붙인 본문은 보통 글씨로
        # 둔다 — 현행 고시가 그렇게 되어 있다.
        runs = [(None, lead)]
        if first:
            runs.append((body_char, " " + first))
        out.append(FF.remake(P["art"], runs))
        for s in lines:
            if isinstance(s, tuple):
                # 표인지 수식인지는 개체 XML 을 보고 가린다
                t = object_table(P, s[1], regid) or object_equation(P, s[1], regid)
                if t:
                    out.append(t)
                else:
                    out.append(FF.remake(line_proto(P, "x"),
                                         [(None, "[개체 %s 를 찾지 못했습니다]"
                                           % s[1])]))
                continue
            out.append(FF.remake(line_proto(P, s), [(None, s)]))

    if supp:
        out.append(FF.remake(P["blank"], []))
        out.append(FF.remake(P["supp"], [(None, "부칙")]))
        for a in ([supp] if isinstance(supp, str) else supp):
            for ln in str(a).split("\n"):
                if ln.strip():
                    out.append(FF.remake(P["art"], [(None, ln.strip())]))

    tops = P["tops"]
    f.xml = f.xml[:tops[0][0]] + "".join(out) + f.xml[tops[-1][1]:]
    return f.save(dst)


# ────────────────────────────────── 신구대조표
KEEP, LONG = 3, 7


def _tok(s):
    return [t for t in re.split(r"(\s+)", str(s or "")) if t != ""]


def _words(ts):
    return [t for t in ts if not t.isspace()]


def _shrink(ts, first, last):
    w = _words(ts)
    if len(w) <= LONG:
        return "".join(ts)
    lead = ts[0] if ts[0].isspace() else ""
    rear = ts[-1] if len(ts) > 1 and ts[-1].isspace() else ""
    head = "" if first else " ".join(w[:KEEP]) + " "
    tail = "" if last else " " + " ".join(w[-KEEP:])
    return lead + head + "_" + tail + rear


def _coalesce(ops, a):
    """고친 도막 사이에 낀 공백뿐인 도막을 합친다 — 붉은 조각이 잘게 쪼개지지 않게"""
    out, i = list(ops), 1
    while i < len(out) - 1:
        t, i1, i2, _j1, _j2 = out[i]
        if (t == "equal" and not _words(a[i1:i2])
                and out[i - 1][0] != "equal" and out[i + 1][0] != "equal"):
            p, n = out[i - 1], out[i + 1]
            out[i - 1:i + 2] = [("replace", p[1], n[2], p[3], n[4])]
            continue
        i += 1
    return out


def diff_runs(was, now, red):
    """(현행 runs, 수정(안) runs) — 그대로인 데는 _ 로 줄이고 새 글은 붉게.

    사례가 적어 둔 표기 원칙 그대로다 —
      「변경 없는 부분은 "_"로 생략 표기, 개정안 문구는 붉은색 표시」"""
    a, b = _tok(was), _tok(now)
    ops = _coalesce(
        difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes(), a)
    old, new = [], []
    for i, (tag, i1, i2, j1, j2) in enumerate(ops):
        first, last = i == 0, i == len(ops) - 1
        if tag == "equal":
            piece = _shrink(a[i1:i2], first, last)
            old.append((None, piece))
            new.append((None, piece))
        else:
            if i1 < i2:
                old.append((None, "".join(a[i1:i2])))
            if j1 < j2:
                new.append((red, "".join(b[j1:j2])))
    return old, new


def split_paras(runs):
    """줄바꿈에서 문단을 가른다 → [[(글자모양, 글), …], …]"""
    out, cur = [], []
    for cid, t in runs:
        parts = str(t).split("\n")
        for k, s in enumerate(parts):
            if k:
                out.append(cur)
                cur = []
            if s:
                cur.append((cid, s))
    out.append(cur)
    return [p for p in out if p] or [[]]


def build_compare(dst, tree, regname, regid, walk, reason_lines):
    """신구대조표를 양식에 얹는다 → (만든 파일 길, 대조한 조 수)"""
    f = FF.Form(TPL_COMPARE)
    tops = top_paras(f)
    title = tops[0][5]
    tblp = next(p[5] for p in tops if p[6])

    span = FF.table_span(tblp)
    tbl = tblp[span[0]:span[1]]
    trs = FF.top_rows(tbl)
    # 본으로 쓸 행은 칸 안에 표가 없는 것을 고른다. 양식의 몇몇 행은 칸 안에
    # 또 표를 담고 있어(시료 보존방법 표 따위) 본으로 삼으면 그 표까지 딸려
    # 온다.
    head_row = trs[0]
    plain = next((t for t in trs[1:] if "<hp:tbl " not in t), trs[1])
    data = FF.RowProto(plain)
    body_char = re.search(r'charPrIDRef="(\d+)"', data.para_proto(2)).group(1)
    head_char = re.search(r'charPrIDRef="(\d+)"', head_row).group(1)
    red = f.new_charpr(body_char, textColor="#FF0000")

    rows, n = [head_row], 0
    for _d, x in walk(tree):
        if x.get("level") != "조" or x.get("annexRef"):
            continue
        st = x.get("status") or "유지"
        if st == "유지" and not x.get("legacyNo"):
            continue
        n += 1
        br = "의%s" % x["branch"] if x.get("branch") else ""
        jo = "제%s조%s" % (x.get("no"), br)
        old_head = x.get("legacyNo") or "<신 설>"
        new_head = "%s(%s)" % (jo, x.get("title") or "")
        w = RE_PROV.sub("", x.get("wasBody") or "")
        m = RE_PROV.sub("", x.get("body") or "")
        w, m = RE_IMG.sub("[표]", w), RE_IMG.sub("[표]", m)
        ow, nw = diff_runs(w, m, red)

        # 본으로 뜬 문단의 글자모양은 굵다 — 양식에서 그 자리가 소제목이라
        # 그렇다. 본문은 보통 글씨(개정 사유 칸의 글자모양)로 맞춘다.
        def plainly(runs):
            return [(cid or body_char, t) for cid, t in runs]

        c0 = [FF.remake(data.para_proto(0), [(head_char, old_head)])]
        c0 += ([FF.remake(data.para_proto(0), plainly(r))
                for r in split_paras(ow)] if w else [])
        c1 = [FF.remake(data.para_proto(1),
                        [(red if st == "신설" else head_char, new_head)])]
        c1 += [FF.remake(data.para_proto(1), plainly(r)) for r in split_paras(nw)]
        why = reason_lines(x) or [st]
        c2 = [FF.remake(data.para_proto(2), [(body_char, "- " + s)]) for s in why]
        rows.append(data.make(n, ["".join(c0), "".join(c1), "".join(c2)]))

    newtbl = FF.retable(tbl, "".join(rows), len(rows))
    # 제목 문단도 쪽 설정(가로쪽)을 이고 있다 — 글자만 바꾼다
    body = (FF.retext(title, "[붙임] %s 일부 개정(안) 신·구대조표" % regname)
            + FF.remake(title, [(body_char,
                                 "표기 원칙 — 변경 없는 부분은 “_”로 생략 표기, "
                                 "개정안 문구는 붉은색 표시")])
            + tblp[:span[0]] + newtbl + tblp[span[1]:])
    f.xml = f.xml[:tops[0][0]] + body + f.xml[tops[-1][1]:]
    return f.save(dst), n


# ────────────────────────────────── 개정사유서
#
# 양식(Form\03.개정사유서)의 문단 종류는 이렇다.
#
#     제목        paraPr 71   ← 첫 문단이라 쪽 설정을 이고 있다
#     절 제목     paraPr 8    (1. 개정 목적 …)
#     항 제목     paraPr 2    (가. 나. …)
#     본문        paraPr 42
#     개조식      paraPr 7    (6. 기대 효과)
#     빈 줄       paraPr 1
#     표 4개                  (2절ㆍ3절ㆍ4절ㆍ5절)
#
# 사람이 쓴 원고가 있으면 그것을 얹는 편이 낫다(Report\scripts\build_from_form.py).
# 여기서 짓는 것은 원고가 아직 없을 때 — 자료에서 뽑을 수 있는 데까지 채우고,
# 줄글로 써야 하는 6ㆍ7절은 무엇을 쓸 자리인지 적어 둔다.

REASON_PP = {"title": "71", "sec": "8", "sub": "2",
             "body": "42", "bullet": "7", "blank": "1"}


def reason_protos(f):
    """개정사유서 양식에서 종류마다 본을 뜬다 → (본 사전, 표 본 넷, 문단들)"""
    tops = top_paras(f)
    P, tbl = {}, []
    for _s, _e, pp, _cp, _t, blk, nested in tops:
        if nested:
            tbl.append(blk)
            continue
        for k, v in REASON_PP.items():
            if pp == v and k not in P:
                P[k] = blk
    P.setdefault("sub", P.get("sec"))
    P.setdefault("bullet", P.get("body"))
    P.setdefault("blank", P.get("body"))
    return P, tbl, tops


def _tbl_of(blk, rows, widths_from=1):
    """표 본 하나 → 행을 갈아 끼운 <hp:p>. rows 는 [[칸 글, …], …] (첫 줄이 머리)"""
    span = FF.table_span(blk)
    tbl = blk[span[0]:span[1]]
    trs = FF.top_rows(tbl)
    head = FF.RowProto(trs[0])
    data = FF.RowProto(trs[min(widths_from, len(trs) - 1)])
    made = []
    for ri, cells in enumerate(rows):
        pr = head if ri == 0 else data
        cols = []
        for ci, c in enumerate(cells):
            lines = c if isinstance(c, list) else [c]
            cols.append("".join(FF.remake(pr.para_proto(ci), [(None, str(x))])
                                for x in (lines or [""])))
        made.append(pr.make(ri, cols))
    return blk[:span[0]] + FF.retable(tbl, "".join(made), len(rows)) + blk[span[1]:]


TODO_6 = ("〔사람이 씁니다〕 이 개정으로 무엇이 나아지는지 다섯 줄 안팎으로 "
          "적습니다 — 적용 범위, 정확도와 정합성, 성과의 추적성, 기관 사이의 "
          "인수인계, 재작업과 검수의 일관성.")
TODO_7 = ("〔사람이 씁니다〕 개정의 전체 취지와 타당성 판단을 두 문단 안팎으로 "
          "적습니다. 시행일과 경과조치에 관한 의견도 함께 적습니다.")


def build_reason(dst, tree, regname, walk, R):
    """개정사유서를 양식에 얹는다 → (만든 파일 길, 담은 항목 수)

    R 은 사유 글을 뜯는 도구를 담은 모듈이다(genreport_hwpx). 여기서 곧바로
    들여오면 서로 물고 물리므로 부르는 쪽이 건네준다."""
    f = FF.Form(TPL_REASON)
    P, TB, tops = reason_protos(f)
    if len(TB) < 4:
        raise SystemExit("개정사유서 양식에서 표 넷을 찾지 못했습니다")

    st = R.stat_of(tree)
    fds = R.fields(tree)
    out = [FF.retext(P["title"], "%s 개정사유서" % regname)]

    def sec(t):
        out.append(FF.remake(P["sec"], [(None, t)]))

    def body(t):
        out.append(FF.remake(P["body"], [(None, t)]))

    # ── 1. 개정 목적
    sec("1. 개정 목적")
    aim = []
    for _d, x in walk(tree):
        if x.get("level") == "조" and "목적" in (x.get("title") or ""):
            aim = R.uniq(R.clean(R.pick(R.reason_secs(x.get("reason")),
                                        R.SEC_WHY, R.SEC_WHAT)))
            break
    body("이 개정은 「%s」의 목적과 적용범위를 넓히고, 작업방법ㆍ장비기준ㆍ"
         "자료처리ㆍ성과품 제작ㆍ정확도 검증 및 품질관리 기준을 하나의 체계로 "
         "정비하기 위한 것이다." % regname)
    for a in aim[:4]:
        body(a)
    body("이 개정으로 고치는 조문은 %d개 조, 새로 두는 조문은 %d개 조이며, "
         "별표는 %d건을 고치고 %d건을 새로 둔다. 정비하는 분야는 %d가지다 — %s."
         % (st.get("수정", 0), st.get("신설", 0), st["별표수정"], st["별표신설"],
            len(fds), "ㆍ".join(x[0] for x in fds)))

    # ── 2. 개정 배경 및 필요성 : 분야마다 항을 세운다
    sec("2. 개정 배경 및 필요성")
    KA = "가나다라마바사아자차카타파하"
    rows2 = [["구분", "현황 및 문제점", "개정 필요성"]]
    for i, (name, desc, arts) in enumerate(fds):
        out.append(FF.remake(P["sub"], [(None, "%s. %s"
                                         % (KA[i] if i < len(KA) else str(i + 1), name))]))
        fresh = [a for a in arts if (a.get("status") or "") == "신설"]
        now = R.uniq([re.sub(r"^현행\s*", "", z) for a in arts
                      for z in R.clean(R.pick(R.reason_secs(a.get("reason")),
                                              R.SEC_NOW))])
        if desc:
            body(desc)
        body("이 분야에 걸리는 조문은 %s이다.%s"
             % (R.jo_list(arts),
                (" 이 가운데 %s은(는) 현행에 해당 조문이 없어 새로 둔다."
                 % R.jo_list(fresh)) if fresh else ""))
        ill = []
        if fresh:
            ill.append("현행에 해당하는 조문이 없다 — %s를 새로 둔다." % R.jo_list(fresh))
        ill += [z[:150] for z in now[:3]]
        rows2.append([name, ill or ["—"], [desc] if desc else ["—"]])
    out.append(_tbl_of(TB[0], rows2))

    # ── 3. 주요 개정 내용
    sec("3. 주요 개정 내용")
    rows3 = [["분야", "주요 개정 내용"]]
    for name, desc, arts in fds:
        what = R.uniq(R.clean([z for a in arts
                               for z in R.pick(R.reason_secs(a.get("reason")),
                                               R.SEC_WHAT)]))
        cell = ([desc] if desc else []) + ["해당 조문 — " + R.jo_list(arts)] + what[:8]
        rows3.append([name, cell])
    out.append(_tbl_of(TB[1], rows3))

    # ── 4. 조항별 개정 사유
    sec("4. 조항별 개정 사유")
    rows4 = [["조항", "개정 항목", "개정 사유"]]
    n = 0
    for _d, x in walk(tree):
        if x.get("annexRef") or x.get("level") != "조":
            continue
        rs = (x.get("reason") or "").strip()
        if not rs:
            continue
        n += 1
        br = "의%s" % x["branch"] if x.get("branch") else ""
        why = R.uniq(R.clean(R.pick(R.reason_secs(rs), R.SEC_WHAT))) \
            or R.uniq(R.clean(R.pick(R.reason_secs(rs), R.SEC_WHY)))
        rows4.append(["제%s조%s" % (x.get("no"), br),
                      x.get("title") or "",
                      ["- " + z for z in why[:6]] or [x.get("status") or "유지"]])
    out.append(_tbl_of(TB[2], rows4))

    # ── 5. 별표 개정 및 신설 사유
    sec("5. 별표 개정 및 신설 사유")
    rows5 = [["구분", "별표명", "조치", "개정 또는 신설 사유"]]
    for _d, x in walk(tree):
        a = x.get("annexRef")
        if not a:
            continue
        n += 1
        why = R.uniq(R.clean(R.pick(R.reason_secs(x.get("reason")),
                                    R.SEC_WHAT, R.SEC_WHY)))
        rows5.append(["%s %s" % (a.get("gubun") or "별표", a.get("no")),
                      x.get("title") or "",
                      x.get("status") or "유지",
                      ["- " + z for z in why[:5]] or ["—"]])
    out.append(_tbl_of(TB[3], rows5))

    # ── 6ㆍ7절은 줄글이라 자료에서 지을 수 없다
    sec("6. 기대 효과")
    out.append(FF.remake(P["bullet"], [(None, TODO_6)]))
    sec("7. 종합 의견")
    body(TODO_7)

    f.xml = f.xml[:tops[0][0]] + "".join(out) + f.xml[tops[-1][1]:]
    return f.save(dst), n
