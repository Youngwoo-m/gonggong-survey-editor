# -*- coding: utf-8 -*-
"""국가법령정보센터에 걸려 있던 별표 원본 파일을 곁에 내려받아 둔다.

여태 별표의 내려받기 단추는 law.go.kr 로 곧장 나갔다. 그러면
  ㆍ 미리보기에 PDF 를 통째로 띄울 수 없다 (다른 데의 것은 화면에 못 붙인다)
  ㆍ 그 쪽이 파일 번호를 갈면 링크가 끊긴다
그래서 파일을 받아 두고, annexRef 의 길을 곁의 것으로 바꾼다.

  data/annex/원본/{자리}/{내려받은 이름}

사용:  python scripts/fetch_annex_files.py [--dry]
"""
import io, json, os, re, sys, time, urllib.parse, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "annex", "원본")
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.law.go.kr/"}

TARGETS = [("draft2025.json", "work"), ("draft_simsa.json", "review"),
           ("draft_uav.json", "uav"), ("reg12.json", "reg12")]

BAD = re.compile(r'[<>:"/\|?*\x00-\x1f]')


def fetch(url):
    r = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(r, timeout=60) as f:
        cd = f.headers.get("Content-Disposition") or ""
        m = re.search(r'filename="([^"]+)"', cd)
        name = urllib.parse.unquote(m.group(1)) if m else ""
        return f.read(), name


def tidy(name, gubun, no, ext):
    """내려받은 이름을 파일 이름으로 쓸 만하게 다듬는다"""
    name = BAD.sub("_", name).strip()
    name = re.sub(r"\s*\(공공측량 작업규정\)|\s*\(측량성과 심사수탁기관[^)]*\)", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if not name or not name.lower().endswith("." + ext):
        name = "%s%s.%s" % (gubun, no, ext)
    if len(name) > 90:
        name = name[:80] + "." + ext
    return name


if __name__ == "__main__":
    dry = "--dry" in sys.argv
    got = skip = fail = 0
    for fname, where in TARGETS:
        path = os.path.join(DATA, fname)
        if not os.path.exists(path):
            continue
        doc = json.load(io.open(path, encoding="utf-8"))
        trees = [doc["tree"]] + [r["tree"] for r in (doc.get("next") or [])]
        outdir = os.path.join(OUT, where)
        os.makedirs(outdir, exist_ok=True)
        n = 0

        def w(ns):
            global got, skip, fail, n
            for node in ns:
                a = node.get("annexRef")
                if a:
                    for ext in ("hwp", "pdf"):
                        u = a.get(ext) or ""
                        if not u.startswith("http"):
                            continue
                        gubun, no = a.get("gubun") or "별표", a.get("no")
                        if dry:
                            print("   %-8s %s %-4s %s" % (where, gubun, no, u))
                            skip += 1
                            continue
                        try:
                            blob, name = fetch(u)
                            name = tidy(name, gubun, no, ext)
                            dst = os.path.join(outdir, name)
                            io.open(dst, "wb").write(blob)
                            a[ext] = "data/annex/원본/%s/%s" % (where, name)
                            a.setdefault("srcUrl", {})[ext] = u
                            got += 1
                            n += 1
                        except Exception as e:
                            print("   실패 %-8s %s %-4s %s — %s" % (where, gubun, no, ext, e))
                            fail += 1
                        time.sleep(0.25)
                w(node.get("children") or [])

        for t in trees:
            w(t)
        if not dry and n:
            io.open(path, "w", encoding="utf-8", newline="\n").write(
                json.dumps(doc, ensure_ascii=False))
        print("%-20s %d개" % (fname, n))

    print("\n받은 것 %d · 건너뛴 것 %d · 실패 %d" % (got, skip, fail))
