# -*- coding: utf-8 -*-
r"""별표ㆍ별지의 내려받기 길을 .hwp 에서 .hwpx 로 옮긴다.

원본 한/글 파일을 모두 .hwpx 로 바꾸었으므로, 자료가 가리키던 .hwp 는
하나도 남아 있지 아니하다(110건 전부). 그대로 두면 내려받기 단추가 없는
파일을 가리킨다.

  ㆍ annexRef.hwp 와 같은 이름의 .hwpx 가 곁에 있으면 그것으로 옮긴다
  ㆍ 옮긴 뒤 .hwp 는 지운다 — 없는 파일을 가리키느니 없는 편이 낫다
  ㆍ .hwpx 도 없으면 그대로 두고 알린다 (손으로 살펴야 한다)

  python scripts\annexhwpxpath.py            보여만 준다
  python scripts\annexhwpxpath.py --write    자료에 적는다
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def main():
    write = "--write" in sys.argv
    moved = kept = lost = 0
    for f in ("draft2025.json", "draft_simsa.json", "draft_uav.json"):
        p = os.path.join(DATA, f)
        d = json.load(io.open(p, encoding="utf-8"))
        touched = False
        for rev in [d] + list(d.get("next") or []):
            for x in walk(rev.get("tree") or []):
                a = x.get("annexRef")
                if not a or not a.get("hwp"):
                    continue
                hwp = a["hwp"]
                if os.path.exists(os.path.join(ROOT, hwp)):
                    kept += 1
                    continue
                alt = os.path.splitext(hwp)[0] + ".hwpx"
                if os.path.exists(os.path.join(ROOT, alt)):
                    if a.get("hwpx") != alt:
                        a["hwpx"] = alt
                    a.pop("hwp", None)
                    moved += 1
                    touched = True
                else:
                    lost += 1
                    print("   ! .hwpx 도 없음 %-13s %s %-4s %s"
                          % (f[:12], a.get("gubun"), a.get("no"), hwp))
        if write and touched:
            io.open(p, "w", encoding="utf-8", newline="\n").write(
                json.dumps(d, ensure_ascii=False))
    print()
    print(".hwpx 로 옮긴 것 %d · 그대로 둔 것 %d · 짝을 못 찾은 것 %d"
          % (moved, kept, lost))
    if not write:
        print("시험만 한 것입니다. 적으려면 --write 를 붙이십시오.")


if __name__ == "__main__":
    main()
