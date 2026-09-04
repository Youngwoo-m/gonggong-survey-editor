# -*- coding: utf-8 -*-
r"""제17조(성과패키지)의 「현행 규정」과 「현행의 문제」를 사실대로 다시 쓴다.

■ 무엇이 틀렸는가

  ㉠ 「현행 규정: 없음 — 신설 조문」이라 적혀 있으나, 이 조는 현행 열 조를
     합쳐 만든 것이다. 같은 조문 안의 「개정 사유」가 그 열 조를 이미
     밝히고 있어 서로 맞선다.

  ㉡ 「현행의 문제」가 따옴표 안에서 끊겨 있다. 「마침표가 나오면 줄을
     바꾼다」는 문체 규칙이 인용부호 안의 마침표까지 끊은 탓이다.

         * 연구 검토 결과 서술 방식 불일치 — • 제11조: "성과 등을 제출함.
         * " • 제31조: "성과 등은…정리함.
         * " • 제43조: "성과 등은…정리함.

     따옴표만 남은 줄이 개정사유서에 그대로 나간다.

■ 무엇으로 갈음하는가

  reg01 에서 잰 것만 적는다.

      통합 대상   현행 제31ㆍ43ㆍ59ㆍ74ㆍ93ㆍ109ㆍ119ㆍ130ㆍ167ㆍ191조
      제목        「성과 등의 정리」 여덟, 「성과 등의 관리」 둘
      분량        60자에서 347자까지
      낱말        「성과 등」 여덟 조, 「기록」 일곱 조, 「메타데이터」 네 조

  python scripts\fixreason17.py            보여만 준다
  python scripts\fixreason17.py --write    고친다
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NL = chr(10)
DRAFT = os.path.join(ROOT, "data", "draft2025.json")
SRC = [31, 43, 59, 74, 93, 109, 119, 130, 167, 191]


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def sections(reason):
    out, cur = [], None
    for ln in (reason or "").split(NL):
        m = re.match(r"^\s*○\s*([^:：]{2,20})\s*[:：]\s*(.*)$", ln)
        if m:
            cur = [m.group(1).strip(), []]
            out.append(cur)
            if m.group(2).strip():
                cur[1].append(m.group(2).strip())
        elif cur is not None:
            cur[1].append(ln)
        else:
            out.append([None, [ln]])
    return out


def render(secs):
    L = []
    for name, lines in secs:
        if name is None:
            L.extend(lines)
            continue
        L.append("○ %s:" % name)
        L.extend(lines)
    return NL.join(L)


def main():
    write = "--write" in sys.argv
    cur = json.load(io.open(os.path.join(ROOT, "data", "reg01.json"),
                            encoding="utf-8"))
    old = {}
    for n in walk(cur["tree"]):
        if n.get("level") == "조" and n.get("no") in SRC:
            old[n["no"]] = (n.get("title") or "", n.get("body") or "")
    titles = {}
    for t, _b in old.values():
        titles[t] = titles.get(t, 0) + 1
    lens = sorted(len(b) for _t, b in old.values())
    n_deung = sum(1 for _t, b in old.values() if "성과 등" in b)
    n_rec = sum(1 for _t, b in old.values() if "기록" in b)
    n_meta = sum(1 for _t, b in old.values() if "메타데이터" in b)
    tt = " ㆍ ".join("「%s」 %d조" % (t, c)
                     for t, c in sorted(titles.items(), key=lambda z: -z[1]))

    doc = json.load(io.open(DRAFT, encoding="utf-8"))
    target = None
    for n in walk(doc["tree"]):
        if (n.get("level") == "조" and n.get("no") == 17
                and n.get("origin") == "통합"):
            target = n
            break
    if not target:
        sys.exit("제17조를 찾지 못했습니다")

    secs = sections(target["reason"])
    for s in secs:
        if s[0] == "현행 규정":
            s[1] = ["",
                    "* 현행 제%s조 열 곳에 나뉘어 있었음."
                    % "ㆍ".join(str(x) for x in SRC),
                    ""]
        elif s[0] == "현행의 문제":
            s[1] = ["",
                    "* 성과를 어떻게 정리하여 낼 것인가를 정한 조문이 편마다 "
                    "따로 있어 열 곳에 흩어져 있음.",
                    "* 제목부터 갈림 — %s." % tt,
                    "* 분량도 %d자에서 %d자까지 고르지 아니함." % (lens[0], lens[-1]),
                    "* 부르는 이름이 갈림 — 「성과 등」 %d조, 「기록」 %d조, "
                    "「메타데이터」 %d조에서 쓰나 무엇을 가리키는지 정한 곳이 없음."
                    % (n_deung, n_rec, n_meta),
                    "* 무엇을 내야 하는지가 조문마다 다르게 읽혀, 빠뜨린 것을 두고 "
                    "반려 여부를 다투게 됨.",
                    ""]
        elif s[0] == "관련 근거":
            s[1] = ["",
                    "* 규정 체계 정비 — 편마다 되풀이되던 현행 조문 열 개를 "
                    "총칙 한 곳으로 모음.",
                    ""]
    target["_new"] = render(secs)

    print("── 제17조 %s" % target.get("title"))
    for s in sections(target["_new"]):
        if s[0] in ("현행 규정", "현행의 문제", "관련 근거"):
            print("  ○ %s" % s[0])
            for ln in s[1]:
                if ln.strip():
                    print("     %s" % ln.strip())
    if not write:
        print()
        print("표시만 한 것임. 고치려면 --write 를 붙일 것.")
        return
    target["reason"] = target.pop("_new")
    io.open(DRAFT, "w", encoding="utf-8", newline=NL).write(
        json.dumps(doc, ensure_ascii=False))
    print()
    print("고쳤습니다.")


if __name__ == "__main__":
    main()
