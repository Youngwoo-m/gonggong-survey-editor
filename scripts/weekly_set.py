# -*- coding: utf-8 -*-
r"""규정마다 개정안 한 세트를 지어 **판(버전) 폴더**에 담는다.

  App\개정안\<규정>\개정안_작업-1.00\
      개정(안).hwpx                 Form\01.개정안 양식에 얹은 조문 전문과 부칙
      개정(안)_신구대조표.hwpx        Form\02.신구대조표 양식에 얹은 세 칸 대조표
      개정사유서.hwpx                Form\03.개정사유서 양식에 얹은 일곱 절
      별표및별지\…                   그 개정안의 별표ㆍ별지 (hwpx ㆍ pdf)
      지은날.txt                     무엇을 언제 무엇으로 지었는지
  App\개정안\<규정>\버전이력.json     어느 판을 언제 무슨 지문으로 지었는지

■ 판 이름

  작업-2.01 처럼 적는다.

      A     등록부(targets.json)가 규정마다 준 머리글자 — 작업규정 A ㆍ
            성과심사 B ㆍ 무인비행장치 C.
      2     개정안 자료의 몇째 판인가 — 자료에 새 판(next)이 붙으면 오른다.
      01    같은 판을 몇 번째로 지었는가 — 내용이 바뀔 때마다 오른다.

■ 바뀐 것이 없으면 짓지 아니한다

  주마다 돌리는 일이므로, 지난 이레 동안 손댄 것이 없는데도 같은 문서를
  또 지으면 폴더만 늘고 어느 것이 무엇인지 알 수 없게 된다.

  그래서 지을 때마다 그 판의 **지문**(내용을 sha256 으로 줄인 것)을
  버전이력에 적어 둔다. 다음에 돌릴 때 지문이 그대로면 짓지 아니하고
  넘어간다. 지문은 이 세 가지를 함께 본다.

      ㆍ 그 판의 조문 나무(tree) 전부
      ㆍ 부칙(supplement)
      ㆍ 별표ㆍ별지 원본 파일의 길과 크기

  자료는 그대로인데 문서를 짓는 코드를 고쳐 새로 지어야 한다면 --force 를
  준다. 지문이 같아도 짓고 작은 번호를 올린다.

■ 판마다 한 벌씩

  개정안 자료 한 벌에 판이 여럿 있다(본판 + next). 무인비행장치는 2024년
  연구성과와 2025년 연구결과 두 판을 지니고 있다. 판마다 따로 한 벌씩
  지어 두어야 어느 판이 무엇이었는지 뒤에 가려낼 수 있다.

  옛 판은 더 고칠 일이 없으므로 한 번 지어 두면 지문이 바뀌지 아니하여
  다음부터는 저절로 넘어간다.

  사람이 쓴 개정사유서 원고(Report 출력 폴더)는 그 원고를 쓴 판의 것이다.
  판마다 따로 쓴 원고(「… 개정사유서_1판.hwpx」)가 있으면 그것을 쓰고,
  없으면 통짜 원고는 마지막 판에만 쓴다. 그러지 아니하면 2024년 판에
  2025년 사유서가 들어간다.

  python scripts\weekly_set.py                  세 규정의 모든 판 (바뀐 것만)
  python scripts\weekly_set.py --only uav       한 규정만
  python scripts\weekly_set.py --last           마지막 판만
  python scripts\weekly_set.py --force          바뀐 것이 없어도 짓는다
  python scripts\weekly_set.py --check          지을지 말지 보여만 준다
  python scripts\weekly_set.py --migrate        옛 날짜 폴더를 판 폴더로 옮긴다
"""
import datetime
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.dirname(HERE)
APP = os.path.dirname(PROTO)
BASE = os.path.dirname(APP)
OUT = os.path.join(APP, "개정안")
FORM = os.path.join(BASE, "Form")
DATA = os.path.join(PROTO, "data")
LEDGER = "버전이력.json"

# (대상 id, 폴더 이름, 개정안 자료)
REGS = [("work", "작업규정", "draft2025.json"),
        ("review", "성과심사 규정", "draft_simsa.json"),
        ("uav", "무인비행장치 규정", "draft_uav.json")]


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def safe(s):
    return re.sub(r'[\\/:*?"<>|]', "_", str(s or "")).strip()


def today():
    return datetime.date.today().isoformat()


# ─────────────────────────────────────────────────── 판과 지문
def ver_letter(target):
    """등록부가 규정에 준 머리글자 — 없으면 X"""
    try:
        tj = json.load(io.open(os.path.join(DATA, "targets.json"),
                               encoding="utf-8"))
    except Exception:
        return "X"
    for t in (tj.get("targets") or tj):
        if t.get("id") == target:
            return str(t.get("ver") or "X")
    return "X"


def all_revs(draftfile):
    """개정안 자료의 판을 모두 → [(몇째 판, 판 이름, 판, 조문 나무), …]

    자료 한 벌에 판이 여럿 있다(본판 + next). 무인비행장치는 2024년
    연구성과와 2025년 연구결과 두 판을 지니고 있다. 판마다 따로 한 벌씩
    지어 두어야 어느 판이 무엇이었는지 뒤에 가려낼 수 있다.

    몇째 판인가는 genreport_hwpx 의 --rev 와 같은 셈(1부터)이다."""
    d = json.load(io.open(os.path.join(DATA, draftfile), encoding="utf-8"))
    revs = [(d.get("title") or "개정안", d)] + [
        (r.get("title") or "개정안 %d판" % (i + 2), r)
        for i, r in enumerate(d.get("next") or [])]
    return [(i + 1, nm, rv, rv.get("tree") or [])
            for i, (nm, rv) in enumerate(revs)]


def last_rev(draftfile):
    """마지막 판 하나 — 옮기기(migrate)에서만 쓴다"""
    return all_revs(draftfile)[-1]


def annex_files(tree):
    """그 판이 딸고 있는 별표ㆍ별지 원본의 길"""
    out = []
    for x in walk(tree):
        a = x.get("annexRef")
        if not a or x.get("isDeleted"):
            continue
        for k in ("hwpx", "hwp", "pdf"):
            p = a.get(k)
            if p and not str(p).startswith("http"):
                out.append(str(p))
    return out


def fingerprint(rev, tree):
    """이 판의 내용을 한 줄의 지문으로 줄인다.

    조문이 한 글자라도 달라지거나 별표 원본이 갈리면 지문이 바뀐다."""
    h = hashlib.sha256()
    h.update(json.dumps(tree, ensure_ascii=False, sort_keys=True)
             .encode("utf-8"))
    h.update(json.dumps(rev.get("supplement"), ensure_ascii=False,
                        sort_keys=True).encode("utf-8"))
    for p in sorted(set(annex_files(tree))):
        f = os.path.join(PROTO, p)
        sz = os.path.getsize(f) if os.path.exists(f) else -1
        h.update(("%s|%d\n" % (p, sz)).encode("utf-8"))
    return h.hexdigest()


def read_ledger(name):
    p = os.path.join(OUT, name, LEDGER)
    if not os.path.exists(p):
        return []
    try:
        d = json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return []
    return d.get("목록") or []


def write_ledger(name, regname, hist):
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    io.open(os.path.join(d, LEDGER), "w", encoding="utf-8",
            newline="\n").write(json.dumps(
                {"규정": regname, "목록": hist},
                ensure_ascii=False, indent=1) + "\n")


def next_tag(hist, letter, major):
    """같은 판 안에서 작은 번호를 하나 올린다"""
    used = [int(h.get("작은번호", 0)) for h in hist
            if int(h.get("판번호", 0)) == major]
    minor = (max(used) + 1) if used else 0
    return "%s-%d.%02d" % (letter, major, minor), minor


def days_since(iso):
    try:
        d = datetime.date.fromisoformat(str(iso)[:10])
    except Exception:
        return None
    return (datetime.date.today() - d).days


# ─────────────────────────────────────────────────── 짓기
def build_set(target, dst, rev_no=None):
    """genreport_hwpx 로 한 벌을 짓고 그 꾸러미를 풀어 담는다.

    생성기는 세 문서와 별표ㆍ별지를 한 꾸러미(zip)로 낸다. 그것을 그대로
    쓰는 편이 낫다 — 담을 것을 두 곳에서 따로 정하면 어긋난다."""
    import glob
    import zipfile
    tmp = os.path.join(dst, "_꾸러미")
    os.makedirs(tmp, exist_ok=True)
    env = dict(os.environ)
    env["FORM_DIR"] = FORM
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, os.path.join(HERE, "genreport_hwpx.py"),
           "--reg", target, "--out", tmp]
    if rev_no:
        cmd += ["--rev", str(rev_no)]
    r = subprocess.run(
        cmd,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=PROTO, env=env)
    log = (r.stdout or "") + (r.stderr or "")
    zips = sorted(glob.glob(os.path.join(tmp, "*.zip")), key=os.path.getmtime)
    if not zips:
        shutil.rmtree(tmp, ignore_errors=True)
        return [], 0, log
    with zipfile.ZipFile(zips[-1]) as z:
        for n in z.namelist():
            if n.endswith("/"):
                continue
            # 꾸러미가 무엇으로 부르든 '별표및별지' 로 담는다 — 판마다
            # '별표및별지모음' 이기도 하고 '개정(안)_별표및별지모음' 이기도 하다
            out = re.sub(r"^[^/]*별표및별지[^/]*/", "별표및별지/", n)
            p2 = os.path.join(dst, *out.split("/"))
            os.makedirs(os.path.dirname(p2), exist_ok=True)
            io.open(p2, "wb").write(z.read(n))
    shutil.rmtree(tmp, ignore_errors=True)
    docs = sorted(f for f in os.listdir(dst) if f.lower().endswith(".hwpx"))
    box = os.path.join(dst, "별표및별지")
    n_anx = len({os.path.splitext(f)[0] for f in os.listdir(box)}) \
        if os.path.isdir(box) else 0
    return docs, n_anx, log


def stamp(dst, name, tag, revname, major, minor, fp, draftfile, docs, n):
    io.open(os.path.join(dst, "지은날.txt"), "w",
            encoding="utf-8", newline="\r\n").write(
        "\r\n".join([
            "%s 개정안 한 세트" % name,
            "판      : %s  (자료의 %d째 판을 %d번째로 지음)" % (tag, major, minor + 1),
            "판 이름 : %s" % revname,
            "지은 날 : %s" % today(),
            "지문    : %s" % fp,
            "양식    : %s" % FORM,
            "자료    : App\\prototype\\data\\%s" % draftfile,
            "",
            "문서 : " + (", ".join(docs) or "(없음)"),
            "별표ㆍ별지 : %d건" % n,
            "",
            "이 폴더는 scripts\\weekly_set.py 가 만듭니다.",
            "지문이 그대로이면 다음 주에는 짓지 아니합니다.",
        ]) + "\r\n")


# ─────────────────────────────────────────────────── 옛 폴더 옮기기
def migrate():
    """개정안_<날짜> 로 지어 둔 것을 판 폴더로 옮기고 이력에 올린다.

    한 번만 하면 되는 일이다. 이미 옮겼으면 아무것도 하지 아니한다."""
    for target, name, draftfile in REGS:
        d = os.path.join(OUT, name)
        if not os.path.isdir(d):
            continue
        olds = sorted(f for f in os.listdir(d)
                      if re.match(r"^개정안_\d{4}-\d{2}-\d{2}$", f))
        if not olds:
            print("   %-14s 옮길 것 없음" % name)
            continue
        hist = read_ledger(name)
        letter = ver_letter(target)
        major, revname, rev, tree = last_rev(draftfile)
        fp = fingerprint(rev, tree)
        for old in olds:
            tag, minor = next_tag(hist, letter, major)
            src, dst = os.path.join(d, old), os.path.join(d, "개정안_" + tag)
            if os.path.exists(dst):
                print("   %-14s %s 는 이미 있습니다 — 그대로 둡니다" % (name, tag))
                continue
            os.rename(src, dst)
            docs = sorted(f for f in os.listdir(dst)
                          if f.lower().endswith(".hwpx"))
            box = os.path.join(dst, "별표및별지")
            n = len({os.path.splitext(f)[0] for f in os.listdir(box)}) \
                if os.path.isdir(box) else 0
            stamp(dst, name, tag, revname, major, minor, fp, draftfile, docs, n)
            hist.append({"판": tag, "판번호": major, "작은번호": minor,
                         "판이름": revname, "지은날": old[len("개정안_"):],
                         "지문": fp, "폴더": "개정안_" + tag,
                         "문서": docs, "별표ㆍ별지": n,
                         "적바림": "날짜 폴더에서 옮김 (%s)" % old})
            print("   %-14s %s → %s" % (name, old, "개정안_" + tag))
        write_ledger(name, name, hist)


# ─────────────────────────────────────────────────── 들머리
def main():
    if "--migrate" in sys.argv:
        print("━━ 옛 날짜 폴더를 판 폴더로 옮깁니다")
        migrate()
        return

    force = "--force" in sys.argv
    check = "--check" in sys.argv
    lastonly = "--last" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    built, skipped = [], []

    for target, name, draftfile in REGS:
        if only and target != only:
            continue
        letter = ver_letter(target)
        revs = all_revs(draftfile)
        if lastonly:
            revs = revs[-1:]
        hist = read_ledger(name)
        print("━━ %s  — 판 %d개" % (name, len(revs)))

        for major, revname, rev, tree in revs:
            fp = fingerprint(rev, tree)
            # 같은 판을 같은 지문으로 이미 지었는가
            mine = [h for h in hist if int(h.get("판번호", 0)) == major]
            # 지문이 같은 것이 여럿이면 가장 나중 것을 든다 — 앞의 것을
            # 집으면 심사-1.01 을 지어 두고도 심사-1.00 이라 알리게 된다
            same = next((h for h in reversed(mine) if h.get("지문") == fp), None)
            print("   %d째 판 「%s」" % (major, revname[:44]))

            if same:
                gone = not os.path.isdir(
                    os.path.join(OUT, name, same.get("폴더", "")))
                ago = days_since(same.get("지은날"))
                if not gone and not force:
                    print("      ├ 이미 %s 로 지어 두었고 지문이 그대로입니다%s."
                          % (same.get("판"),
                             "" if ago is None else " (%d일 전)" % ago))
                    print("      └ 짓지 아니합니다.")
                    skipped.append((name, same.get("판"), ago))
                    continue
                if gone:
                    print("      ! 지어 둔 폴더가 없습니다 — 다시 짓습니다")
            elif mine:
                print("      ├ 지문이 달라졌습니다 — 고친 것이 있습니다.")
            else:
                print("      ├ 아직 지은 적이 없는 판입니다.")

            tag, minor = next_tag(hist, letter, major)
            dst = os.path.join(OUT, name, "개정안_" + tag)
            if check:
                print("      └ 지을 것 : %s" % os.path.basename(dst))
                built.append((name, tag, 0, 0))
                hist.append({"판": tag, "판번호": major, "작은번호": minor,
                             "지문": fp, "폴더": "개정안_" + tag})
                continue

            print("      └ 짓습니다 : %s" % os.path.basename(dst))
            os.makedirs(dst, exist_ok=True)
            docs, n, log = build_set(target, dst, rev_no=major)
            for f in docs:
                print("         %-30s %6dKB"
                      % (f, os.path.getsize(os.path.join(dst, f)) // 1024))
            if not docs:
                print("         ! 문서를 짓지 못했습니다")
                print("         " + log.strip()[-700:].replace("\n", "\n" + "         "))
                shutil.rmtree(dst, ignore_errors=True)
                continue
            print("         별표ㆍ별지 %d건" % n)
            stamp(dst, name, tag, revname, major, minor, fp, draftfile, docs, n)
            hist.append({"판": tag, "판번호": major, "작은번호": minor,
                         "판이름": revname, "지은날": today(), "지문": fp,
                         "폴더": "개정안_" + tag, "문서": docs, "별표ㆍ별지": n,
                         "적바림": "--force 로 지음" if force else "지문이 달라져 지음"})
            write_ledger(name, name, hist)
            built.append((name, tag, len(docs), n))

    print()
    if built:
        print("지은 것 %d" % len(built))
        for name, tag, nd, na in built:
            print("   %-14s %-9s 문서 %d · 별표ㆍ별지 %d" % (name, tag, nd, na))
    if skipped:
        print("고친 것이 없어 넘어간 것 %d" % len(skipped))
        for name, tag, ago in skipped:
            print("   %-14s %-9s %s"
                  % (name, tag, "" if ago is None else "%d일째 그대로" % ago))
    if not built and not skipped:
        print("할 일이 없었습니다")
    print()
    print("담는 곳 — %s" % OUT)


if __name__ == "__main__":
    main()
