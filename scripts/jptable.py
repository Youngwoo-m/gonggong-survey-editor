# -*- coding: utf-8 -*-
r"""일본 준칙의 표를 우리말로 옮긴다.

본문은 다 옮겼는데 표는 원문 그대로였다. 국외 규정의 대역은 표까지 옮겨야
온전하다. 옮긴 표는 원본 옆에 `<id>.ko.xml` 로 따로 두고, 화면에서 대역을
그릴 때 그것을 쓴다 (core/objects.js 의 ObjectStore.get 에 ko 를 넘긴다).
없으면 원문 표를 그대로 보이므로, 옮기는 도중에도 화면이 깨지지 아니한다.

■ 어떻게 나누는가

  ㉠ 기계로 되는 것 —— `mech` 가 원본을 그대로 베끼면서 전각 영문을 반각으로,
     가운뎃점(・)을 아래아(ㆍ)로 바꾸고, 정해진 낱말표를 적용한다.
     숫자ㆍ단위ㆍ기호만 든 칸은 이것으로 끝난다.

  ㉡ 사람이 할 것 —— 그러고도 가나ㆍ한자가 남은 칸만 `out` 이 꺼내 온다.
     `in` 이 그것을 받아 넣는다.

■ 쓰는 법

    python scripts\jptable.py mech          기계로 되는 만큼 .ko.xml 을 만든다
    python scripts\jptable.py out 2500      아직 일본말이 남은 칸을 꺼낸다
    python scripts\jptable.py in 파일.json   {"loc11t0003": {"3": "옮긴 글", …}}
    python scripts\jptable.py stat          어디까지 왔는가

  넣기의 열쇠는 **칸의 차례(0부터)** 이다. 표의 구조를 건드리지 아니하고
  칸의 글자만 갈아 끼우므로, 병합ㆍ머리칸 표시가 그대로 살아 있다.
"""
import io
import json
import os
import re
import sys
import glob

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NL = chr(10)
DIR = os.path.join(ROOT, "data", "objects", "loc11")

RE_CELL = re.compile(r"(<cell\b[^>]*>)(.*?)(</cell>)", re.S)
# 가나ㆍ한자가 하나라도 남아 있으면 사람이 볼 칸이다
RE_JP = re.compile(r"[぀-ヿ㐀-鿿]")

WORDS = [
    ("測 量 種 別", "측량 종별"), ("区 分 項 目", "구분 항목"),
    ("電子基準点", "위성기준점"), ("地図情報レベル", "지도정보 수준"),
    ("精度管理表", "정확도 관리표"), ("数値写真", "디지털 사진"),
    ("読定", "읽음"), ("次表", "다음 표"),
    ("平均計画図", "망평균계획도"), ("平均図", "망평균도"), ("平均計算", "망조정 계산"),
    ("製品仕様書", "제품사양서"), ("品質評価", "품질평가"), ("点群", "점군"),
    ("基図", "기본도"), ("調整点", "조정점"), ("較差", "교차"),
]


def files():
    return sorted(p for p in glob.glob(os.path.join(DIR, "loc11t*.xml"))
                  if not p.endswith(".ko.xml"))


def ko_path(p):
    return p[:-4] + ".ko.xml"


def half(s):
    out = []
    for c in s:
        o = ord(c)
        if 0xFF01 <= o <= 0xFF5E:
            out.append(chr(o - 0xFEE0))
        elif c == "　":
            out.append(" ")
        elif c == "・":
            out.append("ㆍ")
        else:
            out.append(c)
    return "".join(out)


def mech_cell(s):
    t = half(s)
    for a, b in WORDS:
        t = t.replace(a, b)
    return t


def cells_of(text):
    return [m.group(2) for m in RE_CELL.finditer(text)]


def put_cells(text, new):
    it = iter(new)
    return RE_CELL.sub(lambda m: m.group(1) + next(it) + m.group(3), text)


def cmd_mech():
    n = 0
    for p in files():
        src = io.open(p, encoding="utf-8").read()
        ko = ko_path(p)
        # 이미 사람이 손댄 것은 덮어쓰지 아니한다
        if os.path.exists(ko):
            continue
        out = put_cells(src, [mech_cell(c) for c in cells_of(src)])
        io.open(ko, "w", encoding="utf-8", newline=NL).write(out)
        n += 1
    print("기계로 만든 표 %d개" % n)
    cmd_stat()


def cmd_out(budget):
    got = 0
    shown = 0
    for p in files():
        ko = ko_path(p)
        if not os.path.exists(ko):
            continue
        text = io.open(ko, encoding="utf-8").read()
        cs = cells_of(text)
        todo = [(i, c) for i, c in enumerate(cs) if RE_JP.search(c)]
        if not todo:
            continue
        size = sum(len(c) for _, c in todo)
        if got and got + size > budget:
            break
        got += size
        shown += 1
        tid = os.path.basename(p)[:-4]
        art = (re.search(r'article="([^"]*)"', text) or [None, ""])[1]
        print("=== %s  %s" % (tid, art))
        for i, c in todo:
            print("  %d| %s" % (i, c.replace(NL, " ")))
        print()
    print("---- 표 %d개 · 일본말 %d자" % (shown, got))


def cmd_in(path):
    data = json.load(io.open(path, encoding="utf-8"))
    n_t = n_c = 0
    for tid, cells in data.items():
        if not tid.startswith("loc11t"):
            continue
        p = os.path.join(DIR, tid + ".ko.xml")
        if not os.path.exists(p):
            print("   없는 표 — %s" % tid)
            continue
        text = io.open(p, encoding="utf-8").read()
        cs = cells_of(text)
        for k, v in cells.items():
            i = int(k)
            if 0 <= i < len(cs):
                cs[i] = v
                n_c += 1
        io.open(p, "w", encoding="utf-8", newline=NL).write(put_cells(text, cs))
        n_t += 1
    print("넣은 표 %d개 · 칸 %d개" % (n_t, n_c))
    cmd_stat()


def cmd_stat():
    tot = made = left_t = left_c = 0
    for p in files():
        tot += 1
        ko = ko_path(p)
        if not os.path.exists(ko):
            continue
        made += 1
        cs = cells_of(io.open(ko, encoding="utf-8").read())
        bad = [c for c in cs if RE_JP.search(c)]
        if bad:
            left_t += 1
            left_c += sum(len(c) for c in bad)
    print("표 %d개 · 만든 것 %d개 · 일본말이 남은 표 %d개 · 남은 글자 %d자"
          % (tot, made, left_t, left_c))


if __name__ == "__main__":
    a = sys.argv[1:] or ["stat"]
    if a[0] == "mech":
        cmd_mech()
    elif a[0] == "out":
        cmd_out(int(a[1]) if len(a) > 1 else 2500)
    elif a[0] == "in":
        cmd_in(a[1])
    else:
        cmd_stat()
