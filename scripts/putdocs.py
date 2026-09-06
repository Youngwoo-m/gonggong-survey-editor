# -*- coding: utf-8 -*-
r"""서고 규정의 원문 파일을 웹이 닿는 자리로 들이고 자료에 잇는다 (할일 ㉧).

■ 왜 옮기는가

  화면의 [원문 내려받기]는 지금 색인한 조문으로 지은 html 을 낸다. 참말
  원문(hwpx ㆍ pdf)이 나가는 것은 자료에 `docFile` 이 달린 둘뿐이다.
  파일은 `App\관련규정` 에 다 있으나 웹 뿌리 밖이라 브라우저가 닿지 못한다.

      App\관련규정\상위법령\…법률…hwpx      ← 브라우저가 닿지 못함
      App\prototype\data\원문\reg02\…hwpx  ← 이 자리로 들인다

■ 무엇을 들이는가

  matchfiles.py 가 지은 짝에서 **본문 파일만** 고른다. 별표ㆍ별지ㆍ부록ㆍ
  서식은 이미 `data\annex` 에 그림과 표로 들어 있으므로 다시 담지 아니한다.

      --one    규정마다 하나 (hwpx 우선, 없으면 pdf)
      --both   hwpx 와 pdf 를 둘 다 (기본)
      --all    잡힌 본문 전부

  ISO 규정(loc29ㆍloc30ㆍloc31)은 유료 표준이라 저장소에 올리지 아니한다.
  자리에는 들이되 .gitignore 로 막는다.

  python scripts\putdocs.py             무엇을 들일지 세어만 본다
  python scripts\putdocs.py --write     들이고 library.json 에 docFile 을 단다
"""
import io
import json
import os
import re
import shutil
import sys
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matchfiles as MF

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = os.path.dirname(ROOT)
SRCDIR = os.path.join(APP, "관련규정")
OUT = os.path.join(ROOT, "data", "원문")
LIB = os.path.join(ROOT, "data", "library.json")
WRITE = "--write" in sys.argv
MODE = ("one" if "--one" in sys.argv else
        "all" if "--all" in sys.argv else "both")
NOPUSH = ("loc29", "loc30", "loc31")          # 유료 표준 —— 저장소에 올리지 아니함

RE_ANX = re.compile(r"^\s*\[?\s*(별표|별지|부록|서식|양식)\s*[\d의\-]")
RE_HEAD = re.compile(r"^\[([^\]]{2,60})\]\s*(?:별표|별지|부록|서식)")
EXT_RANK = {".hwpx": 0, ".hwp": 1, ".pdf": 2, ".docx": 3, ".doc": 4}


def files_under(root):
    for base, _dirs, names in os.walk(root):
        for f in names:
            p = os.path.join(base, f)
            yield os.path.relpath(p, root).replace("\\", "/"), f, os.path.getsize(p)


def main():
    # matchfiles.main 이 쓰는 꼴 그대로 —— 다섯째 자리에 다듬은 이름이 있어야 한다
    lib = json.load(io.open(LIB, encoding="utf-8"))
    lib_pre = lib
    names = {r["id"]: r.get("name", "") for r in lib["regulations"]}
    table = [(i, n, c, cl, MF.norm(n)) for i, n, c, cl in MF.regs()]
    hits = collections.defaultdict(list)      # 규정 id -> [(rel, 이름, 크기)]
    for rel, f, size in files_under(SRCDIR):
        if RE_ANX.match(f) or RE_HEAD.match(f):
            continue                          # 별표ㆍ별지는 담지 아니한다
        got = MF.by_hand(rel, table) or MF.match(f, table)
        if not got:
            continue
        rid = got[0]
        if os.path.splitext(f)[1].lower() not in EXT_RANK:
            continue
        hits[rid].append((rel, f, size))

    # 자료에 사람이 적어 둔 원문(localFile)이 있으면 그것을 앞세운다.
    # 준칙은 구글번역본이 hwpx 라 이름 차례로는 그것이 먼저 잡힌다.
    local = {}
    for r in lib_pre["regulations"]:
        lf = r.get("localFile")
        if lf:
            local[r["id"]] = os.path.basename(str(lf).replace("\\", "/"))

    plan = {}
    for rid, xs in hits.items():
        want = local.get(rid)
        xs.sort(key=lambda z: (0 if z[1] == want else 1,
                               EXT_RANK.get(os.path.splitext(z[1])[1].lower(), 9),
                               -len(z[1])))
        if MODE == "one":
            plan[rid] = xs[:1]
        elif MODE == "all":
            plan[rid] = xs
        else:
            seen, take = set(), []
            for x in xs:
                ext = os.path.splitext(x[1])[1].lower()
                kind = "hwp" if ext in (".hwp", ".hwpx") else ext
                if kind in seen:
                    continue
                seen.add(kind)
                take.append(x)
            plan[rid] = take

    n_file = sum(len(v) for v in plan.values())
    n_byte = sum(s for v in plan.values() for _r, _f, s in v)
    print("■ 담는 방식 : %s" % {"one": "규정마다 하나", "both": "hwpx 와 pdf 둘 다",
                            "all": "잡힌 본문 전부"}[MODE])
    print("   규정 %d종 ㆍ 파일 %d개 ㆍ %.1f MB" % (len(plan), n_file, n_byte / 1024 / 1024))
    miss = [r["id"] for r in lib["regulations"] if r["id"] not in plan]
    if miss:
        print("   본문을 못 찾은 규정 %d종 — %s" % (len(miss), ", ".join(miss[:12])))
    print()
    for rid in sorted(plan, key=lambda k: -sum(s for _r, _f, s in plan[k]))[:8]:
        v = plan[rid]
        print("   %-7s %-40s %d개 %.1fMB" % (rid, names.get(rid, "")[:38], len(v),
                                            sum(s for _r, _f, s in v) / 1024 / 1024))

    if not WRITE:
        print("\n들이려면 --write 를 붙이십시오.")
        return

    os.makedirs(OUT, exist_ok=True)
    put = 0
    for rid, xs in plan.items():
        d = os.path.join(OUT, rid)
        os.makedirs(d, exist_ok=True)
        for rel, f, _s in xs:
            dst = os.path.join(d, f)
            if not os.path.exists(dst):
                shutil.copy2(os.path.join(SRCDIR, rel.replace("/", os.sep)), dst)
            put += 1
    for r in lib["regulations"]:
        xs = plan.get(r["id"])
        if not xs:
            continue
        r["docFile"] = "data/원문/%s/%s" % (r["id"], xs[0][1])
        if len(xs) > 1:
            r["docFiles"] = ["data/원문/%s/%s" % (r["id"], x[1]) for x in xs]
        elif "docFiles" in r:
            del r["docFiles"]
    io.open(LIB, "w", encoding="utf-8", newline="").write(
        json.dumps(lib, ensure_ascii=False))
    print("\n들였습니다 —— 파일 %d개 ㆍ docFile 을 단 규정 %d종"
          % (put, sum(1 for r in lib["regulations"] if r.get("docFile"))))
    print("저장소에 올리지 아니할 것 : %s" % ", ".join(NOPUSH))


if __name__ == "__main__":
    main()
