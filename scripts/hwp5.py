# -*- coding: utf-8 -*-
"""
HWP 5.0 (OLE2 이진) 문서에서 표를 읽어 낸다.

국가법령정보센터의 별표·서식 원본은 HWPX 가 아니라 옛 HWP 이진 파일이다.
한글문서파일형식 5.0 공개 문서에 따라 레코드를 직접 훑는다.

  OLE2 → BodyText/SectionN (zlib raw deflate) → 레코드 스트림
  레코드 머리 4바이트 = tag(10bit) | level(10bit) | size(12bit)
      size 가 0xFFF 이면 다음 4바이트가 진짜 길이

  쓰는 태그
    66 PARA_HEADER   문단 시작
    67 PARA_TEXT     문단 글자 (UTF-16LE + 제어문자)
    71 CTRL_HEADER   개체 머리 — id 가 'tbl ' 이면 표
    72 LIST_HEADER   문단 목록 머리 — 표 안에서는 '셀'
    77 TABLE         표 크기·행별 셀 수
"""
import io, struct, zlib

import olefile

TAG_PARA_HEADER = 66
TAG_PARA_TEXT = 67
TAG_CTRL_HEADER = 71
TAG_LIST_HEADER = 72
TAG_TABLE = 77

# 글자 자리를 차지하는 제어문자 — 앞뒤로 8개 WCHAR 를 먹는다
CTRL_EXTEND = {1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23}
CTRL_INLINE = {4, 5, 6, 7, 8, 9, 19, 20}
CTRL_CHAR = {0, 10, 13, 24, 25, 26, 27, 28, 29, 30, 31}


# ───────────────────────── 레코드 훑기 ─────────────────────────
def records(buf):
    """[(tag, level, data), …]"""
    out, i, n = [], 0, len(buf)
    while i + 4 <= n:
        (h,) = struct.unpack_from("<I", buf, i)
        i += 4
        tag = h & 0x3FF
        level = (h >> 10) & 0x3FF
        size = (h >> 20) & 0xFFF
        if size == 0xFFF:
            if i + 4 > n:
                break
            (size,) = struct.unpack_from("<I", buf, i)
            i += 4
        if i + size > n:
            break
        out.append((tag, level, buf[i:i + size]))
        i += size
    return out


def sections(path):
    """[bytes, …] — 압축을 푼 BodyText 스트림들"""
    ole = olefile.OleFileIO(path)
    try:
        head = ole.openstream("FileHeader").read()
        if head[:17] != b"HWP Document File":
            raise ValueError("HWP 5.0 파일이 아닙니다")
        (flags,) = struct.unpack_from("<I", head, 36)
        compressed = bool(flags & 1)

        names = sorted(
            ("/".join(p) for p in ole.listdir() if p[0] == "BodyText"),
            key=lambda s: int(s.rsplit("Section", 1)[-1] or 0),
        )
        out = []
        for nm in names:
            raw = ole.openstream(nm).read()
            out.append(zlib.decompress(raw, -15) if compressed else raw)
        return out
    finally:
        ole.close()


# ───────────────────────── 글자 ─────────────────────────
def para_text(data):
    """PARA_TEXT 레코드 → 글자 (제어문자는 건너뛴다)"""
    out, i, n = [], 0, len(data) - 1
    while i < n:
        (c,) = struct.unpack_from("<H", data, i)
        if c in CTRL_EXTEND or c in CTRL_INLINE:
            i += 16                       # 8 WCHAR
            continue
        if c in CTRL_CHAR:
            if c in (10, 13):
                out.append("\n")
            i += 2
            continue
        # UTF-16 대리쌍 — 짝이 맞으면 합치고, 홀로 있으면 버린다
        if 0xD800 <= c <= 0xDBFF:
            lo = struct.unpack_from("<H", data, i + 2)[0] if i + 4 <= len(data) else 0
            if 0xDC00 <= lo <= 0xDFFF:
                out.append(chr(0x10000 + ((c - 0xD800) << 10) + (lo - 0xDC00)))
                i += 4
                continue
            i += 2
            continue
        if 0xDC00 <= c <= 0xDFFF:
            i += 2
            continue
        out.append(chr(c))
        i += 2
    return "".join(out)


def _u16(d, o):
    return struct.unpack_from("<H", d, o)[0] if o + 2 <= len(d) else 0


def read_table_rec(data):
    """TABLE 레코드 → {rows, cols, rowSizes}"""
    if len(data) < 12:
        return None
    rows = _u16(data, 4)
    cols = _u16(data, 6)
    o = 18                                # 속성4 + 행2 + 열2 + 셀간격2 + 여백2*4 = 18
    row_sizes = []
    for _ in range(rows):
        row_sizes.append(_u16(data, o))
        o += 2
    return {"rows": rows, "cols": cols, "rowSizes": row_sizes}


def read_cell_head(data):
    """표 안 LIST_HEADER → 셀 주소·병합
       공통부 = 문단수 INT32 + 속성 UINT32 (8바이트), 그 뒤가 셀 속성"""
    if len(data) < 16:
        return None
    return {
        "col": _u16(data, 8), "row": _u16(data, 10),
        "colspan": max(1, _u16(data, 12)), "rowspan": max(1, _u16(data, 14)),
    }


# ───────────────────────── 표 뽑기 ─────────────────────────
def extract(path):
    """
    [{kind:'table', rows:[[{col,row,colspan,rowspan,text}, …], …]} |
     {kind:'text',  text:'…'}, …]  — 문서 순서대로
    """
    out = []
    for sec in sections(path):
        recs = records(sec)
        i, n = 0, len(recs)
        stack = []                        # 열려 있는 표들 [(level, table)]

        while i < n:
            tag, level, data = recs[i]

            # 표가 끝났는지 — 표를 연 깊이보다 얕아지면 닫는다
            while stack and level <= stack[-1][0]:
                out.append(_finish(stack.pop()[1]))

            if tag == TAG_CTRL_HEADER and len(data) >= 4 and data[:4][::-1] == b"tbl ":
                # 바로 뒤(같은 문단 안)의 TABLE 레코드를 찾는다
                j, meta = i + 1, None
                while j < n and j < i + 8:
                    if recs[j][0] == TAG_TABLE:
                        meta = read_table_rec(recs[j][2])
                        break
                    j += 1
                if meta:
                    stack.append((level, {"meta": meta, "cells": [], "cur": None}))
                i += 1
                continue

            if stack and tag == TAG_LIST_HEADER:
                head = read_cell_head(data)
                if head:
                    head["text"] = []
                    stack[-1][1]["cells"].append(head)
                    stack[-1][1]["cur"] = head
                i += 1
                continue

            if tag == TAG_PARA_TEXT:
                t = para_text(data)
                if stack and stack[-1][1]["cur"] is not None:
                    stack[-1][1]["cur"]["text"].append(t)
                elif t.strip():
                    if out and out[-1].get("kind") == "text":
                        out[-1]["text"] += "\n" + t.strip()
                    else:
                        out.append({"kind": "text", "text": t.strip()})
            i += 1

        while stack:
            out.append(_finish(stack.pop()[1]))
    return out


def _finish(tb):
    """셀 목록을 행 단위로 정리한다"""
    rows = {}
    for c in tb["cells"]:
        txt = "\n".join(x for x in ("".join(c["text"]).split("\n")) if x.strip())
        rows.setdefault(c["row"], []).append({
            "col": c["col"], "row": c["row"],
            "colspan": c["colspan"], "rowspan": c["rowspan"],
            "text": txt.strip(),
        })
    ordered = [sorted(rows[k], key=lambda x: x["col"]) for k in sorted(rows)]
    return {
        "kind": "table",
        "rows": ordered,
        "rowCnt": tb["meta"]["rows"] or len(ordered),
        "colCnt": tb["meta"]["cols"] or max((len(r) for r in ordered), default=0),
    }


# ───────────────────────── 글줄 뽑기 ─────────────────────────
def text_lines(path):
    """문서 순서대로 문단 글줄. 표는 행마다 '칸 | 칸 | 칸' 한 줄로 편다."""
    out = []
    for item in extract(path):
        if item["kind"] == "text":
            out.extend(x.strip() for x in item["text"].split("\n") if x.strip())
        else:
            for cells in item["rows"]:
                line = " | ".join(c["text"].replace("\n", " ").strip() for c in cells)
                if line.strip(" |"):
                    out.append(line)
    return out
