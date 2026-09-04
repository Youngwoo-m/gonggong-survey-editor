# -*- coding: utf-8 -*-
r"""표로 서지 못하던 별표 본문의 줄을 한 줄씩으로 고쳐 쓴다.

■ 왜

  annexdoc 은 〔 〕 안의 한 줄을 한 행으로 본다. 칸 수가 머리와 딱 맞을
  때에만 표로 세우고, 하나라도 어긋나면 글줄로 되돌린다 — 짜 맞추다가
  내용이 어긋나는 것이 더 나쁘기 때문이다.

  그런데 본문 가운데에는 한 행이 여러 줄로 벌어져 있거나, 칸 수가 머리와
  맞지 않거나, 아예 〔 〕 로 감싸지 않은 덩이가 아홉 있었다. 그것들이
  종이에서 표가 아니라 글줄로 찍혔다.

■ 무엇을 고치는가

  글은 그대로 두고 **줄만 고쳐 쓴다**. 값을 지어내지 아니한다.

    별표 8   구간과 시각을 한 칸으로 (· C-05 · 14:22 → · C-05 14:22)
    별표 10  보정 전ㆍ후 수평ㆍ수직을 네 칸으로 벌리고, 딸린 말은 ※ 로 뺀다
    별표 11  칸을 일곱으로 맞추고, 설명 줄은 ※ 로 뺀다
    별표 12  '같은 근거' 한 칸을 '같은 기준 · 같은 근거' 두 칸으로
    별표 14  〔 〕 로 감싼다
    별표 15  한 항목이 네댓 줄로 벌어진 것을 한 줄로, 뒤 표는 머리에
             '조치 뒤의 판정' 을 더한다
    별지 3   머리에 '번호' 를 더한다
    별지 5   '일어난 때와 곳' 이 한 칸이므로 때와 곳을 붙인다

  python scripts\annexrow.py            바꿔 볼 것을 보여만 준다
  python scripts\annexrow.py --write    자료에 적는다
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

NL = "\n"


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


# ────────────────────────────────── 글자 그대로 갈아 끼울 것
SWAP = {
    ("draft_uav.json", "별표", "8"): [(
        "  〔· C-05 · 14:22:10~14:22:26 · 교량 하부 통과로 위성 차폐 · 16초 ·",
        "  〔· C-05 14:22:10~14:22:26 · 교량 하부 통과로 위성 차폐 · 16초 ·")],

    ("draft_uav.json", "별표", "10"): [(
        "  〔· C-01/C-02 · 0.9㎞ · 0.000 / 0.000 m → 0.000 / 0.000 m · 적합" + NL
        + "    · C-02/C-03 · 1.1㎞ · 0.000 / 0.000 m → 0.000 / 0.000 m · 적합" + NL
        + "    · C-05/C-06 · 0.7㎞ · 0.000 / 0.000 m → 0.000 / 0.000 m · 적합" + NL
        + "      (교량 하부 위성 차폐 구간 — 별표 5 제5호와 함께 본다)" + NL
        + "    · … 중첩이 있는 코스 짝을 빠뜨리지 아니하고 적는다〕",
        "  〔· C-01/C-02 · 0.9㎞ · 0.000 m · 0.000 m · 0.000 m · 0.000 m · 적합" + NL
        + "    · C-02/C-03 · 1.1㎞ · 0.000 m · 0.000 m · 0.000 m · 0.000 m · 적합" + NL
        + "    · C-05/C-06 · 0.7㎞ · 0.000 m · 0.000 m · 0.000 m · 0.000 m · 적합〕" + NL
        + "  ※ C-05/C-06 은 교량 하부 위성 차폐 구간이다 — 별표 5 제5호와 함께 본다." + NL
        + "  ※ 중첩이 있는 코스 짝을 빠뜨리지 아니하고 적는다.")],

    ("draft_uav.json", "별표", "11"): [(
        "  〔· 제방 마루 · 000,000 · 0 / 000 / 00.0 점/㎡ · 작업계획서가 정한 값 · 0개 · 0%" + NL
        + "    · 비탈면   · 000,000 · 0 / 000 / 00.0 점/㎡ · 같은 값 · 000개 · 0.0%" + NL
        + "    · 둔치     · 000,000 · 0 / 000 / 00.0 점/㎡ · 같은 값 · 0개 · 0%" + NL
        + "    (전체 점 기준과 지면점 기준을 나누어 적는다 — 위는 전체 점 기준)" + NL
        + "    · 지면점 기준 비탈면 · 000,000 · 0 / 00 / 0.0 점/㎡ · 같은 값 · 0,000개 · 0.0%" + NL
        + "      — 식생이 우거진 구간이다" + NL
        + "    · 코스 중첩으로 밀도가 높아진 곳  C-03/C-04 겹침 0.6㎞ 구간 — 평균의 약 2배〕",
        "  〔· 제방 마루 · 000,000 · 0 · 000 · 00.0 점/㎡ · 작업계획서가 정한 값 · 0개 0%" + NL
        + "    · 비탈면 · 000,000 · 0 · 000 · 00.0 점/㎡ · 같은 값 · 000개 0.0%" + NL
        + "    · 둔치 · 000,000 · 0 · 000 · 00.0 점/㎡ · 같은 값 · 0개 0%" + NL
        + "    · 지면점 기준 비탈면 · 000,000 · 0 · 00 · 0.0 점/㎡ · 같은 값 · 0,000개 0.0%〕" + NL
        + "  ※ 전체 점 기준과 지면점 기준을 나누어 적는다 — 위의 셋은 전체 점 기준이다." + NL
        + "  ※ 지면점 기준 비탈면은 식생이 우거진 구간이다." + NL
        + "  ※ 코스 중첩으로 밀도가 높아진 곳도 적는다 — C-03/C-04 겹침 0.6㎞ 구간은"
        + " 평균의 약 2배이다.")],

    ("draft_uav.json", "별표", "12"): [(
        "      · 평탄지 지면점 퍼짐  0.000 m · 같은 근거 · 적합〕",
        "      · 평탄지 지면점 퍼짐 · 0.000 m · 같은 기준 · 같은 근거 · 적합〕")],

    ("draft_uav.json", "별표", "14"): [(
        "     · 정사영상                  GeoTIFF 또는 측량시행자가 승인한 공간참조 영상포맷",
        "     〔· 정사영상 · GeoTIFF 또는 측량시행자가 승인한 공간참조 영상포맷"),
        ("     · DSM, DTM, DEM             GeoTIFF, GRID, ASCII Grid 또는 측량시행자가 승인한 격자포맷",
         "       · DSM, DTM, DEM · GeoTIFF, GRID, ASCII Grid 또는 측량시행자가 승인한 격자포맷"),
        ("     · 레이저측량 점군            LAS 또는 LAZ",
         "       · 레이저측량 점군 · LAS 또는 LAZ"),
        ("     · 수치도화ㆍ객체기반 갱신자료  SHP, GPKG, DXF 또는 측량시행자가 승인한 벡터포맷",
         "       · 수치도화ㆍ객체기반 갱신자료 · SHP, GPKG, DXF 또는 측량시행자가 승인한 벡터포맷"),
        ("     · 품질평가 보고서            PDF 또는 문서형식",
         "       · 품질평가 보고서 · PDF 또는 문서형식"),
        ("     · 메타데이터 및 처리이력      XML, CSV, TXT 또는 측량시행자가 승인한 형식",
         "       · 메타데이터 및 처리이력 · XML, CSV, TXT 또는 측량시행자가 승인한 형식〕")],

    ("draft_uav.json", "별표", "15"): [(
        "  ┌ 항목 ├ 잰 값 ├ 요구 기준(출처) ├ 판정 ├ 조치 ├ 조치 뒤의 값",
        "  ┌ 항목 ├ 잰 값 ├ 요구 기준(출처) ├ 판정 ├ 조치 ├ 조치 뒤의 값"
        + " ├ 조치 뒤의 판정"),
        ("    · 3 검사점 RMSE(수직) · 0.000m · 같은 항 · 적합 · − · −〕",
         "    · 3 검사점 RMSE(수직) · 0.000m · 같은 항 · 적합 · − · − · −〕")],

    ("draft2025.json", "별지", "3"): [(
        "  ┌ 일어날 가능성 ├ 다칠 정도 ├ 위험성 (가능성 × 정도) ├ 판정",
        "  ┌ 번호 ├ 일어날 가능성 ├ 다칠 정도 ├ 위험성 (가능성 × 정도) ├ 판정"),
        ("  〔① 2 × 3 = 6 · 낮추어야 함" + NL
         + "   ② 2 × 4 = 8 · 낮추어야 함" + NL
         + "   ③ 2 × 5 = 10 · 낮추어야 함" + NL
         + "   ④ 3 × 3 = 9 · 낮추어야 함" + NL
         + "   ⑤ 3 × 5 = 15 · 작업 불가〕",
         "  〔① · 2 · 3 · 6 · 낮추어야 함" + NL
         + "   ② · 2 · 4 · 8 · 낮추어야 함" + NL
         + "   ③ · 2 · 5 · 10 · 낮추어야 함" + NL
         + "   ④ · 3 · 3 · 9 · 낮추어야 함" + NL
         + "   ⑤ · 3 · 5 · 15 · 작업 불가〕")],

    ("draft2025.json", "별지", "5"): [(
        "  〔2026-06-11 14:05 · 구간 A ○○로 320m 지점 · 다친 사람 없음(아차사고) ·",
        "  〔2026-06-11 14:05 구간 A ○○로 320m 지점 · 다친 사람 없음(아차사고) ·")],
}


# ────────────────────────── 별표 15 첫 표 — 한 항목이 네댓 줄로 벌어져 있다
RE_ITEM = re.compile(r"^\s*(\d+)\s+(\S.*)$")


def fold_annex15(body):
    """번호 줄 + '·' 조건 줄들 + '→ 서식 · 조치' 줄 → 한 줄"""
    lines = body.split(NL)
    try:
        s = next(i for i, ln in enumerate(lines)
                 if ln.strip().startswith("┌ 번호 ├ 품질관리 항목"))
    except StopIteration:
        return body, 0
    e = s + 1
    while e < len(lines) and lines[e].strip() and not lines[e].strip().startswith("┌"):
        e += 1
    rows, cur = [], None
    for ln in lines[s + 1:e]:
        t = ln.strip()
        if not t:
            continue
        if t.startswith("→"):
            if cur:
                cur["tail"] = t.lstrip("→").strip()
            continue
        if t.startswith("·"):
            if cur:
                cur["cond"].append(t.lstrip("·").strip())
            continue
        m = RE_ITEM.match(ln)
        if m:
            if cur:
                rows.append(cur)
            cur = {"no": m.group(1), "name": m.group(2).strip(), "cond": [], "tail": ""}
    if cur:
        rows.append(cur)
    if not rows:
        return body, 0
    out = []
    for i, r in enumerate(rows):
        head = "  〔· " if i == 0 else "    · "
        tail = r["tail"]
        # '→ 서식 · 조치' 에서 서식과 조치를 가른다 (가름표는 하나뿐이다)
        if " · " in tail:
            form, act = tail.split(" · ", 1)
        else:
            form, act = tail, "−"
        out.append("%s%s · %s · %s · %s · %s"
                   % (head, r["no"], r["name"], " / ".join(r["cond"]) or "−",
                      form.strip(), act.strip()))
    out[-1] += "〕"
    return NL.join(lines[:s + 1] + out + lines[e:]), len(rows)


def main():
    write = "--write" in sys.argv
    total = 0
    for f in ("draft2025.json", "draft_simsa.json", "draft_uav.json"):
        p = os.path.join(DATA, f)
        doc = json.load(io.open(p, encoding="utf-8"))
        touched = False
        for rev in [doc] + list(doc.get("next") or []):
            for x in walk(rev.get("tree") or []):
                a = x.get("annexRef")
                if not a or x.get("status") != "신설":
                    continue
                key = (f, a.get("gubun"), str(a.get("no")))
                body = str(x.get("body") or "")
                start = body
                for old, new in SWAP.get(key, []):
                    if old in body:
                        body = body.replace(old, new, 1)
                    else:
                        print("   ! 못 찾음 %s %s %s — %s"
                              % (f[:12], key[1], key[2], old.split(NL)[0][:46]))
                if key == ("draft_uav.json", "별표", "15"):
                    body, n = fold_annex15(body)
                    if n:
                        print("   별표 15 첫 표 — %d 항목을 한 줄씩으로" % n)
                if body != start:
                    total += 1
                    touched = True
                    x["body"] = body
                    print("   고침 %-13s %s %s — %s"
                          % (f[:12], a.get("gubun"), a.get("no"), str(x.get("title"))[:26]))
        if write and touched:
            io.open(p, "w", encoding="utf-8", newline=NL).write(
                json.dumps(doc, ensure_ascii=False))
    print()
    print("고친 별표ㆍ별지 %d개" % total)
    if not write:
        print("시험만 한 것입니다. 적으려면 --write 를 붙이십시오.")


if __name__ == "__main__":
    main()
