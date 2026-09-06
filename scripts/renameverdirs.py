# -*- coding: utf-8 -*-
r"""판 폴더의 옛 이름을 새 이름으로 바꾼다 (vA → 작업 ㆍ vB → 심사 ㆍ vC → 드론).

  2026-09-06 사람이 개정안 이름의 머리글자를 글자에서 말로 바꾸었다.

      개정안_vA-1.16   →   개정안_작업-1.16
      개정안_vB-1.11   →   개정안_심사-1.11
      개정안_vC-2.04   →   개정안_드론-2.04

  폴더 이름만이 아니라 그 안의 「지은날.txt」와 규정마다의 「버전이력.json」
  (판 이름과 폴더 값)도 함께 고친다. 그러지 아니하면 checkset 이 어긋난다.

  python scripts\renameverdirs.py            무엇을 바꿀지 보여만 준다
  python scripts\renameverdirs.py --write    바꾼다
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = os.path.dirname(ROOT)
OUT = os.path.join(APP, "개정안")
WRITE = "--write" in sys.argv
MAP = {"vA": "작업", "vB": "심사", "vC": "드론"}
# 「개정안_vA-1.16」 처럼 밑줄 뒤에 온다. \b 는 밑줄과 v 사이에 서지
# 아니하므로(둘 다 낱말 글자다) 앞에 로마자만 없으면 되는 것으로 본다.
RE_TAG = re.compile(r"(?<![A-Za-z])(vA|vB|vC)-(\d+\.\d{2})(?![\d.])")


def newname(s):
    return RE_TAG.sub(lambda m: "%s-%s" % (MAP[m.group(1)], m.group(2)), s)


def main():
    if not os.path.isdir(OUT):
        print("개정안 폴더가 없습니다 — %s" % OUT)
        return
    moves, files = [], []
    for reg in sorted(os.listdir(OUT)):
        d = os.path.join(OUT, reg)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.startswith("개정안_"):
                continue
            nn = newname(name)
            if nn != name:
                moves.append((os.path.join(d, name), os.path.join(d, nn)))
        led = os.path.join(d, "버전이력.json")
        if os.path.exists(led):
            files.append(led)

    print("■ 이름을 바꿀 폴더 %d개" % len(moves))
    for a, b in moves[:8]:
        print("   %s → %s" % (os.path.basename(a), os.path.basename(b)))
    if len(moves) > 8:
        print("   … 그 밖에 %d개" % (len(moves) - 8))
    print()
    print("■ 함께 고칠 이력 %d개 : %s" % (len(files),
                                  ", ".join(os.path.basename(os.path.dirname(f)) for f in files)))

    if not WRITE:
        print("\n바꾸려면 --write 를 붙이십시오.")
        return

    done = 0
    for a, b in moves:
        if os.path.exists(b):
            print("   건너뜀 (이미 있음) — %s" % os.path.basename(b))
            continue
        os.rename(a, b)
        done += 1
        # 그 안의 「지은날.txt」에 적힌 판 이름도 고친다
        note = os.path.join(b, "지은날.txt")
        if os.path.exists(note):
            t = io.open(note, encoding="utf-8").read()
            t2 = newname(t)
            if t2 != t:
                io.open(note, "w", encoding="utf-8", newline="").write(t2)

    for f in files:
        d = json.load(io.open(f, encoding="utf-8"))
        s = json.dumps(d, ensure_ascii=False)
        s2 = newname(s)
        if s2 != s:
            io.open(f, "w", encoding="utf-8", newline="").write(
                json.dumps(json.loads(s2), ensure_ascii=False, indent=1))

    print("\n바꾼 폴더 %d개 ㆍ 고친 이력 %d개" % (done, len(files)))
    print("checkset 으로 어긋난 것이 없는지 보십시오.")


if __name__ == "__main__":
    main()
