# -*- coding: utf-8 -*-
r"""별표수정(안) 양식을 별표마다 한 파일로 잘라 낸다.

■ 왜

  신설 별표를 조문 본문 글에서 지어 왔다(annexhwpx.py). 그런데 양식과 견주니
  어긋나는 데가 컸다.

      양식   [별표 10] 블록 조정 결과표   ← 제목 한 줄, 곧바로 표, 아래 주석
      지은 것  빈 줄 / [별표 7] / 블록 조정 결과표 / (제21조…) / 규정 이름 /
               ※ 안내 문구 / 1. 머리 / 사업명 〔…〕 …   ← 글만 49줄, 표가 없다

  별표는 서식이므로 표여야 한다. 그리고 지은 파일의 번호는 낡아 있었다
  (파일은 별표10 인데 문서 안은 [별표 7]).

  다행히 Form\04.별표별지\[양식] 별표수정(안).hwpx 에 별표 1~15 가 표까지
  갖추어 조판되어 있고, 번호와 제목이 개정안 트리와 모두 맞는다. 그러니
  새로 짓지 아니하고 그것을 잘라 쓴다.

■ 용어

  양식은 용어를 정비하기 전에 만든 것이라 LiDAR·수치표면모델 이 남아 있다.
  개정안은 레이저측량·수치표면모형 으로 고쳤으므로 잘라 내면서 함께 맞춘다.

  python scripts\annexsplit.py            무엇이 나오는지 보여만 준다
  python scripts\annexsplit.py --write    파일을 만들고 자료를 고친다
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ROOT = os.path.dirname(HERE)
BASE = os.path.dirname(os.path.dirname(ROOT))
DATA = os.path.join(ROOT, "data")

import formfill as FF                                   # noqa: E402
import forms_hwp as HWP                                 # noqa: E402

TPL = os.path.join(BASE, "Form", "04.별표별지", "[양식] 별표수정(안).hwpx")
OUT = os.path.join(DATA, "annex", "form", "uav")
DRAFT = os.path.join(DATA, "draft_uav.json")

# 개정안이 정비한 용어. 긴 것을 먼저 놓아야 한다 — 'UAV LiDAR' 를 'LiDAR'
# 보다 뒤에 두면 '무인비행장치 레이저측량' 이 아니라 'UAV 레이저측량' 이 된다.
TERMS = [
    ("UAV LiDAR", "무인비행장치 레이저측량"),
    ("Strip Adjustment", "블록 조정"),
    ("Boresight Calibration", "조준선 검정"),
    ("수치표면모델", "수치표면모형"),
    ("수치표고모델", "수치표고모형"),
    ("LiDAR", "레이저측량"),
    ("드론", "무인비행장치"),
]

RE_HEAD = re.compile(r"^\[(별표|별지)\s*(\d+)\]\s*(.*)$")
RE_T = re.compile(r"(<hp:t(?:\s[^>]*)?>)(.*?)(</hp:t>)", re.S)


def fix_terms(xml):
    """글자 마디 안에서만 용어를 맞춘다 — 태그와 속성은 건드리지 아니한다"""
    def one(m):
        s = m.group(2)
        for a, b in TERMS:
            s = s.replace(a, b)
        return m.group(1) + s + m.group(3)
    return RE_T.sub(one, xml)


def tree_titles():
    """개정안 트리의 별표 번호 → 제목 (문서 제목의 기준이다)"""
    d = json.load(io.open(DRAFT, encoding="utf-8"))
    rev = (d.get("next") or [d])[-1]
    out = {}

    def walk(ns):
        for n in ns:
            a = n.get("annexRef")
            if a and a.get("no"):
                out[(a.get("gubun") or "별표", str(a["no"]))] = n.get("title") or ""
            walk(n.get("children") or [])
    walk(rev.get("tree") or [])
    return out, d


def slices():
    """양식 → [(구분, 번호, 양식 제목, [문단 블록…])]"""
    f = FF.Form(TPL)
    tops, last = [], -1
    for p in f.paras():
        if p[0] >= last:
            tops.append(p)
            last = p[1]
    heads = [i for i, p in enumerate(tops) if RE_HEAD.match(p[4])]
    out = []
    for k, i in enumerate(heads):
        j = heads[k + 1] if k + 1 < len(heads) else len(tops)
        g, no, ti = RE_HEAD.match(tops[i][4]).groups()
        out.append((g, no, ti, [tops[x][5] for x in range(i, j)]))
    return f, tops, out


def main():
    write = "--write" in sys.argv
    titles, draft = tree_titles()
    f0, tops, parts = slices()
    print("양식에서 %d개를 찾았습니다 — %s\n"
          % (len(parts), os.path.relpath(TPL, BASE)))

    if write:
        os.makedirs(OUT, exist_ok=True)
    made = []
    for g, no, ftitle, blocks in parts:
        ti = titles.get((g, no))
        if ti is None:
            print("  [건너뜀] %s %s — 개정안 트리에 없습니다" % (g, no))
            continue
        head = "[%s %s] %s" % (g, no, ti)

        # 첫 문단은 쪽 설정(secPr)을 이고 있다. 그것을 머리글로 삼고 나머지를
        # 이어 붙인다 — 그래야 잘라 낸 파일도 쪽 설정을 지닌다.
        body = FF.retext(tops[0][5], head) + "".join(FF.strip_seg(b)
                                                     for b in blocks[1:])
        f = FF.Form(TPL)
        f.xml = f.xml[:tops[0][0]] + body + f.xml[tops[-1][1]:]
        f.xml = fix_terms(f.xml)

        ntbl = f.xml.count("<hp:tbl ")
        dst = os.path.join(OUT, "%s%s.hwpx" % (g, no))
        if write:
            f.save(dst)
            made.append((g, no, dst, ntbl))
        print("  %s %-3s %-44s 표 %d개" % (g, no, ti[:44], ntbl))

    if not write:
        print("\n보여만 준 것입니다. 만들려면 --write 를 붙이십시오.")
        return

    # 한/글로 .hwp 와 .pdf 도 만든다 — 화면의 내려받기와 미리보기가 쓴다
    if HWP.available():
        hwp = HWP.Hwp()
        for g, no, dst, _n in made:
            hwp.convert(dst, {"HWP": dst[:-1], "PDF": dst[:-4] + "pdf"},
                        fmt="HWPX")
        hwp.close()
        print("\n한/글로 .hwp 와 .pdf 도 만들었습니다.")
    else:
        print("\n[주의] 한/글을 부를 수 없어 .hwpx 만 만들었습니다.")

    # 개정안 자료가 새 파일을 가리키게 한다
    rel = os.path.relpath(OUT, ROOT).replace("\\", "/")
    n = 0
    for rev in [draft] + list(draft.get("next") or []):
        def walk(ns):
            nonlocal n
            for x in ns:
                a = x.get("annexRef")
                if a and a.get("no"):
                    g = a.get("gubun") or "별표"
                    p = "%s/%s%s" % (rel, g, a["no"])
                    if os.path.exists(os.path.join(ROOT, p + ".hwpx")):
                        a["hwp"] = p + ".hwp"
                        a["pdf"] = p + ".pdf"
                        a["hwpx"] = p + ".hwpx"
                        a["src"] = "별표수정(안) 양식에서 잘라 냄"
                        a.pop("gen", None)
                        n += 1
                walk(x.get("children") or [])
        walk(rev.get("tree") or [])
    io.open(DRAFT, "w", encoding="utf-8", newline="\n").write(
        json.dumps(draft, ensure_ascii=False))
    print("개정안 자료의 별표 %d건이 새 파일을 가리킵니다." % n)


if __name__ == "__main__":
    main()
