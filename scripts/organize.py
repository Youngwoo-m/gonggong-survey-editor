# -*- coding: utf-8 -*-
r"""App\관련규정 의 파일을 규정 갈래별 폴더로 이동하고 별표 파일명을 정비함.

matchfiles.py 가 지은 짝을 근거로 함. 짝의 타당성은 사람이 이미 확인하였음.

■ 이동 위치

  편집기가 규정을 묶는 갈래를 그대로 폴더명으로 사용함.

      core     공공측량작업규정        law      상위법령
      review   성과심사관련규정        sub      하위규정
      intl     국외관련규정            kds      건설측량_설계기준
      under    지하시설물관련법령      safety   안전관리규정
      research 연구보고서              etc      기타관련규정

  별표ㆍ별지는 해당 갈래 폴더 아래 `별표서식\` 에 모음.

■ 임자 규정 판정 순서

  ㉠ 상위 폴더명이 규정명과 일치하면 그 규정으로 함.
     「[별지 1] 위촉장」 처럼 제목만으로는 임자를 가릴 수 없는 별표가
     여럿 있으므로, 폴더명이 가장 확실한 근거임.
  ㉡ 파일명에 규정명이 드러나면 그 규정으로 함(matchfiles.match).
  ㉢ 규정별 별표 목록과 제목을 대조함(matchfiles.by_annex).

■ 파일명 정비 범위

  규정 본문 파일은 이미 규정명, 고시번호, 시행일을 갖추어 정비 대상이 아님.
  정비 대상은 별표임. `하위규정\별표서식` 에 329개가 뒤섞여 있어 파일명만
  으로는 임자 규정 식별이 불가하므로 임자 규정을 앞에 붙임.

      [별표 10] 3차원 국토공간정보 품질관리표(자료취득 및 편집).hwpx
      [3차원국토공간정보구축작업규정] 별표 10 3차원 국토공간정보 품질관리표….hwpx

  윈도우 경로 길이 제한이 260자이므로 규정명은 40자, 파일명 전체는 150자로
  절단함.

■ 같은 자리로 두 파일이 가는 경우

  내용이 같으면 중복이므로 한 벌만 남기고 나머지는 삭제함.
  내용이 다르면 판단이 필요하므로 이동하지 아니하고 보고만 함.

■ 이동 제외 대상

  개정안 작업물(무인비행장치 개정관련의 2020년 판, 2024년 한글파일,
  2025년 연구결과)과 짝을 찾지 못한 파일은 그대로 둠. 자리 결정은
  사람의 몫임.

  python scripts\organize.py            수행 내용 표시
  python scripts\organize.py --write    실제 이동
"""
import hashlib
import io
import json
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import matchfiles as MF                                # noqa: E402

NL = chr(10)
BOX = MF.BOX
NAME_MAX, REG_MAX = 150, 40

GROUP_DIR = {
    "core": "공공측량작업규정", "review": "성과심사관련규정",
    "research": "연구보고서", "law": "상위법령", "sub": "하위규정",
    "intl": "국외관련규정", "kds": "건설측량_설계기준",
    "under": "지하시설물관련법령", "safety": "안전관리규정",
    "etc": "기타관련규정",
}
RE_ANX = re.compile(
    r"^\s*\[?\s*(별표|별지|부록|서식)\s*([\d의\-]+)\s*(?:호서식)?\s*\]?\s*(.*)$")
# 이미 정비한 이름 —— 「[규정명] 별표 10 …」
RE_DONE = re.compile(r"^\[[^\]]{2,60}\]\s*(별표|별지|부록|서식)\s*[\d의\-]+\s")
BAD = re.compile(r'[\\/:*?"<>|]')


def is_annex(stem):
    """별표ㆍ별지 파일인가. 정비 전 이름과 정비 후 이름을 모두 알아본다"""
    return bool(RE_ANX.match(stem) or RE_DONE.match(stem))


def cat_of():
    lib = json.load(io.open(os.path.join(MF.ROOT, "data", "library.json"),
                            encoding="utf-8"))
    return {r["id"]: r.get("category") for r in lib["regulations"]}


def sha(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


RE_MOD = re.compile(r'name="ModifiedDate"[^<]*<', re.S)


def same_doc(a, b):
    """두 파일이 같은 문서인지 판정함.

    바이트가 달라도 같은 문서인 경우가 있음.
      ㉠ HWPX 는 내려받은 시각이 Contents/content.hpf 의 ModifiedDate 에
         박히므로, 같은 자료를 두 번 받으면 그 값만 달라짐.
      ㉡ PDF 는 만든 도구와 압축률에 따라 크기가 달라지므로, 쪽수와
         본문 글자로 견주어야 함.
    """
    if sha(a) == sha(b):
        return True
    ea, eb = os.path.splitext(a)[1].lower(), os.path.splitext(b)[1].lower()
    if ea != eb:
        return False
    if ea in (".hwpx", ".docx", ".xlsx", ".pptx"):
        try:
            import zipfile
            za, zb = zipfile.ZipFile(a), zipfile.ZipFile(b)
            na, nb = sorted(za.namelist()), sorted(zb.namelist())
            if na != nb:
                return False
            for n in na:
                da, db = za.read(n), zb.read(n)
                if da == db:
                    continue
                if not n.endswith("content.hpf"):
                    return False
                # 고친 시각만 다른지 확인함
                sa = RE_MOD.sub("", da.decode("utf-8", "replace"))
                sb = RE_MOD.sub("", db.decode("utf-8", "replace"))
                if sa != sb:
                    return False
            return True
        except Exception:
            return False
    if ea == ".pdf":
        try:
            import fitz
            da, db = fitz.open(a), fitz.open(b)
            if len(da) != len(db):
                return False
            ta = "".join(da[i].get_text() for i in range(len(da)))
            tb = "".join(db[i].get_text() for i in range(len(db)))
            return ta == tb
        except Exception:
            return False
    return False


def by_folder(rel, folders):
    """상위 폴더명이 규정명과 같으면 그 규정을 임자로 봄 (깊은 쪽 우선)"""
    parts = rel.split("/")[:-1]
    for part in reversed(parts):
        got = folders.get(MF.norm(part))
        if got:
            return got
    return None


def short(name):
    """폴더명에 사용할 짧은 규정명. 길이 절단 후 금지 문자 치환"""
    s = BAD.sub("_", str(name or "")).strip()
    s = re.sub(r"\s+", " ", s)
    return s[:REG_MAX].strip()


def newname(fname, regname):
    """별표 파일의 새 이름. 임자 규정을 앞에 붙임"""
    stem, ext = os.path.splitext(fname)
    if RE_DONE.match(stem):
        return None                       # 이미 정비한 이름은 그대로 둔다
    m = RE_ANX.match(stem)
    if not m:
        return None
    gu, no, ti = m.group(1), m.group(2).strip(), m.group(3).strip()
    # 이름 끝에 이미 (규정명) 이 붙어 있으면 제거함. 앞에 붙일 것이므로 중복임
    ti = re.sub(r"\([^()]{6,60}\)\s*$", "", ti).strip()
    ti = re.sub(r"\([^)]*관련[^)]*\)\s*$", "", ti).strip()
    body = " ".join(x for x in ("[%s]" % short(regname), gu, no, ti) if x)
    return BAD.sub("_", body)[:NAME_MAX].strip() + ext


def main():
    write = "--write" in sys.argv
    cat = cat_of()
    table = [(i, n, c, cl, MF.norm(n)) for i, n, c, cl in MF.regs()]
    aidx = MF.annex_index()
    # 갈래 폴더명은 규정명과 헷갈릴 수 있으므로 폴더 판정에서 뺌
    gnames = set(GROUP_DIR.values())
    folders = {}
    for rid, rname, _c, _cl, nn in table:
        if nn and rname not in gnames:
            folders.setdefault(nn, (rid, rname, "폴더명"))

    plan, keep, skip = [], [], []
    for cur, dirs, files in os.walk(BOX):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in sorted(files):
            p = os.path.join(cur, f)
            rel = os.path.relpath(p, BOX).replace(os.sep, "/")
            if rel in MF.DROP_PAIR or any(rel.startswith(x)
                                          for x in MF.DRAFT_DIRS):
                skip.append((rel, "사람이 자리를 정할 대상"))
                continue
            hand = MF.by_hand(rel, table)
            got = (hand or by_folder(rel, folders)
                   or MF.match(f, table) or MF.by_annex(f, aidx))
            if not got:
                skip.append((rel, "짝을 찾지 못함"))
                continue
            # 별칭과 못박은 짝은 「어느 규정의 것인가」 를 알리려는 것이지
            # 자리를 옮기라는 뜻이 아니다. 국외 자료는 받은 곳별로 묶어 둔
            # 폴더가 따로 있고, 일본 준칙의 별표ㆍ부록은 원어 이름 그대로
            # 두어야 원문과 맞대어 볼 수 있다.
            if hand:
                keep.append(rel)
                continue
            rid, rname, _how = got
            g = GROUP_DIR.get(cat.get(rid) or "etc", "기타관련규정")
            isanx = is_annex(os.path.splitext(f)[0])
            nf = (newname(f, rname) or f) if isanx else f
            dst = os.path.normpath(
                os.path.join(BOX, g, "별표서식" if isanx else "", nf))
            if os.path.normpath(p) == dst:
                keep.append(rel)
            else:
                plan.append([p, dst, rel,
                             os.path.relpath(dst, BOX).replace(os.sep, "/")])

    # ── 같은 자리로 가는 것을 가림. 내용이 같으면 중복, 다르면 보류
    grp = {}
    for row in plan:
        grp.setdefault(row[1], []).append(row)
    plan, dup, hold = [], [], []
    for dst, rows in grp.items():
        if len(rows) == 1:
            plan.append(rows[0])
            continue
        head = rows[0]
        if all(same_doc(head[0], r[0]) for r in rows[1:]):
            plan.append(head)
            dup.extend(rows[1:])
        else:
            hold.extend(rows)

    print("이동 대상 %d건, 제자리 유지 %d건, 중복 삭제 %d건, 보류 %d건, 제외 %d건"
          % (len(plan), len(keep), len(dup), len(hold), len(skip)))
    if dup:
        print()
        print("중복 삭제 대상 (내용이 같은 파일이 이미 있음)")
        for r in dup:
            print("   %s" % r[2])
    if hold:
        print()
        print("보류 (같은 이름이나 내용이 다름)")
        for r in hold:
            print("   %s" % r[2])
    print()
    byg = {}
    for r in plan:
        g = r[3].split("/")[0]
        byg[g] = byg.get(g, 0) + 1
    print("%-24s %6s" % ("갈래 폴더", "이동"))
    for g in sorted(byg, key=lambda z: -byg[z]):
        print("%-24s %6d" % (g, byg[g]))
    print()
    ren = [r for r in plan if os.path.basename(r[2]) != os.path.basename(r[3])]
    print("파일명 정비 %d건, 보기" % len(ren))
    for r in ren[:6]:
        print("   %s" % os.path.basename(r[2])[:78])
        print("     %s" % os.path.basename(r[3])[:78])

    if not write:
        print()
        print("표시만 한 것임. 이동하려면 --write 를 붙일 것.")
        return

    # 되돌릴 수 있도록 내역을 먼저 적음
    log = [["구분", "원래 자리", "옮긴 자리"]]
    moved, killed = 0, 0
    for a, b, _r1, _r2 in plan:
        os.makedirs(os.path.dirname(b), exist_ok=True)
        if os.path.exists(b):
            if same_doc(a, b):
                log.append(["중복삭제", _r1, _r2])
                os.remove(a)
                killed += 1
                continue
            base, ext = os.path.splitext(b)
            k = 2
            while os.path.exists("%s (%d)%s" % (base, k, ext)):
                k += 1
            b = "%s (%d)%s" % (base, k, ext)
        shutil.move(a, b)
        log.append(["이동", _r1, os.path.relpath(b, BOX).replace(os.sep, "/")])
        moved += 1
    for r in dup:
        if os.path.exists(r[0]):
            log.append(["중복삭제", r[2], r[3]])
            os.remove(r[0])
            killed += 1
    for cur, dirs, files in os.walk(BOX, topdown=False):
        if cur != BOX and not os.listdir(cur):
            os.rmdir(cur)
    tsv = os.path.join(BOX, "이동내역.tsv")
    io.open(tsv, "w", encoding="utf-8-sig", newline=NL).write(
        NL.join("\t".join(r) for r in log) + NL)
    print()
    print("이동 %d건, 중복 삭제 %d건 완료" % (moved, killed))
    print("내역 : %s" % tsv)


if __name__ == "__main__":
    main()
