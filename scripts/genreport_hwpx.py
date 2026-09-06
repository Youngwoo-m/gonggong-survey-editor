# -*- coding: utf-8 -*-
r"""규정 하나의 보고서를 한/글 문서(HWPX)로 짓는다 — 별표ㆍ별지까지 함께.

genreport.py 는 작업규정에 박혀 있다(draft2025 · reg01, 별표는 폴더 이름으로
짐작해 찾는다). 이것은 어느 규정이든 받고, 별표는 개정안에 적힌 파일 길을
그대로 쓴다 — 110건이 모두 갖추어져 있으므로 짐작할 까닭이 없다.

  개정(안).hwpx                편ㆍ장ㆍ절ㆍ관 차례대로 담은 조문 전문
  개정사유서.hwpx              조문마다 [변경 사유]
  개정(안)_신구대조표.hwpx      현행 ↔ 개정안 두 칸
  별표및별지모음\              별표ㆍ별지의 한/글 파일과 PDF

■ HWPX 는 한/글에게 맡긴다

  HWPX(ZIP+XML)를 손으로 조립하면 한/글이 '손상된 파일' 로 본다. 그래서 HTML 을
  지어 한/글(HWPFrame.HwpObject)에게 넘겨 저장하게 한다. 한/글을 부를 수 없는
  컴퓨터에서는 HTML 까지만 만들고 멈춘다.

사용:
  python scripts/genreport_hwpx.py --reg uav --rev 2 --out "D:\어느\폴더"
  python scripts/genreport_hwpx.py --list
"""
import datetime as _dt
import difflib
import io, json, os, re, shutil, sys, tempfile, zipfile

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
BASE = os.path.dirname(os.path.dirname(ROOT))     # …\2026.공공측량.품관원

import forms_hwp as HWP                                   # noqa: E402
import formdocs as FD                                     # noqa: E402
from genreport import (esc, page, walk, body_html, table_html,   # noqa: E402
                       preview_ok, RE_PROV, RE_IMG, TH_STYLE)


# ─────────────────────────────────────── 고시 서식에 맞추기
#
# 현행 고시 원본(2020.무인비행장치 측량 작업규정.hwp)을 뜯어 견주었더니
# 우리가 뽑던 글과 어긋나는 데가 있었다.
#
#   원본   국토지리정보원 고시 제2020-5670호      ← 고시 번호를 머리에 둔다
#          무인비행장치 측량 작업규정
#          제1장 총칙
#          제1조(목적) 이 고시는 「공간정보의…      ← 조 제목과 본문이 한 줄
#
#   여태   무인비행장치 측량 작업규정 개정(안)
#          제1조(목적)                            ← 제목만 한 줄
#          이 고시는 「공간정보의…                  ← 본문은 다음 줄
#
# 조 제목 뒤에 첫 문장이 이어 붙는 것이 고시의 꼴이다. 그렇게 맞춘다.

def body_lead(text, regid, lead):
    """조문 본문 — 첫 줄을 조 제목(lead) 뒤에 이어 붙인다.

    본문이 표로 시작하면 이어 붙일 글이 없으므로 제목만 한 줄로 둔다."""
    t = RE_PROV.sub("", str(text or ""))
    parts, last = [], 0
    for m in RE_IMG.finditer(t):
        parts.append(("t", t[last:m.start()]))
        parts.append(("tbl", m.group(1)))
        last = m.end()
    parts.append(("t", t[last:]))

    out, joined = [], False
    for kind, v in parts:
        if kind == "tbl":
            if not joined:                       # 표가 먼저 오면 제목만 세운다
                out.append(f"<div class='jo'>{lead}</div>")
                joined = True
            out.append(table_html(v, regid))
            continue
        for line in str(v).split("\n"):
            line = line.strip()
            if not line:
                continue
            if not joined:
                out.append(f"<p class='jo'>{lead} {esc(line)}</p>")
                joined = True
            else:
                out.append(f"<p>{esc(line)}</p>")
    if not joined:
        out.append(f"<div class='jo'>{lead}</div>")
    return "".join(out)


def arg(name, dflt=None):
    a = sys.argv[1:]
    return a[a.index(name) + 1] if name in a and len(a) > a.index(name) + 1 else dflt


def rj(p):
    return json.load(io.open(p, encoding="utf-8"))


# ─────────────────────────────────────────────────────── 본문 짓기
def html_draft(tree, regname, regid, meta, supp=None):
    """조문 전문 — 관련규정 폴더의 현행 원본과 같은 꼴로 세운다.

        공공측량 작업규정
        [시행 2025. 4. 23.] [국토지리정보원고시 제2025-2092호, 2025. 4. 23., 일부개정.]

    개정안은 시행일과 고시 번호가 아직 없으므로 ○ 로 자리만 둔다 —
    지어 넣으면 정해진 것처럼 읽힌다.

    서식은 인라인으로 준다. page() 의 style 은 genreport.py 와 함께 쓰는
    것이라, 여기서만 필요한 꾸밈을 넣자고 그것을 건드리지 아니한다."""
    GS = "style=\"text-align:center;margin:0 0 6pt;font-size:10.5pt\""
    org = meta.get("org") or "국토지리정보원"
    kind = meta.get("kind") or "고시"
    yy = _dt.datetime.now().year
    # 고시 번호는 아직 없다. 양식도 제2026-0000호 로 자리만 두었다.
    L = [f"<p {GS}>{esc(org)} {esc(kind)} 제{yy}-0000호</p>",
         f"<h1>{esc(regname)} 개정(안)</h1>"]
    # 별표만 담은 묶음 마디(제0편 별표)는 조문 전문에 낼 것이 아니다.
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
        if lv == "편":
            L.append(f"<h2>제{no}편 {esc(ti)}</h2>")
        elif lv == "장":
            L.append(f"<h3>제{no}장 {esc(ti)}</h3>")
        elif lv in ("절", "관"):
            L.append(f"<h4>제{no}{lv} {esc(ti)}</h4>")
        elif lv == "조":
            br = f"의{x['branch']}" if x.get("branch") else ""
            L.append(body_lead(x.get("body"), regid, f"제{no}조{br}({esc(ti)})"))

    # 부칙 — 조문 뒤에 붙는다. 현행 고시도 이 자리에 둔다.
    # 규정 트리에는 담지 아니한다(색인이 부칙을 걷어내므로 조 번호가
    # 어그러진다). 개정안 자료의 supplement 자리에서 가져다 쓴다.
    if supp:
        L.append("<h2 style=\"text-align:center\">부  칙</h2>")
        for a in ([supp] if isinstance(supp, str) else supp):
            for ln in str(a).split(chr(10)):
                if ln.strip():
                    L.append(f"<p>{esc(ln.strip())}</p>")
    return page(regname, "".join(L))


TODO = ("<p style=\"color:#888\">〔이 마디는 사람이 씁니다 — 개정안 자료에 없는 "
        "글입니다.〕</p>")


# ─────────────────────────────────── 개조식 사유 다루기
#
# 개정안 자료의 사유는 이미 개조식이다 — '○ 머리:' 밑에 '* 항목' 이 붙는
# 다섯 도막(현행 규정ㆍ현행의 문제ㆍ관련 근거ㆍ개정 사유ㆍ개정 내용)이다.
# 여태는 '개정 사유' 도막만 여섯 줄까지 잘라 썼는데, 개정사유서에는 사유를
# 통째로 개조식으로 실어야 한다. 그래서 도막을 뜯어 두고 쓰는 데마다 골라
# 쓴다.

SEC_NOW, SEC_ILL = "현행 규정", "현행의 문제"
SEC_WHY, SEC_WHAT = "개정 사유", "개정 내용"


def reason_secs(reason):
    """사유 글 → [(머리, [항목])]

    머리가 없이 시작하는 줄은 머리 '' 로 담는다 — 별표 사유 가운데 '○' 한
    줄로만 된 것이 있다."""
    secs, head, items = [], None, []
    for ln in str(reason or "").split("\n"):
        s = ln.strip()
        if not s or s == "[변경 사유]":
            continue
        if s.startswith("○"):
            if head is not None:
                secs.append((head, items))
            head = s.lstrip("○").strip().rstrip(":").strip()
            items = []
        elif head is None:
            secs.append(("", [re.sub(r"^\*\s*", "", s)]))
        else:
            items.append(re.sub(r"^\*\s*", "", s))
    if head is not None:
        secs.append((head, items))
    return secs


def pick(secs, *names):
    """도막 이름으로 항목만 뽑는다 — 머리는 버린다"""
    out = []
    for head, items in secs:
        if any(n in head for n in names):
            out.extend(items)
    return out


def uniq(xs):
    """차례는 그대로 두고 겹치는 줄만 덜어 낸다"""
    seen, out = set(), []
    for x in xs:
        k = re.sub(r"\s+", "", x)
        if k and k not in seen:
            seen.add(k)
            out.append(x)
    return out


# 사유 글에는 자리만 채워 둔 줄이 섞여 있다. 42개 조가 모두 같은 한 줄을
# 이고 있으므로 그대로 실으면 표가 같은 말로만 가득 찬다. 걷어 낸다.
NOISE = re.compile(r"짚은 마디가 따로 없다|확인된 내용이 없다|해당 없음")


def clean(items):
    return [x for x in items if not NOISE.search(x)]


# 「주요 개정 내용 — 용어체계 정비: …」 꼴에서 분야와 설명을 가른다.
RE_FIELD = re.compile(
    r"^주요 개정 내용\s*[\u2014\u2013-]\s*([^:\uff1a]{2,40})[:\uff1a]\s*(.+)$")


def fields(tree):
    """[(분야, 설명, [조 마디])] — 사유의 '관련 근거' 에 적힌 분야로 묶는다.

    양식 3절이 장이 아니라 분야로 묶여 있다. 자료도 분야를 이고 있으므로
    그대로 따른다. 분야가 적히지 아니한 조는 버리지 아니하고
    '그 밖의 조문 정비' 로 모은다."""
    order, box = [], {}
    for _d, x in walk(tree):
        if x.get("annexRef") or x.get("level") != "조":
            continue
        if not (x.get("reason") or "").strip():
            continue
        name, desc = "그 밖의 조문 정비", ""
        for it in pick(reason_secs(x.get("reason")), "관련 근거"):
            m = RE_FIELD.match(it.strip())
            if m:
                name, desc = m.group(1).strip(), m.group(2).strip()
                break
        if name not in box:
            order.append(name)
            box[name] = [desc, []]
        if desc and not box[name][0]:
            box[name][0] = desc
        box[name][1].append(x)
    return [(k, box[k][0], box[k][1]) for k in order]


def jo_list(arts, lim=6):
    """조 번호를 '제1조ㆍ제2조ㆍ…' 로 늘어놓는다.

    많이 늘어놓으면 한 덩이가 되어 줄이 안 바뀌고, 앞 줄의 자간이 크게
    벌어진다(실제로 그렇게 나왔다). 여섯을 넘으면 '등 N개 조' 로 줄인다."""
    ns = ["제" + str(a.get("no")) + "조"
          + ("의" + str(a["branch"]) if a.get("branch") else "")
          for a in arts]
    return ("ㆍ".join(ns[:lim])
            + (" 등 " + str(len(ns)) + "개 조" if len(ns) > lim else ""))


def kaejo(secs, heads=None):
    """개조식 HTML — '○ 머리' 밑에 '- 항목'

    heads 를 주면 그 도막만 싣는다. 머리가 빈 도막은 머리 없이 항목만 낸다."""
    out = []
    for head, items in secs:
        if heads and not any(h in head for h in heads):
            continue
        keep = clean(items)
        if not keep:
            continue
        if head:
            out.append("<p><b>○ " + esc(head) + "</b></p>")
        for it in keep:
            out.append("<p style='margin-left:10pt'>- " + esc(it) + "</p>")
    return "".join(out) or "&nbsp;"


def kaejo_lines(items):
    """항목 여럿을 개조식 줄로만"""
    return ("".join("<p>- " + esc(x) + "</p>" for x in clean(items))
            or "&nbsp;")


# ─────────────────────────────────── 고친 데만 짚기
#
# 신구대조표 양식의 표기 원칙은 이렇다 —
#   「현행 또는 기존 문구 중 변경 없는 부분은 "_" 로 생략 표기,
#     개정안 문구는 붉은색 밑줄로 표시」
#
# 그래서 두 글을 낱말 단위로 견주어, 그대로인 데가 길면 _ 로 줄이고 고친
# 데만 남긴다. 개정안 칸에서는 새로 든 낱말에 붉은 밑줄을 친다.
#
# 붉은 밑줄은 <u><font color> 로 친다. 한/글의 HTML importer 는 오래된
# 것이라 style 속성보다 이 꼴을 확실히 알아본다.

KEEP = 3          # 그대로인 데를 줄일 때 앞뒤로 남길 낱말 수
LONG = 7          # 낱말이 이보다 많이 이어져 같으면 줄인다


def tokz(s):
    """낱말과 사이 공백을 번갈아 담는다 — 붙이면 본디 글 그대로다"""
    return [t for t in re.split(r"(\s+)", str(s or "")) if t != ""]


def words_of(ts):
    return [t for t in ts if not t.isspace()]


def shrink(ts, first, last):
    """그대로인 도막을 줄인다 — 맨 앞/맨 뒤면 한쪽만 남긴다"""
    w = words_of(ts)
    if len(w) <= LONG:
        return "".join(ts)
    # 도막의 양끝 공백은 살려 둔다. 낱말만 이어 붙이면 앞뒤의 고친 도막과
    # 맞붙어 「필요한사항을」 처럼 붙어 버린다.
    lead = ts[0] if ts[0].isspace() else ""
    rear = ts[-1] if len(ts) > 1 and ts[-1].isspace() else ""
    head = "" if first else " ".join(w[:KEEP]) + " "
    tail = "" if last else " " + " ".join(w[-KEEP:])
    return lead + head + "_" + tail + rear


def mark(s):
    """붉은 밑줄 — 양끝 공백은 밑줄 밖으로 뺀다"""
    core = s.strip()
    if not core:
        return esc(s)
    lead = s[:len(s) - len(s.lstrip())]
    rear = s[len(s.rstrip()):]
    return (esc(lead) + '<u><font color="#C00000">' + esc(core)
            + "</font></u>" + esc(rear))


def coalesce(ops, a):
    """고친 도막 사이에 낀 공백뿐인 도막을 한 덩이로 합친다"""
    out = list(ops)
    i = 1
    while i < len(out) - 1:
        t, i1, i2, _j1, _j2 = out[i]
        if (t == "equal" and not words_of(a[i1:i2])
                and out[i - 1][0] != "equal" and out[i + 1][0] != "equal"):
            p, n = out[i - 1], out[i + 1]
            out[i - 1:i + 2] = [("replace", p[1], n[2], p[3], n[4])]
            continue
        i += 1
    return out


def diff_cells(was, now):
    """(현행 칸, 수정(안) 칸) — 고친 데만 남기고 새 글에는 붉은 밑줄"""
    a, b = tokz(was), tokz(now)
    ops = coalesce(
        difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes(), a)
    old, new = [], []
    for i, (tag, i1, i2, j1, j2) in enumerate(ops):
        first, last = i == 0, i == len(ops) - 1
        if tag == "equal":
            piece = shrink(a[i1:i2], first, last)
            old.append(esc(piece))
            new.append(esc(piece))
        else:
            if i1 < i2:
                old.append(esc("".join(a[i1:i2])))
            if j1 < j2:
                new.append(mark("".join(b[j1:j2])))
    return "".join(old), "".join(new)


def paras_of(s):
    return "".join("<p>" + x.strip() + "</p>" for x in s.split("\n") if x.strip())


def cell_body(was, now, regid):
    """본문에 표가 박혀 있으면 견주지 아니하고 통째로 그린다.

    <img id=…> 자리는 표로 그려지는데, 그것까지 낱말로 견주면 표가 글자로
    풀려 버린다. 표가 있는 조문은 드물어 통째로 두어도 읽는 데 지장이 없다."""
    w = RE_PROV.sub("", str(was or ""))
    n = RE_PROV.sub("", str(now or ""))
    if RE_IMG.search(w) or RE_IMG.search(n):
        return (body_html(w, regid) if w else ""), body_html(n, regid)
    ow, nw = diff_cells(w, n)
    return (paras_of(ow) if w else ""), (paras_of(nw) or "<p></p>")


# ─────────────────────────────────── 개정사유서
def chapters(tree):
    """[(장 이름, [조 마디])] — 편ㆍ장을 따라가며 조를 모은다"""
    out = []
    for _d, x in walk(tree):
        lv = x.get("level")
        if lv in ("편", "장"):
            out.append(("제" + str(x.get("no")) + lv + " " + (x.get("title") or ""), []))
        elif lv == "조" and not x.get("annexRef"):
            if not out:
                out.append(("본칙", []))
            out[-1][1].append(x)
    return [(k.strip(), v) for k, v in out if v]


def stat_of(tree):
    """고친 조ㆍ신설 조ㆍ별표를 센다"""
    s = {"수정": 0, "신설": 0, "삭제": 0, "유지": 0, "별표신설": 0, "별표수정": 0}
    for _d, x in walk(tree):
        st = x.get("status") or "유지"
        if x.get("annexRef"):
            if "신설" in st:
                s["별표신설"] += 1
            elif st != "유지":
                s["별표수정"] += 1
        elif x.get("level") == "조":
            s[st] = s.get(st, 0) + 1
    return s


def html_reason(tree, regname, regid):
    """개정사유서 — Form\\03.개정사유서 의 양식을 따른다.

    양식은 일곱 절이며 모두 채워져 있다(빈 틀이 아니었다).
      1. 개정 목적          2. 개정 배경 및 필요성   3. 주요 개정 내용
      4. 조항별 개정 사유    5. 별표 개정 및 신설 사유
      6. 기대 효과          7. 종합 의견

    여태는 4ㆍ5만 짓고 나머지를 비워 두었는데 1ㆍ2ㆍ3도 자료에서 짓는다.
    사유 글이 '현행의 문제 / 개정 사유 / 개정 내용' 으로 나뉘어 있으므로
    2절은 앞의 둘, 3절은 마지막 하나를 장별로 모으면 그대로 채워진다.
    4ㆍ5절의 사유는 잘라 쓰지 아니하고 개조식 그대로 싣는다.
    """
    st = stat_of(tree)
    fds = fields(tree)
    L = ["<h1>" + esc(regname) + " 개정사유서</h1>"]

    # ── 1. 개정 목적 : 목적 조의 사유와 이번 개정의 크기로 짓는다
    aim = []
    for _d, x in walk(tree):
        if x.get("level") == "조" and "목적" in (x.get("title") or ""):
            aim = pick(reason_secs(x.get("reason")), SEC_WHY, SEC_WHAT)
            break
    L.append("<h2>1. 개정 목적</h2>")
    L.append("<p>이 개정은 「" + esc(regname) + "」의 목적과 적용범위를 넓히고, "
             "작업방법ㆍ장비기준ㆍ자료처리ㆍ성과품 제작ㆍ정확도 검증 및 "
             "품질관리 기준을 하나의 체계로 정비하기 위한 것이다.</p>")
    if aim:
        L.append(kaejo_lines(uniq(aim)))
    L.append("<p>- 정비하는 분야는 " + str(len(fds)) + "가지다 — "
             + esc("ㆍ".join(f[0] for f in fds)) + ".</p>")
    L.append("<p>- 고치는 조문 " + str(st.get("수정", 0)) + "개 조, "
             "새로 두는 조문 " + str(st.get("신설", 0)) + "개 조, "
             "별표는 " + str(st["별표수정"]) + "건을 고치고 "
             + str(st["별표신설"]) + "건을 새로 둔다.</p>")

    # ── 2. 개정 배경 및 필요성 : 장마다 '현행의 문제' 와 '개정 사유'
    L.append("<h2>2. 개정 배경 및 필요성</h2>")
    L.append("<table><thead><tr>"
             "<th width='18%'" + TH_STYLE + ">구분</th>"
             "<th width='41%'" + TH_STYLE + ">현황 및 문제점</th>"
             "<th width='41%'" + TH_STYLE + ">개정 필요성</th></tr></thead><tbody>")
    # 분야마다 현황과 필요성. 현황은 그 분야가 손대는 현행 조문에서 뽑고,
    # 필요성은 분야 설명으로 적는다. 사유 글의 '현행의 문제' 도막은 42개
    # 조가 모두 같은 한 줄이라 쓸 것이 못 된다.
    for name, desc, arts in fds:
        now = uniq([re.sub(r"^현행\s*", "", x) for a in arts
                    for x in clean(pick(reason_secs(a.get("reason")), SEC_NOW))])
        fresh = [a for a in arts if (a.get("status") or "") == "신설"]
        ill = []
        if fresh:
            ill.append("현행 규정에 이에 해당하는 조문이 없다 — "
                       + jo_list(fresh) + "를 새로 둔다.")
        ill += [x[:160] for x in now[:4]]
        L.append("<tr><td>" + esc(name) + "</td>"
                 "<td>" + kaejo_lines(ill) + "</td>"
                 "<td>" + (kaejo_lines([desc]) if desc else
                           "<p>- 조문 체계와 인용ㆍ용어를 규정 전반에 걸쳐 "
                           "일관되게 맞출 필요가 있다.</p>") + "</td></tr>")
    L.append("</tbody></table>")

    # ── 3. 주요 개정 내용 : 장마다 '개정 내용'
    L.append("<h2>3. 주요 개정 내용</h2>")
    L.append("<table><thead><tr>"
             "<th width='22%'" + TH_STYLE + ">분야</th>"
             "<th width='78%'" + TH_STYLE + ">주요 개정 내용</th></tr></thead><tbody>")
    for name, desc, arts in fds:
        what = []
        for a in arts:
            what += pick(reason_secs(a.get("reason")), SEC_WHAT)
        what = uniq(clean(what))
        L.append("<tr><td>" + esc(name) + "</td><td>"
                 + (("<p>" + esc(desc) + "</p>") if desc else "")
                 + "<p class='mut'>해당 조문 — " + esc(jo_list(arts)) + "</p>"
                 + kaejo_lines(what[:10]) + "</td></tr>")
    L.append("</tbody></table>")

    # ── 4. 조항별 개정 사유 : 사유를 통째로 개조식으로
    L.append("<h2>4. 조항별 개정 사유</h2>")
    L.append("<table><thead><tr>"
             "<th width='12%'" + TH_STYLE + ">조항</th>"
             "<th width='20%'" + TH_STYLE + ">개정 항목</th>"
             "<th width='10%'" + TH_STYLE + ">구분</th>"
             "<th width='58%'" + TH_STYLE + ">개정 사유</th></tr></thead><tbody>")
    n = 0
    for _d, x in walk(tree):
        if x.get("annexRef") or x.get("level") != "조":
            continue
        r = (x.get("reason") or "").strip()
        if not r:
            continue
        n += 1
        br = "의" + str(x["branch"]) if x.get("branch") else ""
        L.append("<tr><td>제" + str(x.get("no")) + "조" + br + "</td>"
                 "<td>" + esc(x.get("title") or "") + "</td>"
                 "<td>" + esc(x.get("status") or "유지") + "</td>"
                 "<td>" + kaejo(reason_secs(r)) + "</td></tr>")
    L.append("</tbody></table>")

    # ── 5. 별표 개정 및 신설 사유
    L.append("<h2>5. 별표 개정 및 신설 사유</h2>")
    L.append("<table><thead><tr>"
             "<th width='10%'" + TH_STYLE + ">구분</th>"
             "<th width='24%'" + TH_STYLE + ">별표명</th>"
             "<th width='8%'" + TH_STYLE + ">조치</th>"
             "<th width='58%'" + TH_STYLE + ">개정 또는 신설 사유</th></tr></thead><tbody>")
    for _d, x in walk(tree):
        a = x.get("annexRef")
        if not a:
            continue
        n += 1
        L.append("<tr><td>" + esc(a.get("gubun") or "별표") + " " + esc(a.get("no")) + "</td>"
                 "<td>" + esc(x.get("title") or "") + "</td>"
                 "<td>" + esc(x.get("status") or "유지") + "</td>"
                 "<td>" + kaejo(reason_secs(x.get("reason"))) + "</td></tr>")
    L.append("</tbody></table>")

    L.append("<h2>6. 기대 효과</h2>")
    L.append(TODO)
    L.append("<h2>7. 종합 의견</h2>")
    L.append(TODO)
    return page(regname + " 개정사유서", "".join(L)), n


def html_compare(tree, regname, regid):
    """신구대조표 — Form\\02.신구대조표\\[양식] 규정.신구대조표.hwpx 의 꼴.

    양식의 표기 원칙 그대로다 — 그대로인 데는 _ 로 줄이고 고친 데만 남기며,
    수정(안) 칸의 새 글에는 붉은 밑줄을 친다. 셋째 칸의 사유는 개조식이다.
    """
    L = ["<h1>[붙임] " + esc(regname) + " 일부 개정(안) 신·구대조표</h1>",
         "<p class='mut'>표기 원칙 — 변경 없는 부분은 “_” 로 줄여 적고, "
         "수정(안)의 새 문구는 붉은색 밑줄로 표시한다.</p>",
         "<table><thead><tr>"
         "<th width='36%'" + TH_STYLE + ">현  행</th>"
         "<th width='37%'" + TH_STYLE + ">수정(안)</th>"
         "<th width='27%'" + TH_STYLE + ">개정 사유</th></tr></thead><tbody>"]
    n = 0
    for _d, x in walk(tree):
        if x.get("level") != "조" or x.get("annexRef"):
            continue
        st = x.get("status") or "유지"
        if st == "유지" and not x.get("legacyNo"):
            continue
        n += 1
        br = "의" + str(x["branch"]) if x.get("branch") else ""
        jo = "제" + str(x.get("no")) + "조" + br
        old_head = esc(x.get("legacyNo")) if x.get("legacyNo") else "&lt;신 설&gt;"
        head = jo + "(" + esc(x.get("title") or "") + ")"
        new_head = mark(jo + "(" + (x.get("title") or "") + ")") if st == "신설" else head
        oc, nc = cell_body(x.get("wasBody"), x.get("body"), regid)
        # 셋째 칸은 '개정 사유' 도막이 아니라 '개정 내용' 도막으로 적는다.
        # '개정 사유' 는 42개 조가 모두 같은 한 줄이라 칸마다 같은 말이
        # 되풀이될 뿐이었다. 분야가 적혀 있으면 머리에 얹는다.
        rs = reason_secs(x.get("reason"))
        why = uniq(clean(pick(rs, SEC_WHAT))) or uniq(clean(pick(rs, SEC_WHY)))
        fd = ""
        for it in pick(rs, "관련 근거"):
            m = RE_FIELD.match(it.strip())
            if m:
                fd = m.group(1).strip()
                break
        L.append("<tr>"
                 "<td><b>" + old_head + "</b>" + oc + "</td>"
                 "<td><b>" + new_head + "</b>" + nc + "</td>"
                 "<td>"
                 + (("<p><b>" + esc(fd) + "</b></p>") if fd else "")
                 + (kaejo_lines(why) if why else esc(st)) + "</td></tr>")
    L.append("</tbody></table>")
    return page(regname + " 신·구대조표", "".join(L)), n


# ─────────────────────────────────────────── 별표ㆍ별지 모으기
BAD = re.compile(r'[\\/:*?"<>|]')


def gather_annex(tree, dest, regname=""):
    """개정안에 적힌 파일 길 그대로 모은다 → (담은 것, 못 담은 것)

    이름은 현행 고시의 별표 파일이 쓰는 꼴을 그대로 따른다 —
      [별표 1] 지상기준점의 배치(무인비행장치 측량 작업규정).hwp
    """
    os.makedirs(dest, exist_ok=True)
    got, miss = [], []
    for _d, x in walk(tree):
        a = x.get("annexRef")
        if not a or x.get("isDeleted"):
            continue
        gu, no = a.get("gubun") or "별표", str(a.get("no"))
        ti = (x.get("title") or "").strip()
        stem = BAD.sub("·", f"[{gu} {no}] {ti}({regname})" if regname
                       else f"[{gu} {no}] {ti}")[:150]
        one = False
        # 원본이 모두 .hwpx 로 바뀌었으므로 그것을 먼저 찾는다.
        # ("hwp", "pdf") 만 보면 살아 있는 .hwp 가 하나도 없어 pdf 만 담긴다.
        for key in ("hwpx", "hwp", "pdf"):
            src = a.get(key) or ""
            if not src or src.startswith("http"):
                continue
            p = os.path.join(ROOT, src)
            if not os.path.exists(p):
                continue
            shutil.copyfile(p, os.path.join(dest, stem + os.path.splitext(p)[1]))
            one = True
        if one:
            got.append(f"{gu} {no} {ti}")
        else:
            miss.append(f"{gu} {no} {ti}")
    return got, miss


# ──────────────────────────────────────────────────────── 짓기
def main():
    lib = rj(os.path.join(DATA, "library.json"))
    tj = rj(os.path.join(DATA, "targets.json"))
    targets = tj.get("targets") or tj

    if "--list" in sys.argv:
        for t in targets:
            print(f"  {t['id']:<8} {t.get('short') or t['base']}")
        return

    want = arg("--reg", "work")
    t = next((x for x in targets if x["id"] == want), None)
    if not t:
        sys.exit(f"등록부에 없는 규정입니다 — {want}")
    meta = next((r for r in lib.get("regulations", []) if r["name"] == t["base"]), None)
    if not meta:
        sys.exit(f"라이브러리에서 못 찾음 — {t['base']}")

    draft = rj(os.path.join(ROOT, t["draft"]))
    revs = [(draft.get("title") or "개정안", draft["tree"], draft)] + [
        (r.get("title") or f"개정안 {i + 2}판", r["tree"], r)
        for i, r in enumerate(draft.get("next") or [])]
    ri = int(arg("--rev", "0") or 0)
    if ri:
        if not 1 <= ri <= len(revs):
            sys.exit(f"--rev 는 1..{len(revs)} 입니다")
        ri -= 1
    else:
        ri = len(revs) - 1                      # 안 주면 마지막 판
    revname, tree, rev = revs[ri]
    regname = t.get("base") or t.get("short")
    regid = meta["id"]                          # 본문 속 표·수식을 찾을 자리

    print(f"규정 : {regname}")
    print(f"판   : {revname}  ({ri + 1}/{len(revs)})")

    out_dir = arg("--out", os.path.join(DATA, "report"))
    os.makedirs(out_dir, exist_ok=True)

    tmp = tempfile.mkdtemp(prefix="hwpxreport_")
    stage = os.path.join(tmp, "stage")
    os.makedirs(stage)
    made, bad = [], []
    try:
        # ── 개정(안) · 신구대조표 : 양식 파일에 얹는다
        #
        # HTML 을 지어 한/글에게 넘기면 서식이 한/글의 짐작이 된다. 양식의
        # 문단과 표 칸을 본으로 삼아 복제하면 글꼴ㆍ테두리ㆍ칸 폭이 한 치도
        # 어긋나지 않는다.
        def add(name, path, note):
            ok, head = preview_ok(path)
            if ok is False:
                bad.append(f"{name} — 미리보기 글이 깨졌습니다: {head}")
            made.append((os.path.basename(path),
                         f"{os.path.getsize(path) // 1024}KB"
                         + (f" · {note}" if note else "")))

        p = FD.build_draft(os.path.join(stage, "개정(안).hwpx"), tree,
                           regname, regid, meta, rev.get("supplement"), walk)
        add("개정(안)", p, None)

        def why_of(x):
            """셋째 칸에 넣을 사유 — 개조식 줄만"""
            rs = reason_secs(x.get("reason"))
            return (uniq(clean(pick(rs, SEC_WHAT)))
                    or uniq(clean(pick(rs, SEC_WHY))))[:6]

        p, nc = FD.build_compare(
            os.path.join(stage, "개정(안)_신구대조표.hwpx"), tree,
            regname, regid, walk, why_of)
        add("신구대조표", p, f"대조한 조 {nc}개")

        # ── 개정사유서 : 사람이 쓴 원고의 결과를 가져다 담는다
        #
        # 개정 목적ㆍ배경ㆍ기대 효과ㆍ종합 의견은 개정안 자료에 없는 줄글이라
        # 여기서 지을 수 없다. Report\원고 에서 쓰고 양식에 얹은 것을 담는다.
        # 사람이 쓴 원고는 그 원고를 쓴 판의 것이다. 판이 여럿인 자료에서
        # 아무 판에나 같은 원고를 넣으면 2024년 판에 2025년 사유서가 들어간다.
        #   ㆍ 판마다 따로 쓴 원고가 있으면 그것 (「… 개정사유서_1판.hwpx」)
        #   ㆍ 없으면 마지막 판에만 통짜 원고를 쓴다
        HAND = os.path.join(BASE, "Report", "출력")
        cand = [os.path.join(HAND, f"{regname} 개정사유서_{ri + 1}판.hwpx")]
        if ri == len(revs) - 1:
            cand.append(os.path.join(HAND, f"{regname} 개정사유서.hwpx"))
        src = next((s for s in cand if os.path.exists(s)), None)
        if src:
            dst = os.path.join(stage, "개정사유서.hwpx")
            shutil.copyfile(src, dst)
            add("개정사유서", dst, "사람이 쓴 원고 — " + os.path.basename(src))
        else:
            # 원고가 없으면 자료에서 뽑을 수 있는 데까지 채워 양식에 얹는다.
            # 6ㆍ7절(기대 효과ㆍ종합 의견)은 줄글이라 자리만 세워 둔다.
            p, nr = FD.build_reason(
                os.path.join(stage, "개정사유서.hwpx"),
                tree, regname, walk, sys.modules[__name__],
                rev.get("supplement"), regid)
            add("개정사유서", p, f"자료에서 지음 · 항목 {nr}개")
            print("  [주의] 사람이 쓴 개정사유서가 없어 자료에서 지었습니다"
                  " — 6ㆍ7절은 직접 쓰셔야 합니다")

        got, miss = gather_annex(tree, os.path.join(stage, "별표및별지모음"), regname)

        today = _dt.datetime.now().strftime("%Y%m%d_%H%M")
        short = BAD.sub("_", t.get("short") or want)
        # 판 이름은 화면과 같은 규칙으로 짓는다 — 등록부의 ver 를 머리글자로
        # 삼아 1.00 에서 0.01 씩 올린다 (드론-1.00 · 드론-1.01).
        # 초안 파일의 제목은 두 판이 모두 '개정안 초안…' 으로 시작하여
        # 그대로 쓰면 판이 갈리지 아니한다.
        tag = f"v{t.get('ver') or 'X'}-1.{ri:02d}" if len(revs) > 1 else ""
        zname = f"개정보고서(한글)_{short}{'_' + tag if tag else ''}_{today}.zip"
        zpath = os.path.join(out_dir, zname)
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for base, _dirs, files in os.walk(stage):
                for f in files:
                    p = os.path.join(base, f)
                    z.write(p, os.path.relpath(p, stage))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if bad:
        print("\n[깨짐] 다시 만들어야 합니다")
        for b in bad:
            print("   " + b)
    print("\n보고서 한 벌")
    for n, note in made:
        print(f"  {n:<28} {note or ''}")
    print(f"  {'별표및별지모음':<28} {len(got)}건")
    if miss:
        print(f"  [주의] 파일이 없는 별표ㆍ별지 {len(miss)}건: " + ", ".join(miss[:6]))
    print(f"\n  {zpath}  ({os.path.getsize(zpath) // 1024}KB)")


if __name__ == "__main__":
    main()
