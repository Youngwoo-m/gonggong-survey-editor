# -*- coding: utf-8 -*-
r"""2026-10-12 검토에서 확신이 높은 지적을 고친다.

■ 어디서 왔나

  작업규정 개정안을 제1편 제1장부터 제7편 보칙까지 검토하여 지적 234건을
  얻었다(저장소 밖 App\검토\). 그 가운데 확신이 높은 94건을 사람이 고치라고
  하였다. 지적마다 지금 자료에서 다시 확인하고, 고칠 안이 하나로 정해지는
  것만 편집으로 적었다. 사람이 골라야 하는 것, 기술 기준값을 새로 정하는 것,
  별표 파일이나 표 개체를 고쳐야 하는 것은 보류로 남겼다.

■ 편집

  편집은 scripts\_review1012_edits.json 에 있다. 하나는 마디 하나의 필드
  하나(body ㆍ title ㆍ status ㆍ reason)에서 글자 그대로의 바꾸기 한 번이다.
  한 필드의 편집은 적힌 차례대로 잇달아 적용하며, `old` 가 그때의 글에 꼭
  한 번 나와야 한다.

  같은 파일의 `final` 에 필드마다 다 고친 뒤의 sha256 을 적어 두었다.
  필드가 이미 그 값이면 건너뛰므로 두 번 돌려도 같다. 새로 고친 필드도 그
  값과 맞아야 한다. 새 글이 옛 글을 품는 편집(꼬리표를 덧붙이는 것 등)이
  있어 「old 가 없으면 고친 것」으로는 가릴 수 없기 때문이다. 들어맞지
  아니하는 필드가 하나라도 있으면 아무것도 쓰지 아니하고 멈춘다.

  현행 자료(reg01.json)와 표ㆍ그림 개체는 손대지 아니한다.

  제6편을 13개 조로 모은 뒤(merge6.py)에는 없어진 마디가 있어 멈춘다.
  이 편집은 그 앞에 이미 들어갔으므로 다시 돌릴 까닭이 없다.

  python scripts\fixreview1012.py            보여만 준다
  python scripts\fixreview1012.py --write    고친다
"""
import collections
import hashlib
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NL = chr(10)
DRAFT = os.path.join(ROOT, "data", "draft2025.json")
EDITS = os.path.join(HERE, "_review1012_edits.json")
STATUS = {"유지", "수정", "이동", "이동·수정", "신설", "삭제"}


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def walk(ns):
    for n in ns:
        yield n
        yield from walk(n.get("children") or [])


def main():
    write = "--write" in sys.argv
    doc = json.load(io.open(DRAFT, encoding="utf-8"))
    pack = json.load(io.open(EDITS, encoding="utf-8"))
    edits, final = pack["edits"], pack["final"]
    byid = {n["id"]: n for n in walk(doc["tree"])}

    fields = collections.OrderedDict()
    for e in edits:
        fields.setdefault((e["id"], e["field"]), []).append(e)

    done, skip, bad, newval = [], [], [], {}
    for (nid, f), es in fields.items():
        n = byid.get(nid)
        key = "%s.%s" % (nid, f)
        if n is None or f not in ("body", "title", "status", "reason"):
            bad.append("마디나 필드가 없음 —— " + key)
            continue
        cur = str(n.get(f) or "")
        if sha(cur) == final[key]:
            skip.append(key)
            continue
        ok = True
        for e in es:
            old, new = e["old"], e["new"]
            if f == "status":
                if cur != old or new not in STATUS:
                    bad.append("상태가 %r 임 —— %s %s" % (cur, e["finding"], key))
                    ok = False
                    break
                cur = new
                continue
            c = cur.count(old) if old else 0
            if c != 1:
                bad.append("old 가 %d번 나옴 —— %s %s 「%s」"
                           % (c, e["finding"], key, old[:60].replace(NL, " / ")))
                ok = False
                break
            cur = cur.replace(old, new, 1)
        if not ok:
            continue
        if sha(cur) != final[key]:
            bad.append("고친 결과가 적어 둔 값과 다름 —— " + key)
            continue
        newval[(nid, f)] = cur
        done.extend(e["finding"] for e in es)

    for (nid, f), v in newval.items():
        byid[nid][f] = v
    per = collections.Counter(done)
    print("필드 %d개(편집 %d개) —— 고칠 것 %d ㆍ 이미 됨 %d ㆍ 어긋남 %d"
          % (len(fields), len(edits), len(newval), len(skip), len(bad)))
    if per:
        print("지적별 편집 수 —— " + " ㆍ ".join("%s %d" % kv for kv in sorted(per.items())))
    for x in bad:
        print("  ! " + x)
    if bad:
        print("어긋난 편집이 있어 쓰지 아니함.")
        sys.exit(1)
    if not write:
        print("표시만 한 것임. 고치려면 --write 를 붙일 것." if newval else "고칠 것 없음.")
        return
    if newval:
        io.open(DRAFT, "w", encoding="utf-8", newline=NL).write(json.dumps(doc, ensure_ascii=False))
    print("고쳤습니다 —— 필드 %d개" % len(newval))


if __name__ == "__main__":
    main()
