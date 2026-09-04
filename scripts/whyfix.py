# -*- coding: utf-8 -*-
r"""「현행의 문제」가 조문과 어긋난 조를 하나씩 꺼내고 채워 넣는다.

■ 무엇이 어긋났는가

  「현행의 문제」에 이렇게 적힌 조가 104개 있다.

      * 이 조문의 내용에는 고칠 것이 없고, 규정 전체의 편제를 다시 나누는
        데 따라 자리만 이동.
      * 이 서식 자체에는 지적된 것이 없음.

  그런데 같은 조의 「개정 사유」에는 무엇을 왜 고쳤는지가 적혀 있고, 본문도
  참말 바뀌었다. 앞뒤가 맞지 아니한다. 개정사유서를 읽는 사람은 「고칠 것이
  없다」 는 조가 왜 바뀌었는지 알 수 없다.

■ 지어내지 아니한다

  「현행의 문제」는 「개정 사유」와 「관련 근거」를 거울처럼 뒤집은 것이다.
  고친 까닭이 있으면 고치기 전의 문제도 있다. 그러므로 이 도구는 그 두
  마디를 함께 꺼내 보여 준다 —— 사람은 거기 적힌 것만으로 문제를 적는다.

■ 쓰는 법

    python scripts\whyfix.py out 6        아직 안 고친 조를 꺼낸다
    python scripts\whyfix.py in 파일.json  {"규정|노드id": ["* 문장", …]}
    python scripts\whyfix.py stat         어디까지 왔는가

  넣기는 「○ 현행의 문제:」 아래의 줄만 갈아 끼운다. 다른 마디는 건드리지
  아니한다.
"""
import io
import json
import os
import re
import sys
import difflib

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NL = chr(10)

SETS = [("작업규정", "data/draft2025.json", "data/reg01.json"),
        ("성과심사", "data/draft_simsa.json", "data/reg29.json"),
        ("무인비행장치", "data/draft_uav.json", "data/reg12.json")]
NOPROB = ("고칠 사유가 확인되지 않았음", "지적된 것이 없음", "짚은 마디가 따로 없음",
          "고칠 것이 없음", "고칠 것이 없고")
HEAD = re.compile(r"^\s*○\s*([^:：]{2,20})\s*[:：]\s*(.*)$")
HANG = re.compile(r"(?=[①-⑳])")
PROB = "현행의 문제"


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def revs_of(d):
    nx = d.get("next")
    return [d] + (nx if isinstance(nx, list) else ([nx] if isinstance(nx, dict) else []))


def tidy(s):
    return NL.join(x.rstrip() for x in str(s or "").split(NL)).strip()


def parts(body):
    t = tidy(body)
    if not t:
        return []
    p = [x.strip() for x in HANG.split(t) if x.strip()]
    return p if len(p) > 1 else [x.strip() for x in t.split(NL) if x.strip()]


def secs(reason):
    """사유 글 → {마디 이름: [줄, …]} (차례 지킴)"""
    out, k = {}, None
    for ln in str(reason or "").split(NL):
        m = HEAD.match(ln)
        if m:
            k = m.group(1).strip()
            out.setdefault(k, [])
            if m.group(2).strip():
                out[k].append(m.group(2).strip())
        elif k and ln.strip():
            out[k].append(ln.strip())
    return out


def put_prob(reason, lines):
    """「○ 현행의 문제:」 아래를 갈아 끼운다. 다른 마디는 그대로 둔다."""
    src = str(reason or "").split(NL)
    out, i, done = [], 0, False
    while i < len(src):
        m = HEAD.match(src[i])
        if m and m.group(1).strip() == PROB:
            out.append("○ %s:" % PROB)
            out.append("")
            out.extend(lines)
            i += 1
            # 다음 ○ 마디를 만날 때까지 건너뛴다
            while i < len(src):
                m2 = HEAD.match(src[i])
                if m2 and m2.group(1).strip() != PROB:
                    break
                i += 1
            out.append("")
            done = True
            continue
        out.append(src[i])
        i += 1
    return (NL.join(out), done)


def collect():
    """고쳐야 할 조 —— [(규정, 개정안 파일, 마디, 현행 마디)]"""
    got = []
    for name, dp, cp in SETS:
        cur = json.load(io.open(os.path.join(ROOT, cp), encoding="utf-8"))
        old = {}
        for n in walk(cur["tree"]):
            if n.get("level") == "조" and n.get("no"):
                old[int(n["no"])] = n
        doc = json.load(io.open(os.path.join(ROOT, dp), encoding="utf-8"))
        for rev in revs_of(doc):
            for n in walk(rev.get("tree") or []):
                if n.get("level") != "조":
                    continue
                # why92.py 와 같은 잣대를 쓴다 —— 두 벌을 두지 아니한다.
                if (n.get("status") or "유지") in ("유지", "이동", "삭제"):
                    continue
                t = " ".join(secs(n.get("reason")).get(PROB) or [])
                if not any(x in t for x in NOPROB):
                    continue
                # legacyNo 는 「제46조」 이기도 하고 「별표 46」 이기도 하다.
                # 숫자만 뽑으면 별표 46 이 제46조로 둔갑한다. 조일 때만 본다.
                lg = str(n.get("legacyNo") or "")
                m = re.match(r"^\s*제?\s*(\d+)\s*조", lg)
                o = old.get(int(m.group(1))) if m else None
                # 글자까지 같으면 상태 문제이지 사유 문제가 아니다
                if o and tidy(o.get("body")) == tidy(n.get("body"))                         and tidy(o.get("title")) == tidy(n.get("title")):
                    continue
                got.append((name, dp, n, o))
    return got


def brief(o, n, k=4):
    """현행 → 개정, 무엇이 달라졌는가 (몇 줄만)"""
    a = parts(o.get("body") if o else "")
    b = parts(n.get("body"))
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            for x in b[j1:j2]:
                out.append(("보탬", "", x))
        elif tag == "delete":
            for x in a[i1:i2]:
                out.append(("뺌", x, ""))
        else:
            for t in range(max(i2 - i1, j2 - j1)):
                x = a[i1 + t] if i1 + t < i2 else ""
                y = b[j1 + t] if j1 + t < j2 else ""
                out.append(("고침" if x and y else ("보탬" if y else "뺌"), x, y))
    return out[:k], len(out), len(a), len(b)


def cut(s, n=96):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[:n] + "…"


def cmd_out(cnt):
    got = collect()
    for name, dp, n, o in got[:cnt]:
        s = secs(n.get("reason"))
        d, tot, na, nb = brief(o, n)
        print("=== %s|%s | 제%s조 %s [%s]"
              % (name, n.get("id"), n.get("no"), n.get("title"), n.get("status")))
        print("  현행 : %s" % cut(" / ".join(s.get("현행 규정") or ["없음"]), 90))
        print("  본문 : 현행 %d항 %d자 → 개정 %d항 %d자 · 달라진 자리 %d"
              % (na, len(o.get("body") or "") if o else 0,
                 nb, len(n.get("body") or ""), tot))
        for tag, x, y in d:
            print("       [%s] %s%s%s" % (tag, cut(x, 60), " → " if x and y else "", cut(y, 60)))
        for key in ("관련 근거", "개정 사유", "개정 내용"):
            if s.get(key):
                print("  %s :" % key)
                for ln in s[key][:8]:
                    print("       %s" % cut(ln, 120))
        print()
    print("---- %d개 꺼냄 (남은 것 %d개)" % (min(cnt, len(got)), len(got)))


def cmd_in(path):
    want = json.load(io.open(path, encoding="utf-8"))
    n_ok = 0
    for name, dp, cp in SETS:
        p = os.path.join(ROOT, dp)
        doc = json.load(io.open(p, encoding="utf-8"))
        hit = 0
        for rev in revs_of(doc):
            for n in walk(rev.get("tree") or []):
                # 마디 id 는 규정마다 겹친다 (a3 가 세 규정에 다 있다).
                # 규정 이름을 앞에 붙여야 엉뚱한 규정을 덮지 아니한다.
                key = "%s|%s" % (name, n.get("id"))
                if key not in want:
                    continue
                lines = want[key]
                if isinstance(lines, str):
                    lines = [lines]
                new, done = put_prob(n.get("reason"), lines)
                if not done:
                    print("   「현행의 문제」 마디가 없음 — %s" % key)
                    continue
                n["reason"] = new
                hit += 1
        if hit:
            io.open(p, "w", encoding="utf-8", newline=NL).write(
                json.dumps(doc, ensure_ascii=False))
            print("   %-8s %d개" % (name, hit))
            n_ok += hit
    print("고친 조 %d개 (준 것 %d개)" % (n_ok, len(want)))
    cmd_stat()


def cmd_stat():
    got = collect()
    by = {}
    for name, dp, n, o in got:
        by[name] = by.get(name, 0) + 1
    print("아직 어긋난 조 %d개 %s" % (len(got), by))


if __name__ == "__main__":
    a = sys.argv[1:] or ["stat"]
    if a[0] == "out":
        cmd_out(int(a[1]) if len(a) > 1 else 6)
    elif a[0] == "in":
        cmd_in(a[1])
    else:
        cmd_stat()
