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


def fixns(path):
    """네임스페이스 뒷손질 — 빠뜨리면 한글 뷰어에서 빈 쪽으로 보인다"""
    subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "fix_namespaces.py"), path],
                   check=True, capture_output=True)


def make_hwpx(job, dst):
    """본문 글을 덩이로 나누어 표는 표로, 마디는 들여쓰기로 세운다 (annexhwpx)"""
    import annexhwpx
    n = job["node"]
    return annexhwpx.build(
        dst,
        gubun=job["gubun"], no=job["no"],
        title=n.get("title") or "", regname=job["regname"],
        body=n.get("body") or "",
        objdir=os.path.join(DATA, "objects", job.get("objdir") or "reg01"),
        fixns=fixns)


def jobs_of(fname, regname, dirs, force=False):
    """신설이면서 본문이 있는 별표ㆍ별지 — 아직 파일이 없는 것만.

    force 를 주면 이미 파일이 있어도 고른다. 양식에서 잘라 온 것을 본문
    글로 갈아 치울 때 쓴다."""
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
                # 이미 우리가 지은 것(gen)은 다시 짓는다 — 조판을 고치면
                # 그때마다 다시 뽑아야 하기 때문이다. 남의 원본은 건드리지 않는다.
                # keepSrc 는 '남에게서 받은 원본이니 덮지 말라' 는 표시다
                if (a and n.get("status") == "신설" and (n.get("body") or "").strip()
                        and not a.get("keepSrc")
                        and (force or a.get("gen")
                             or not (a.get("hwp") or a.get("pdf")))):
                    out.append({"doc": path, "regname": regname, "where": where,
                                # 본문 속 표는 지금 셋 다 작업규정에서 옮겨 온 것뿐이다
                                "objdir": "reg01",
                                "gubun": a.get("gubun") or "별표", "no": str(a.get("no")),
                                "node": n, "annexRef": a})
                w(n.get("children") or [])
        w(tree)
    return doc, out


if __name__ == "__main__":
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    listing = "--list" in sys.argv
    wire = "--no-wire" not in sys.argv
    force = "--force" in sys.argv

    books = []
    for fname, regname, dirs in TARGETS:
        doc, js = jobs_of(fname, regname, dirs, force)
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
            # 남이 만든 원본이 놓여 있으면 그것을 쓴다.
            # 우리가 지은 것(gen)이면 조판을 다시 하여야 하므로 새로 짓는다.
            if os.path.exists(src) and not j["annexRef"].get("gen") and not force:
                j["src"] = "원본"
                todo.append(src)
                continue
            j["src"] = "본문 글"
            hwpx = os.path.join(outdir, base + ".hwpx")
            make_hwpx(j, hwpx)
            todo.append(hwpx)
    print("   HWPX %d건을 지었다" % sum(1 for _, _, js in books for j in js if j["src"] == "본문 글"))

    # ------------------------------------------------ 한글로 HWP ㆍ PDF 뽑기
    pages, bad = render(todo)          # .hwp 는 더 뽑지 아니한다
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
                a0 = j["annexRef"]
                # 양식에서 잘라 온 것을 갈아 치우는 것이면 그 길을 남겨 둔다 —
                # 기관 서식ㆍ연구결과 원본이라 되짚어 볼 일이 있다
                if a0.get("hwp") and not a0.get("gen") and not a0.get("formSrc"):
                    a0["formSrc"] = {k: a0.get(k) for k in ("hwp", "hwpx", "pdf")
                                     if a0.get(k)}
                    if a0.get("src"):
                        a0["formSrc"]["note"] = a0["src"]
                # 원본을 모두 .hwpx 로 쓰기로 하였으므로 .hwp 는 걸지 않는다
                j["annexRef"]["hwpx"] = rel + ".hwpx"
                j["annexRef"].pop("hwp", None)
                j["annexRef"]["pdf"] = rel + ".pdf"
                j["annexRef"]["gen"] = True          # 본문 글로 지은 것임을 밝힌다
                j["annexRef"]["pages"] = pages.get(j["base"], 1)
                n += 1
            io.open(path, "w", encoding="utf-8", newline="\n").write(
                json.dumps(doc, ensure_ascii=False))
            print("   %s — %d건 걸었다" % (os.path.basename(path), n))
