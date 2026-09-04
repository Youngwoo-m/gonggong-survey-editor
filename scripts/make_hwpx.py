# -*- coding: utf-8 -*-
r"""꾸러미 안에서 한/글 문서를 짓는다 — 웹에서 받은 zip 을 푼 자리에서 돈다.

■ 무엇인가

  편집기를 웹(GitHub Pages)에 올려 두면 [보고서 생성] 으로 zip 을 받을 수
  있다. 그런데 HWPX 는 브라우저가 만들지 못한다. 손으로 조립한 꾸러미를
  한/글이 '손상된 파일' 로 보기 때문에, 한/글에게 저장을 맡겨야 한다.

  그래서 zip 안에 도구와 양식과 편집 상태를 함께 담아 두고, 한/글이 깔린
  PC 에서 [한글문서만들기.bat] 을 누르면 이 파일이 돌아 문서를 짓는다.

■ 꾸러미의 짜임

    한글문서만들기.bat
    개정안.json          ← [보고서 생성] 을 누른 그때의 편집 상태
    도구\                ← 이 파일과 formfill·formdocs·forms_hwp
    도구\hwpx\scripts\   ← 뒤처리ㆍ검증 스크립트 (hwpx 스킬에서 가져온 것)
    양식\                ← Form 폴더의 양식 그대로
    objects\             ← 조문 본문에 박힌 표
    별표및별지모음\        ← 별표ㆍ별지의 한/글 파일과 PDF
    출력\                ← 여기에 만들어진다

■ 미리 갖출 것

  ㆍ 한글과컴퓨터 한/글 (2018 이상)
  ㆍ 파이썬 3.9 이상
  ㆍ pywin32  (없으면 이 파일이 알려 준다 — pip install pywin32)

사용:
  python 도구\make_hwpx.py            (bat 이 이렇게 부른다)
  python 도구\make_hwpx.py --out 다른폴더
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # 꾸러미를 푼 자리

# 도구들에게 꾸러미 안의 자리를 알려 준다 — 이 컴퓨터의 Form·data 를 찾지
# 않게 하려는 것이다. 반드시 formdocs 를 들여오기 전에 해야 한다.
os.environ.setdefault("FORM_DIR", os.path.join(ROOT, "양식"))
os.environ.setdefault("DATA_DIR", ROOT)            # objects\ 가 바로 밑에 있다
os.environ.setdefault("HWPX_SKILL", os.path.join(HERE, "hwpx"))
sys.path.insert(0, HERE)

import formdocs as FD                              # noqa: E402
import genreport_hwpx as G                         # noqa: E402


def walk(tree):
    """[(깊이, 마디)] — 그린 차례 그대로"""
    out = []

    def rec(ns, d):
        for x in ns:
            out.append((d, x))
            rec(x.get("children") or [], d + 1)

    rec(tree, 0)
    return out


def why_of(x):
    """신구대조표 셋째 칸 — 개조식 줄만"""
    rs = G.reason_secs(x.get("reason"))
    return (G.uniq(G.clean(G.pick(rs, G.SEC_WHAT)))
            or G.uniq(G.clean(G.pick(rs, G.SEC_WHY))))[:6]


def arg(name, dflt=None):
    i = sys.argv.index(name) if name in sys.argv else -1
    return sys.argv[i + 1] if 0 <= i < len(sys.argv) - 1 else dflt


def main():
    src = os.path.join(ROOT, "개정안.json")
    if not os.path.exists(src):
        sys.exit("개정안.json 이 없습니다 — zip 을 통째로 푸셨는지 보십시오.")
    regs = json.load(io.open(src, encoding="utf-8"))
    if isinstance(regs, dict):
        regs = [regs]

    try:
        import forms_hwp as HWP
        ok = HWP.available()
    except Exception:
        ok = False
    if not ok:
        print("한/글을 부를 수 없습니다. 다음을 확인하십시오.")
        print("  1) 한글과컴퓨터 한/글이 깔려 있는가")
        print("  2) pip install pywin32 를 하셨는가")
        sys.exit(1)

    out_dir = arg("--out", os.path.join(ROOT, "출력"))
    os.makedirs(out_dir, exist_ok=True)

    made = []
    for r in regs:
        name = r.get("regname") or r.get("short") or "규정"
        tree = r.get("tree") or []
        meta = {"org": r.get("org"), "kind": r.get("kind")}
        tag = (" " + r["revLabel"]) if r.get("revLabel") else ""
        print(f"\n[{name}{tag}]")

        p = FD.build_draft(os.path.join(out_dir, f"개정(안){tag}.hwpx"),
                           tree, name, r.get("regId") or "", meta,
                           r.get("supplement"), walk)
        made.append(p)
        print(f"  개정(안)            {os.path.getsize(p) // 1024}KB")

        p, nc = FD.build_compare(
            os.path.join(out_dir, f"개정(안)_신구대조표{tag}.hwpx"),
            tree, name, r.get("regId") or "", walk, why_of)
        made.append(p)
        print(f"  신구대조표          {os.path.getsize(p) // 1024}KB · 대조한 조 {nc}개")

        p, nr = FD.build_reason(os.path.join(out_dir, f"개정사유서{tag}.hwpx"),
                                tree, name, walk, G)
        made.append(p)
        print(f"  개정사유서          {os.path.getsize(p) // 1024}KB · 항목 {nr}개")

    print(f"\n만들었습니다 — {out_dir}")
    print("  6ㆍ7절(기대 효과ㆍ종합 의견)은 줄글이라 자료에서 지을 수 없습니다.")
    print("  개정사유서를 열어 그 두 절을 직접 쓰십시오.")
    ax = os.path.join(ROOT, "별표및별지모음")
    if os.path.isdir(ax):
        print(f"  별표ㆍ별지 {len(os.listdir(ax))}건은 별표및별지모음\\ 에 있습니다.")


if __name__ == "__main__":
    main()
