# -*- coding: utf-8 -*-
r"""지어 놓은 개정안 한 벌이 지금 자료와 맞는가 — 정합성 검증.

기존 검사기는 자료 안쪽을 본다.

    checkdraft.py   조문과 별표의 짜임
    auditdraft.py   조문 속 괄호ㆍ호의 짜임
    checkjo.py      번호만 적은 인용이 말이 되는가
    checkcites.py   밖을 가리키는 법령 이름이 서고와 맞는가
    checklib.py     서고 사본 자체가 성한가

여기서는 **자료와 산출물 사이**를 본다. 지어 놓고 자료를 고치면 폴더의
문서는 조용히 낡는다. 눈으로는 알 수 없다.

  ㉮ 최신 판의 지문이 지금 자료의 지문과 같은가 (문서가 낡지 아니했는가)
  ㉯ 세 문서가 다 있고 속이 비지 아니했는가
  ㉰ 별표ㆍ별지가 자료의 건수와 맞고 hwpx 와 pdf 가 짝을 이루는가
  ㉱ hwpx 가 성한 꾸러미인가 (ZIP 이 열리고 mimetype 이 첫 항목인가)
  ㉲ 버전이력과 실제 폴더가 서로 맞는가
  ㉳ 지은날.txt 가 제 폴더의 판을 가리키는가

한/글을 쓰지 아니하므로 빠르다. 조판까지 보려면 hwprender 로 따로 연다.

  python scripts\checkset.py            모두
  python scripts\checkset.py --only uav 한 규정만
"""
import io
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import weekly_set as W                                 # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

DOCS = ("개정(안).hwpx", "개정(안)_신구대조표.hwpx", "개정사유서.hwpx")


def annex_count(tree):
    """자료가 딸고 있는 별표ㆍ별지 — 지워진 것과 파일 없는 것은 빼고 센다"""
    n = 0
    for x in W.walk(tree):
        a = x.get("annexRef")
        if not a or x.get("isDeleted"):
            continue
        got = [k for k in ("hwpx", "hwp", "pdf")
               if a.get(k) and not str(a[k]).startswith("http")
               and os.path.exists(os.path.join(W.PROTO, a[k]))]
        if got:
            n += 1
    return n


def zip_ok(path):
    """성한 hwpx 인가 — ZIP 이 열리고 mimetype 이 첫 항목이며 무압축인가"""
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if not names or names[0] != "mimetype":
                return "mimetype 이 첫 항목이 아님"
            if z.getinfo("mimetype").compress_type != zipfile.ZIP_STORED:
                return "mimetype 이 압축되어 있음"
            bad = z.testzip()
            if bad:
                return "깨진 항목 %s" % bad
            if not any(re.match(r"Contents/section\d+\.xml$", n) for n in names):
                return "본문(section) 이 없음"
    except Exception as e:
        return str(e)[:60]
    return None


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    bad = []
    print("지어 놓은 개정안이 지금 자료와 맞는가")
    print()

    for target, name, draftfile in W.REGS:
        if only and target != only:
            continue
        hist = W.read_ledger(name)
        revs = W.all_revs(draftfile)
        print("━━ %s" % name)

        # ㉲ 이력과 실제 폴더가 서로 맞는가
        regdir = os.path.join(W.OUT, name)
        onwall = {f for f in os.listdir(regdir)
                  if f.startswith("개정안_v")} if os.path.isdir(regdir) else set()
        inbook = {h.get("폴더") for h in hist}
        for f in sorted(onwall - inbook):
            bad.append((name, f, "폴더는 있는데 이력에 없음"))
        for f in sorted(inbook - onwall):
            bad.append((name, f, "이력에는 있는데 폴더가 없음"))

        for major, revname, rev, tree in revs:
            fp = W.fingerprint(rev, tree)
            mine = [h for h in hist if int(h.get("판번호", 0)) == major]
            if not mine:
                bad.append((name, "%d째 판" % major, "지은 적이 없음"))
                print("   %d째 판 — 지은 적이 없습니다" % major)
                continue
            last = mine[-1]
            tag, folder = last.get("판"), last.get("폴더")
            d = os.path.join(W.OUT, name, folder or "")
            fresh = last.get("지문") == fp
            print("   %d째 판 %s%s" % (major, tag, "" if fresh else "  ← 자료가 더 새롭습니다"))
            if not fresh:
                bad.append((name, tag, "지문이 자료와 다름 — 다시 지어야 함"))
            if not os.path.isdir(d):
                bad.append((name, tag, "폴더가 없음"))
                continue

            # ㉯ 세 문서 · ㉱ 꾸러미
            for f in DOCS:
                p = os.path.join(d, f)
                if not os.path.exists(p):
                    bad.append((name, tag, "%s 가 없음" % f))
                    continue
                if os.path.getsize(p) < 4096:
                    bad.append((name, tag, "%s 가 너무 작음(%dB)"
                                % (f, os.path.getsize(p))))
                why = zip_ok(p)
                if why:
                    bad.append((name, tag, "%s — %s" % (f, why)))

            # ㉰ 별표ㆍ별지
            box = os.path.join(d, "별표및별지")
            want = annex_count(tree)
            if not os.path.isdir(box):
                if want:
                    bad.append((name, tag, "별표및별지 폴더가 없음 (자료 %d건)" % want))
            else:
                fs = os.listdir(box)
                hx = {os.path.splitext(f)[0] for f in fs if f.lower().endswith(".hwpx")}
                pf = {os.path.splitext(f)[0] for f in fs if f.lower().endswith(".pdf")}
                print("      별표ㆍ별지 자료 %d · hwpx %d · pdf %d"
                      % (want, len(hx), len(pf)))
                if len(hx) != want:
                    bad.append((name, tag, "별표ㆍ별지 hwpx %d개 (자료는 %d개)"
                                % (len(hx), want)))
                for s in sorted(hx - pf):
                    bad.append((name, tag, "pdf 가 없음 — %s" % s[:44]))
                for s in sorted(pf - hx):
                    bad.append((name, tag, "hwpx 가 없음 — %s" % s[:44]))
                for f in sorted(fs):
                    if f.lower().endswith(".hwpx"):
                        why = zip_ok(os.path.join(box, f))
                        if why:
                            bad.append((name, tag, "%s — %s" % (f[:40], why)))

            # ㉳ 지은날.txt 가 제 판을 가리키는가
            stamp = os.path.join(d, "지은날.txt")
            if not os.path.exists(stamp):
                bad.append((name, tag, "지은날.txt 가 없음"))
            else:
                t = io.open(stamp, encoding="utf-8").read()
                if tag and tag not in t:
                    bad.append((name, tag, "지은날.txt 가 다른 판을 가리킴"))
                if fp[:16] not in t:
                    bad.append((name, tag, "지은날.txt 의 지문이 다름"))

    print()
    if bad:
        print("■ 어긋난 것 %d건" % len(bad))
        for n, t, why in bad:
            print("   %-14s %-9s %s" % (n[:14], str(t)[:9], why))
    else:
        print("어긋난 것이 없습니다.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
