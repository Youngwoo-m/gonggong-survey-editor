# -*- coding: utf-8 -*-
"""
참조 규정 서고 사본 자체를 훑는다 — 담아 온 원문이 성한가.

checkcites 로 개편안의 인용을 맞대어 보다가, 맞대는 잣대인 사본 쪽이
성치 않으면 검사 결과를 믿을 수 없다는 것을 알았다. 고압가스 안전관리법
사본에서 제22조·제26조가 통째로 없는 것을 보고 이 검사를 만든다.

■ 무엇이 흠이고 무엇이 흠이 아닌가

  제목이 빈 조는 대개 흠이 아니다 — 「삭제 <2009.5.22>」 인 조는 원래
  제목이 없다. 전기통신기본법 사본은 71개 조 가운데 63개가 제목이 없는데
  거의 다 삭제된 조다. 제목이 비었다는 것만으로 사본을 의심하면 성한 것을
  깨진 것이라 말하게 된다. 삭제된 조인지부터 가린다.

■ 보는 것

  1) 조 번호가 끊긴 곳 — 삭제 조로 설명되지 아니하는 빈 번호
  2) 제목도 본문도 없는 조 (삭제 조가 아닌데)
  3) 본문 안에 다른 조의 머리가 들어 있는 것 — 조를 못 가른 자국
  4) 목차가 본문으로 샌 것 (점선·쪽번호)
  5) 조 번호가 뒤로 가거나 겹치는 것
  6) library.json 의 조 수와 실제 조 수가 어긋나는 것
  7) 어디에서 언제 받은 것인지 적히지 아니한 것

■ 넣었다가 걷어 낸 것

  제 안을 가리킨 인용이 실제로 있는 조인지 보려 하였다. 번호가 밀린 것을
  가장 잘 짚을 자리라 여겼으나 쓸 수 없었다. 법령은 다른 법령을 줄줄이
  가리키는데 (「하천법」 제10조, 제33조 및 제50조) 뒤따르는 제33조·제50조가
  제 조인지 남의 조인지 글만 보아서는 가릴 수 없다. 도시가스사업법 198건,
  수도법 153건이 죄다 이것이었다. 반쯤 맞는 검사는 없느니만 못하다.

  본조 없이 가지조만 있는 것도 흠이 아니다. 본조가 삭제되면서 통째로
  빠지고 가지조만 남는 일이 흔하다 (수도법 제6조의2·제9조의2 …).

사용:  python scripts/checklib.py [-v] [규정id …]
"""
import io, json, os, re, sys, collections

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

RE_DEL = re.compile(r"^\s*삭제\s*[<〈]")
RE_PROV = re.compile(r"<현행[^<>]*>")
RE_IMG = re.compile(r'<img\s+id="[\w.-]+"></img>')
# 본문 속에 들어앉은 조 머리 — 「제12조(정의) ① …」 꼴
# 괄호 안이 조문 제목처럼 생겨야 한다. 「제40조(제39조의5에서 준용하는 경우를
# 포함한다)에 따른」 같은 인용 괄호는 조 머리가 아니므로 조·항·호·준용을 물리친다.
RE_INNER = re.compile(r"(?:^|[.。\n]\s*)제\s*(\d{1,4})\s*조(?:의\s*\d+)?\s*"
                      r"[（(]\s*(?![^)）]*(?:제\d|조|항|호|준용|따라|포함))"
                      r"([^)）\d]{2,25})\s*[)）]\s*(?=[①-⑳])")
DOTS = re.compile(r"[·․‥…]{5,}|[.]{6,}")
PAGENO = re.compile(r"(?:^|\n)\s*-\s*\d{1,3}\s*-\s*(?:$|\n)")


def clean(t):
    return RE_IMG.sub("", RE_PROV.sub("", str(t or "")))


def articles(tree):
    out = []

    def rec(ns):
        for x in ns:
            if x.get("level") == "조":
                out.append(x)
            rec(x.get("children") or [])
    rec(tree or [])
    return out


def key_of(x):
    k = str(x.get("no"))
    if x.get("branch"):
        k += "의" + str(x["branch"])
    return k


def audit(reg):
    """한 사본을 훑는다 → {흠 종류: [설명]}"""
    out = collections.defaultdict(list)
    path = os.path.join(DATA, reg.get("file") or (reg["id"] + ".json"))
    if not os.path.exists(path):
        out["사본 파일이 없음"].append(path)
        return out, 0
    doc = json.load(io.open(path, encoding="utf-8"))
    tree = doc.get("tree") or (doc.get("versions") or [{}])[0].get("tree") or []
    A = articles(tree)
    if not A:
        if (reg.get("stats") or {}).get("조"):
            out["조가 하나도 없음"].append(f"library 는 조 {reg['stats']['조']}개라 한다")
        return out, 0

    have = {key_of(x) for x in A}
    is_del = {key_of(x): bool(RE_DEL.match(clean(x.get("body")))) for x in A}

    # 8) 어디에서 언제 받았는가
    if not (doc.get("source") or doc.get("localFile")):
        out["출처가 적히지 아니함"].append("source·localFile 둘 다 없다")
    if not doc.get("effective"):
        out["시행일이 적히지 아니함"].append("effective 가 없다")

    # 7) 조 수
    want = (reg.get("stats") or {}).get("조")
    if want is not None and want != len(A):
        out["library 의 조 수와 다름"].append(f"library {want} · 사본 {len(A)}")

    nos = [int(x["no"]) for x in A if str(x.get("no")).isdigit()]
    base = {n for x, n in zip(A, nos) if not x.get("branch")}

    # 1) 끊긴 번호 — 삭제 조가 있다면 그 자리는 설명이 된다
    if nos:
        gaps = [n for n in range(min(nos), max(nos) + 1) if n not in set(nos)]
        if gaps:
            out["조 번호가 끊김"].append(
                f"{len(gaps)}개 — {', '.join('제%d조' % n for n in gaps[:10])}"
                + (" …" if len(gaps) > 10 else ""))
    # 5) 차례 — 목차를 뼈대로 삼은 매뉴얼은 장마다 번호가 다시 시작한다
    seq = ([] if reg.get("indexMode") == "목차"
           else [(int(x["no"]), int(x.get("branch") or 0)) for x in A
                 if str(x.get("no")).isdigit()])
    for i in range(1, len(seq)):
        if seq[i] < seq[i - 1]:
            out["조 차례가 뒤로 감"].append(
                f"제{seq[i - 1][0]}조 뒤에 제{seq[i][0]}조")
    # 목차를 뼈대로 삼은 매뉴얼은 장마다 번호가 다시 시작하므로 겹치는 것이 정상이다
    dup = ([] if reg.get("indexMode") == "목차"
           else [k for k, v in collections.Counter(key_of(x) for x in A).items() if v > 1])
    if dup:
        out["조 번호가 겹침"].append(", ".join(f"제{k}조" for k in dup[:10]))

    for x in A:
        body = clean(x.get("body"))
        lbl = f"제{key_of(x)}조"

        # 2) 삭제 조가 아닌데 비었다
        if not (x.get("title") or "").strip() and not body.strip():
            out["제목도 본문도 없음"].append(lbl)
        elif not body.strip():
            out["본문이 없음"].append(f"{lbl}({x.get('title')})")

        # 5) 목차가 샘
        if DOTS.search(body) or PAGENO.search(body):
            out["목차가 본문에 섞임"].append(f"{lbl}({x.get('title')})")

        if is_del.get(key_of(x)):
            continue

        # 3) 본문 안에 다른 조의 머리 — 조문 규정에서만 본다.
        #    매뉴얼은 다른 법령의 조문을 통째로 인용해 싣는 것이 예사다
        #    (측량 안전관리 매뉴얼이 「측량법」 제10조의2 를 그대로 옮겨 적는다).
        if reg.get("indexMode") == "목차":
            continue
        for m in RE_INNER.finditer(body):
            if m.group(1) != str(x.get("no")):
                out["본문에 다른 조가 들어앉음"].append(
                    f"{lbl} 안에 제{m.group(1)}조 — …{body[max(0, m.start() - 20):m.end() + 24].strip()}…")
                break

    return out, 0


def main():
    verbose = "-v" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    lib = json.load(io.open(os.path.join(DATA, "library.json"), encoding="utf-8"))
    regs = [r for r in lib["regulations"] if not only or r["id"] in only]

    rows, total = [], 0
    for r in regs:
        bad, n_self = audit(r)
        n = sum(len(v) for v in bad.values())
        total += n
        if n:
            rows.append((n, r, bad))
    rows.sort(key=lambda v: -v[0])

    print(f"서고 사본 {len(regs)}종을 훑었습니다 — 흠이 있는 사본 {len(rows)}종 · 모두 {total}건\n")
    for n, r, bad in rows:
        print(f"■ {r['id']} 「{r['name']}」 — {n}건")
        for k in sorted(bad, key=lambda k: -len(bad[k])):
            v = bad[k]
            print(f"    {k} {len(v)}건")
            for one in (v if verbose else v[:3]):
                print(f"        {one}")
            if not verbose and len(v) > 3:
                print(f"        … 그 밖에 {len(v) - 3}건")
        print()
    return total


if __name__ == "__main__":
    main()
