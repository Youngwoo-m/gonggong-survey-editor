# -*- coding: utf-8 -*-
"""신설 별표ㆍ별지의 HWPX ㆍ HWP ㆍ PDF 를 만들고 개정안에 걸어 준다.

현행에서 이어받은 별표는 원본 파일이 있어 내려받기가 되지만, 이번에 새로
지은 별표ㆍ별지는 원본이 없어 내려받을 것이 없었다. 본문 글로 HWPX 를 짓고,
한글(HWPFrame.HwpObject)로 HWP 와 PDF 를 뽑는다.

  data/annex/gen/{자리}/{별표N}.hwpx | .hwp | .pdf

만든 뒤 annexRef 에 hwp ㆍ pdf 길을 적어 넣는다 — 화면의 내려받기 단추와
PDF 미리보기가 그것을 본다.

보기값 〔 〕 은 글자 그대로 둔다 — 종이에서도 보기값임이 드러나야 한다.
이미 그 자리에 원본 파일(.hwp)이 놓여 있으면 짓지 아니하고 그것을 쓴다.

사용:
  python scripts/gen_annex_files.py            모두
  python scripts/gen_annex_files.py --only work:별표:15
  python scripts/gen_annex_files.py --list     무엇을 만들지 보이기만
  python scripts/gen_annex_files.py --no-wire  파일만 만들고 걸지는 않기
"""
import io, json, os, re, subprocess, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
GEN = os.path.join(DATA, "annex", "gen")
SKILL = r"C:\Users\ds2ey\.claude\skills\hwpx"
sys.path.insert(0, HERE)
from hwprender import render                      # noqa: E402

# (파일, 규정 이름, 판마다의 미리보기ㆍ파일 자리)
TARGETS = [
    ("draft2025.json", "공공측량 작업규정", ["work"]),
    ("draft_simsa.json", "측량성과 심사수탁기관의 심사업무 및 지정절차 등에 관한 규정", ["review"]),
    ("draft_uav.json", "무인비행장치 측량 작업규정", ["draftUav", "draftUav2"]),
]


def safe(s):
    return re.sub(r"[^0-9A-Za-z가-힣_.-]", "_", s)


def make_hwpx(title, subtitle, body, dst):
    """본문 글로 HWPX 를 짓는다 — 별표는 제목 한 줄과 글줄로 이루어진 단순 문서다"""
    from hwpx.document import HwpxDocument
    doc = HwpxDocument.new()
    doc.add_paragraph(title)
    if subtitle:
        doc.add_paragraph(subtitle)
    doc.add_paragraph("")
    for line in body.replace("\r\n", "\n").split("\n"):
        doc.add_paragraph(line.rstrip())
    doc.save_to_path(dst)
    subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "fix_namespaces.py"), dst],
                   check=True, capture_output=True)
    return dst


def jobs_of(fname, regname, dirs):
    """신설이면서 본문이 있고 아직 파일이 없는 별표ㆍ별지"""
    path = os.path.join(DATA, fname)
    doc = json.load(io.open(path, encoding="utf-8"))
    revs = [(doc["tree"], dirs[0])] + [
        (r["tree"], dirs[min(i + 1, len(dirs) - 1)])
        for i, r in enumerate(doc.get("next") or [])]
    out = []
    for tree, where in revs:
        def w(ns):
            for n in ns:
                a = n.get("annexRef")
                if (a and n.get("status") == "신설" and (n.get("body") or "").strip()
                        and not (a.get("hwp") or a.get("pdf"))):
                    out.append({"doc": path, "regname": regname, "where": where,
                                "gubun": a.get("gubun") or "별표", "no": str(a.get("no")),
                                "node": n, "annexRef": a})
                w(n.get("children") or [])
        w(tree)
    return doc, out


if __name__ == "__main__":
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    listing = "--list" in sys.argv
    wire = "--no-wire" not in sys.argv

    books = []
    for fname, regname, dirs in TARGETS:
        doc, js = jobs_of(fname, regname, dirs)
        if only:
            js = [j for j in js if only in ("%s:%s:%s" % (j["where"], j["gubun"], j["no"]),
                                            "%s:%s:%s" % (regname, j["gubun"], j["no"]))]
        if js:
            books.append((doc, os.path.join(DATA, fname), js))

    total = sum(len(js) for _, _, js in books)
    print("만들 것 %d건" % total)
    if listing:
        for _, _, js in books:
            for j in js:
                print("   %-10s %s %-3s %-40s %5d자" % (
                    j["where"], j["gubun"], j["no"], (j["node"].get("title") or "")[:40],
                    len(j["node"].get("body") or "")))
        sys.exit(0)

    # ------------------------------------------------------------------ 짓기
    todo = []
    for _, _, js in books:
        for j in js:
            outdir = os.path.join(GEN, j["where"])
            os.makedirs(outdir, exist_ok=True)
            base = safe("%s%s" % (j["gubun"], j["no"]))
            j["base"], j["outdir"] = base, outdir
            src = os.path.join(outdir, base + ".hwp")
            if os.path.exists(src):                       # 원본이 놓여 있으면 그것을 쓴다
                j["src"] = "원본"
                todo.append(src)
                continue
            j["src"] = "본문 글"
            hwpx = os.path.join(outdir, base + ".hwpx")
            title = "[%s %s] %s" % (j["gubun"], j["no"], j["node"].get("title") or "")
            make_hwpx(title, j["regname"], j["node"].get("body") or "", hwpx)
            todo.append(hwpx)
    print("   HWPX %d건을 지었다" % sum(1 for _, _, js in books for j in js if j["src"] == "본문 글"))

    # ------------------------------------------------ 한글로 HWP ㆍ PDF 뽑기
    pages, bad = render(todo, also_hwp=True)
    print("   한글로 뽑음 — 된 것 %d · 안 된 것 %d" % (len(pages), len(bad)))
    for k, m in bad:
        print("      실패 %-16s %s" % (k, m))

    # ------------------------------------------------------------------ 걸기
    if wire:
        for doc, path, js in books:
            n = 0
            for j in js:
                rel = "data/annex/gen/%s/%s" % (j["where"], j["base"])
                if not os.path.exists(os.path.join(ROOT, rel + ".pdf")):
                    continue
                j["annexRef"]["hwp"] = rel + ".hwp"
                j["annexRef"]["pdf"] = rel + ".pdf"
                j["annexRef"]["gen"] = True          # 본문 글로 지은 것임을 밝힌다
                j["annexRef"]["pages"] = pages.get(j["base"], 1)
                n += 1
            io.open(path, "w", encoding="utf-8", newline="\n").write(
                json.dumps(doc, ensure_ascii=False))
            print("   %s — %d건 걸었다" % (os.path.basename(path), n))
