# -*- coding: utf-8 -*-
"""별표ㆍ별지의 본문 글을 조판할 수 있는 덩이로 나눈다.

본문 글은 사람이 읽으라고 쓴 것이라 짜임이 글자에 담겨 있다.

  1.  가.  1)  가)     마디의 깊이
  ·                    벌임표
  ※                    주
  ┌ A ├ B ├ C          표의 머리 (여러 줄로 나뉘기도 한다)
  〔 … 〕               적는 보기 — 줄이 한 줄, 칸은 ' · ' 로 가른다
  <img id="tNNNN">     본문 속 표 — data/objects 에 XML 로 있다

이것을 그대로 글줄로 흘리면 표가 글자로 남아 종이에서 읽히지 아니한다.
그래서 덩이로 나누어 두고, 짓는 쪽에서 표는 표로 세운다.

돌려주는 덩이
  {"kind":"para",  "level":n, "text":…}     n 은 들여쓰기 깊이(0~3)
  {"kind":"note",  "text":…}               ※ 로 시작하는 주
  {"kind":"table", "head":[…], "rows":[[…]], "caption":…}
  {"kind":"obj",   "id":"tNNNN"}           본문 속 표
  {"kind":"blank"}

표로 세우는 것은 칸 수가 머리와 딱 맞을 때뿐이다. 하나라도 어긋나면
글줄로 되돌린다 — 짜 맞추다가 내용이 어긋나는 것이 더 나쁘다.
"""
import re

RE_IMG = re.compile(r'<img id="([^"]+)"\s*>(?:</img>)?')
RE_LV1 = re.compile(r"^\d+\.\s")
RE_LV2 = re.compile(r"^[가-힣]\.\s")
RE_LV3 = re.compile(r"^\d+\)\s")
RE_LV4 = re.compile(r"^[가-힣]\)\s")


def _level(line):
    """줄의 깊이 — 글머리와 들여쓴 칸을 함께 본다"""
    ind = len(line) - len(line.lstrip())
    s = line.strip()
    if RE_LV1.match(s):
        return 0
    if RE_LV2.match(s):
        return 1
    if RE_LV3.match(s):
        return 2
    if RE_LV4.match(s):
        return 3
    return min(3, ind // 2)


def _split_row(s):
    """한 줄을 칸으로 가른다 — 가름표는 ' · ' 이고, 칸 안의 'ㆍ' 는 건드리지 않는다"""
    return [c.strip() for c in re.split(r"\s+·\s+", s.strip()) if c.strip() != ""]


def _split_row_sp(s):
    """빈칸을 벌려 줄을 맞춘 꼴 — 앞의 벌임표를 떼고 두 칸 이상에서 가른다

    무인비행장치 별표들이 이 꼴이다.  '· 보정 방식      PPK'
    """
    s = re.sub(r"^[·•]\s*", "", s.strip())
    return [c.strip() for c in re.split(r"\s{2,}", s) if c.strip() != ""]


def _cells_of(rows_raw, ncol):
    """줄들을 칸으로 가른다 — 가름표 꼴을 먼저 보고, 안 맞으면 빈칸 꼴로 본다.

    칸이 머리보다 모자란 줄은 빈 칸을 채워 맞춘다 (줄 끝에 가름표가 남아
    마지막 칸이 비는 일이 잦다). 머리보다 넘치는 줄이 하나라도 있으면
    표로 세우지 아니한다 — 글이 엉뚱한 칸으로 밀려 뜻이 달라진다."""
    for f in (_split_row, _split_row_sp):
        cells = [f(r) for r in rows_raw]
        if not cells or any(len(c) > ncol for c in cells):
            continue
        if all(len(c) == ncol for c in cells):
            return cells
        # 절반 넘는 줄이 딱 맞을 때에만 모자란 줄을 채워 맞춘다
        exact = sum(1 for c in cells if len(c) == ncol)
        if exact * 2 > len(cells):
            return [c + [""] * (ncol - len(c)) for c in cells]
    return None


def _gather_head(lines, i):
    """┌ 로 여는 표 머리를 거둔다. (머리칸들, 다음 줄 번호) 를 돌려준다."""
    s = lines[i].strip()
    head = [c.strip() for c in re.split(r"[├└]", s.lstrip("┌")) if c.strip()]
    j = i + 1
    while j < len(lines) and lines[j].strip()[:1] in ("├", "└"):
        head.append(lines[j].strip()[1:].strip())
        j += 1
    return head, j


def _gather_rows(lines, i):
    """〔 … 〕 덩이를 줄 목록으로 거둔다. (줄들, 다음 줄 번호, 찾았는가)

    깊이 들여쓴 이어짐 줄은 앞줄에 붙인다 — 한 줄이 길어 접힌 것이다."""
    j = i
    while j < len(lines):
        s = lines[j].strip()
        if "〔" in lines[j]:
            break
        if s.startswith("┌") or (s and not s.startswith("적는 보기") and "〔" not in s):
            # 표와 보기 사이에는 '적는 보기' 말고 다른 말이 끼지 아니한다
            if s.startswith("적는 보기"):
                j += 1
                continue
            return [], i, False
        j += 1
    if j >= len(lines):
        return [], i, False

    buf = []
    while j < len(lines):
        buf.append(lines[j])
        if "〕" in lines[j]:
            break
        j += 1
    # 여는ㆍ닫는 표를 잘라 내지 아니하고 빈칸으로 바꾼다 — 잘라 내면 첫 줄만
    # 들여쓴 칸을 잃어, 뒷줄이 모두 '접힌 줄' 로 보여 한 줄로 뭉친다
    txt = "\n".join(buf).replace("〔", " ", 1)
    if "〕" in txt:
        k0 = txt.rindex("〕")
        txt = txt[:k0] + " " + txt[k0 + 1:]

    rows, cur = [], ""
    base = None
    for ln in txt.split("\n"):
        if not ln.strip():
            continue
        ind = len(ln) - len(ln.lstrip())
        if base is None:
            base = ind
        if cur and ind > base + 2:
            cur += " " + ln.strip()          # 접힌 줄 — 앞줄에 잇는다
        else:
            if cur:
                rows.append(cur)
            cur = ln.strip()
    if cur:
        rows.append(cur)
    return rows, j + 1, True


def parse(body):
    """본문 글 → 덩이 목록"""
    lines = str(body or "").replace("\r\n", "\n").split("\n")
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()

        if not s:
            out.append({"kind": "blank"})
            i += 1
            continue

        if s.startswith("┌"):
            head, j = _gather_head(lines, i)
            rows_raw, k, found = _gather_rows(lines, j)
            cells = _cells_of(rows_raw, len(head)) if found else None
            if cells:
                out.append({"kind": "table", "head": head, "rows": cells})
                i = k
                continue
            # 어긋나면 표로 세우지 아니하고 글줄 그대로 둔다
            for x in range(i, (k if found else j)):
                t = lines[x].strip()
                if t:
                    out.append({"kind": "para", "level": _level(lines[x]), "text": t})
                else:
                    out.append({"kind": "blank"})
            i = k if found else j
            continue

        # 본문 속 표 — 글 사이에 박혀 있으므로 앞뒤를 갈라 낸다
        if RE_IMG.search(s):
            last = 0
            for m in RE_IMG.finditer(s):
                pre = s[last:m.start()].strip()
                if pre:
                    out.append({"kind": "para", "level": _level(line), "text": pre})
                out.append({"kind": "obj", "id": m.group(1)})
                last = m.end()
            tail = s[last:].strip()
            if tail:
                out.append({"kind": "para", "level": _level(line), "text": tail})
            i += 1
            continue

        if s.startswith("※"):
            out.append({"kind": "note", "text": s})
            i += 1
            continue

        out.append({"kind": "para", "level": _level(line), "text": s})
        i += 1

    # 잇달아 빈 줄이 여럿이면 하나로 줄인다
    tidy = []
    for b in out:
        if b["kind"] == "blank" and tidy and tidy[-1]["kind"] == "blank":
            continue
        tidy.append(b)
    while tidy and tidy[0]["kind"] == "blank":
        tidy.pop(0)
    while tidy and tidy[-1]["kind"] == "blank":
        tidy.pop()
    return tidy


def obj_table(path):
    """data/objects 의 표 XML → (머리, 줄들, 이름). 못 읽으면 None"""
    import xml.etree.ElementTree as ET
    try:
        root = ET.parse(path).getroot()
    except Exception:
        return None
    grid = {}
    ncol = 0
    for row in root.findall("row"):
        for c in row.findall("cell"):
            r0 = int(c.get("row", 0))
            c0 = int(c.get("col", 0))
            grid[(r0, c0)] = (c.text or "").strip()
            ncol = max(ncol, c0 + 1)
    if not grid:
        return None
    nrow = max(r for r, _ in grid) + 1
    cells = [[grid.get((r, c), "") for c in range(ncol)] for r in range(nrow)]
    return cells[0], cells[1:], (root.get("article") or "")
