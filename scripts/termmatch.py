# -*- coding: utf-8 -*-
"""
작업규정과 성과심사 규정의 말을 맞댄다 (할일 ㉳).

두 규정이 같은 것을 다른 말로 부르는 자리를 맞춘다. 성과심사 규정 제2조가
「성과패키지」와 「제품사양서」를 **「공공측량 작업규정」에 따라** 라고 정의해
두었으므로, 알맹이는 작업규정이 정하고 성과심사는 그것을 그대로 불러야 한다.
그런데 정작 두 규정이 구성요소를 다른 네 낱말로 벌여 놓았다.

  자리            작업규정 제17조제2항          성과심사 제2조제12호
  성과패키지 구성  원시자료ㆍ처리 결과물ㆍ        성과데이터ㆍ메타데이터ㆍ
                  메타데이터ㆍ처리이력           품질보고서ㆍ이력자료

무엇을 맞추었는가 (2026-09-07 사람이 정함)
  ① 구성요소는 성과데이터ㆍ메타데이터ㆍ품질보고서ㆍ처리이력 으로 맞춘다.
     - 「이력자료」(성과심사 1곳)보다 쓰임이 많은 「처리이력」(20곳)을 살린다.
     - 성과심사가 11곳에서 쓰는 「품질보고서」를 작업규정 구성에 들인다.
     - 「원시자료ㆍ처리 결과물」은 성과데이터의 하위로 제17조제2항 뒷문장에 남긴다.
  ② 성과패키지의 구성은 작업규정 별표 17이 정하고, 성과심사 별표 5는 그것을
     인용한다. 별표 5에는 성과심사 단위와 접수 시 확인 항목만 남긴다.
  ③ 갈래를 부르는 말은 「측량의 종류」로 맞춘다 (작업규정 제14조ㆍ성과심사 제14조).
  ④ 간행심사 보고서가 축으로 삼는 말(관심지점정보ㆍGeoTIFFㆍVector Tile)은
     작업규정에 한 번도 없다. 포맷 이름을 고시에 박으면 기술이 바뀔 때마다
     고쳐야 하므로 담지 아니하고, 두 규정이 다르게 부를 위험만 검토의견에 적는다.

사용:  python scripts/termmatch.py          무엇을 고칠지 보여만 준다
       python scripts/termmatch.py --write  자료에 적는다
"""
import io, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORK = os.path.join(ROOT, "data", "draft2025.json")
SIMSA = os.path.join(ROOT, "data", "draft_simsa.json")
WRITE = "--write" in sys.argv
NL = chr(10)


def walk(nodes):
    for n in nodes or []:
        yield n
        yield from walk(n.get("children"))


def art(doc, no):
    for n in walk(doc.get("tree") or []):
        if n.get("level") == "조" and n.get("no") == no and not n.get("annexRef"):
            return n
    raise SystemExit("제%d조를 찾지 못하였습니다" % no)


def bump(node):
    st = node.get("status") or "유지"
    if st in ("삭제", "신설"):
        return
    node["status"] = "이동·수정" if st == "이동" else "수정"


def add_note(node, lines):
    """사유 끝에 검토의견을 덧붙인다 —— 이미 있으면 더하지 아니한다"""
    r = node.get("reason") or ""
    head = "○ 규정 사이의 말 맞대기 (2026-09-07):"
    if head in r:
        return False
    body = NL.join([head, ""] + ["* " + x for x in lines])
    node["reason"] = (r.rstrip() + NL + NL + body) if r else body
    return True


# ─────────────────── 작업규정 ───────────────────
WORK_EDITS = [
    (17, "② 성과패키지는 원시자료, 처리 결과물, 메타데이터 및 처리이력으로 구성한다.",
     "② 성과패키지는 성과데이터, 메타데이터, 품질보고서 및 처리이력으로 구성한다. "
     "이 경우 성과데이터에는 원시자료와 처리 결과물을 함께 담는다.",
     "성과심사 규정 제2조제12호가 이 조를 불러 정의하므로 구성요소의 이름을 맞춘다"),
    (17, "③ 성과패키지에는 측량의 유형과 관계없이",
     "③ 성과패키지에는 측량의 종류와 관계없이",
     "갈래를 부르는 말을 제14조(공공측량의 종류)에 맞춘다"),
    (17, "5. 정확도 관리표와 품질평가표",
     "5. 정확도 관리표와 품질평가표를 담은 품질보고서",
     "제2항의 품질보고서가 무엇으로 이루어지는지 밝혀 성과심사가 부를 수 있게 한다"),
    (9, "③ 공정별 정확도 관리 결과는 측량의 유형에 따라 다음 표에서 정하는",
     "③ 공정별 정확도 관리 결과는 측량의 종류에 따라 다음 표에서 정하는",
     "갈래를 부르는 말을 제14조(공공측량의 종류)에 맞춘다"),
    (17, "④ 측량의 유형별로 성과패키지에 담는 성과 등은 별표 17에서 정한다.",
     "④ 측량의 종류별로 성과패키지에 담는 성과 등은 별표 17에서 정한다. "
     "성과심사에서 확인하는 성과패키지의 구성도 이 별표에 따른다.",
     "성과심사 규정 별표 5와 겹치지 아니하도록 구성을 정하는 자리를 이 별표 하나로 못박는다"),
]

WORK_NOTES = {
    17: ["성과심사 규정 제2조제12호는 성과패키지를 「공공측량 작업규정에 따라」 정의하면서도 "
         "구성요소를 성과데이터ㆍ메타데이터ㆍ품질보고서ㆍ이력자료로 적어, 이 조의 "
         "원시자료ㆍ처리 결과물ㆍ메타데이터ㆍ처리이력과 어긋나 있었다.",
         "두 규정의 말을 성과데이터ㆍ메타데이터ㆍ품질보고서ㆍ처리이력으로 맞추고, "
         "원시자료와 처리 결과물은 성과데이터의 하위로 제2항 뒷문장에 남겼다.",
         "성과패키지의 구성을 정하는 별표가 둘(이 규정 별표 17ㆍ성과심사 규정 별표 5)이어서 "
         "제4항에 이 별표가 정한다는 것을 밝히고, 성과심사 별표 5는 이를 인용하도록 하였다."],
    18: ["간행심사 연구보고서(2026)는 디지털 간행심사의 표준 포맷을 GeoTIFFㆍVector TileㆍSHP "
         "셋으로 못박고 관심지점정보(POI)를 수수료와 심사의 축으로 삼는다. 그러나 이 규정에는 "
         "그 말이 한 번도 나오지 아니한다(관심지점정보 0곳ㆍGeoTIFF 0곳ㆍVector Tile 0곳).",
         "보고서가 이 규정을 고치라고 한 것은 아니다 — 232쪽에 「공공측량 작업규정」은 한 번도 "
         "나오지 아니한다. 다만 성과심사 규정에는 간행심사 서식 개편으로 관심지점정보가 "
         "들어왔으므로, 같은 것을 두 규정이 다르게 부를 위험이 생겼다.",
         "포맷 이름을 고시에 박으면 기술이 바뀔 때마다 고쳐야 하므로 이 별표에는 담지 "
         "아니한다. 전자성과 제출 표준 규격(별표 18)을 지을 때 성과 유형별 파일 형식을 "
         "적게 되면 그때 성과심사 규정과 맞대어 같은 이름을 쓰도록 한다."],
}

# ─────────────────── 성과심사 규정 ───────────────────
SIMSA_EDITS = [
    (2, "성과데이터, 메타데이터, 품질보고서 및 이력자료를 하나로 묶어 제출하는",
     "성과데이터, 메타데이터, 품질보고서 및 처리이력을 하나로 묶어 제출하는",
     "「공공측량 작업규정」 제17조제2항의 말에 맞춘다 — 그 규정은 「처리이력」으로 적는다"),
]

SIMSA_NOTES = {
    2: ["성과패키지의 구성을 「이력자료」로 적어 「공공측량 작업규정」 제17조제2항의 "
        "「처리이력」과 어긋나 있었다. 이 호는 그 규정을 불러 정의하므로 말을 맞추었다."],
    32: ["간행심사 신청에 관심지점정보(POI) 목록을 내도록 하였으나, 「공공측량 작업규정」에는 "
         "관심지점정보라는 말이 한 번도 나오지 아니한다. 성과심사와 간행심사가 같은 것을 "
         "다르게 부르지 아니하도록, 작업규정이 전자성과 제출 표준 규격(별표 18)을 지을 때 "
         "이 말과 맞대어 보아야 한다."],
}


# 별표 마디 —— 제목과 본문의 「측량의 유형」 도 「측량의 종류」 로 맞춘다.
# 다만 「성과 유형별 품질요소 평가기준」(별표 15)의 '성과의 유형' 은 다른 축이므로
# 건드리지 아니한다.
ANNEX_EDITS = [
    ("별표", "17", "성과 유형별 성과패키지의 구성", "측량의 종류별 성과패키지의 구성",
     [("측량의 유형별로", "측량의 종류별로")],
     "표의 머리줄과 제목이 어긋나 있었다 —— 표는 측량의 종류로 벌여 놓았다"),
    ("별표", "18", None, None,
     [("측량의 유형이 둘 이상인 경우", "측량의 종류가 둘 이상인 경우"),
      ("별표 17의 유형 이름", "별표 17의 종류 이름")],
     "폴더 이름의 근거가 되는 별표 17의 말에 맞춘다"),
]


def run_annex(path, label):
    """별표 마디의 제목과 본문을 맞춘다"""
    doc = json.load(io.open(path, encoding="utf-8"))
    done, skip = [], []
    by = {}
    for n in walk(doc.get("tree") or []):
        r = n.get("annexRef")
        if r:
            by[(r.get("gubun"), str(r.get("no")))] = n
    for gubun, no, old_title, new_title, subs, why in ANNEX_EDITS:
        n = by.get((gubun, no))
        if not n:
            raise SystemExit("%s %s %s 를 찾지 못하였습니다" % (label, gubun, no))
        hit = False
        if new_title and n.get("title") == old_title:
            n["title"] = new_title
            hit = True
        body = n.get("body") or ""
        for a, b in subs:
            if a in body:
                body = body.replace(a, b)
                hit = True
        n["body"] = body
        if hit:
            bump(n)
            done.append("%s %s — %s" % (gubun, no, why))
        else:
            skip.append("%s %s (이미 되어 있음)" % (gubun, no))
    for x in done:
        print("   " + x)
    for x in skip:
        print("   (건너뜀) " + x)
    if WRITE and done:
        json.dump(doc, io.open(path, "w", encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)
    return len(done)


def run(path, edits, notes, label):
    doc = json.load(io.open(path, encoding="utf-8"))
    done, skip = [], []
    for no, old, new, why in edits:
        a = art(doc, no)
        body = a.get("body") or ""
        # 새 글이 있는지 먼저 본다 —— 옛 글이 새 글의 앞머리이면(「…품질평가표」 →
        # 「…품질평가표를 담은 품질보고서」) 다시 돌릴 때 겹쳐 붙는다
        if new in body:
            skip.append("제%d조 (이미 되어 있음)" % no)
        elif old in body:
            a["body"] = body.replace(old, new, 1)
            bump(a)
            done.append("제%d조 — %s" % (no, why))
        else:
            raise SystemExit("%s 제%d조에서 고칠 글을 찾지 못하였습니다 —— %s"
                             % (label, no, old[:40]))
    for no, lines in notes.items():
        a = art(doc, no)
        if add_note(a, lines):
            done.append("제%d조 — 검토의견 %d줄" % (no, len(lines)))
        else:
            skip.append("제%d조 검토의견 (이미 있음)" % no)
    print("── %s" % label)
    for x in done:
        print("   " + x)
    for x in skip:
        print("   (건너뜀) " + x)
    if WRITE and done:
        json.dump(doc, io.open(path, "w", encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)
    return len(done)


def main():
    n = run(WORK, WORK_EDITS, WORK_NOTES, "공공측량 작업규정")
    n += run_annex(WORK, "공공측량 작업규정 별표")
    n += run(SIMSA, SIMSA_EDITS, SIMSA_NOTES, "성과심사 규정")
    print()
    if WRITE:
        print("적었습니다 — 고친 자리 %d곳" % n)
    else:
        print("보여만 주었습니다 —— 적으려면 --write 를 붙이십시오.")


if __name__ == "__main__":
    main()
