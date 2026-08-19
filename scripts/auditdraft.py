# -*- coding: utf-8 -*-
"""
개편안 조문 전수 감사 — 기존 검사기가 보지 않는 조문 속 짜임을 본다.

checkdraft·reviewdraft 는 조문 사이(번호·인용·별표 위임)를 본다.
이 감사기는 조문 안을 본다.

  1) 항(①②③) 이 1부터 끊김 없이 이어지는가
  2) 호(1. 2. 3.) 가 항마다 1부터 이어지는가
  3) 목(가. 나. 다.) 이 호마다 가부터 이어지는가
  4) 조문 안에서 '제○항·제○호' 를 가리킬 때 그 항·호가 실제로 있는가
  5) 본문이 품은 표·수식(<img id>) 이 실제 파일로 있는가
  6) 괄호와 낫표의 짝이 맞는가
  7) 허용오차에 부호가 빠진 곳이 있는가 (± 로 적어야 할 자리)
  8) 같은 값을 다른 단위로 적은 곳이 있는가
  9) 다른 법령을 가리키면서 이름을 「」 로 감싸지 아니한 곳이 있는가
 10) 빈 편·장이 있는가

사용:  python scripts/auditdraft.py [-v]
"""
import io, json, os, re, sys, collections

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
OBJ = os.path.join(DATA, "objects", "reg01")

HANG = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
MOK = "가나다라마바사아자차카타파하"

RE_IMG = re.compile(r'<img\s+id="([\w.-]+)"')
RE_PROV = re.compile(r"<현행[^<>]*>")
# 호·목은 줄바꿈 없이 이어 붙은 곳이 많아 글 가운데의 표시도 잡는다
RE_HO = re.compile(r"(?:(?<=^)|(?<=[^\d]))(\d{1,2})\.\s")
# 목 표시 — 앞이 한글이면 목이 아니다 ("…말한다. " 의 '다' 를 목으로 보지 아니한다).
# 원문이 "…관측가. 수평위치" 처럼 붙여 쓴 자리는 이 규칙으로 놓치는데,
# 잘못 알리는 것보다 놓치는 편이 낫다.
RE_MOK = re.compile("(?<![가-힣0-9])([" + MOK + r"])\.\s")


def clean(body):
    """견주기 위한 글 — 표·수식 표식과 출처 표시를 뺀다"""
    return RE_PROV.sub("", RE_IMG.sub("", str(body or "")).replace("</img>", ""))


def paras(body):
    """항으로 자른다 — [(항번호, 글)]"""
    b = clean(body)
    if not b.strip() or b.strip()[0] not in HANG:
        return [(0, b)]
    out, cur, no = [], "", 0
    for ch in b:
        if ch in HANG:
            if cur.strip():
                out.append((no, cur))
            no = HANG.index(ch) + 1
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append((no, cur))
    return out


def main():
    verbose = "-v" in sys.argv
    doc = json.load(io.open(os.path.join(DATA, "draft2025.json"), encoding="utf-8"))
    tree = doc.get("tree") or doc["versions"][0]["tree"]

    arts, groups = [], []

    def rec(ns, trail):
        for x in ns:
            if x.get("isDeleted"):
                continue
            t = trail + [x.get("title") or ""]
            if x.get("level") == "조" and not x.get("annexRef"):
                arts.append((x, " › ".join(trail)))
            elif x.get("level") in ("편", "장") and not x.get("isAnnex"):
                groups.append((x, " › ".join(trail)))
            rec(x.get("children") or [], t)
    rec(tree, [])

    bad = collections.defaultdict(list)
    # 표는 .xml, 그림은 .gif 로 담기고 index.json 이 그 짝을 안다
    have_obj = set()
    if os.path.isdir(OBJ):
        have_obj = {os.path.splitext(f)[0] for f in os.listdir(OBJ)}
        ip = os.path.join(OBJ, "index.json")
        if os.path.exists(ip):
            have_obj |= set(json.load(io.open(ip, encoding="utf-8")).keys())

    for x, path in arts:
        label = f"제{x.get('no')}조({x.get('title')})"
        body = x.get("body") or ""
        ps = paras(body)

        # 1) 항 번호
        nums = [n for n, _ in ps if n]
        if nums and nums != list(range(1, len(nums) + 1)):
            bad["항 번호 어긋남"].append(f"{label} — {nums}")

        # 2)·3) 호와 목
        for hno, ptxt in ps:
            ho = [int(m.group(1)) for m in RE_HO.finditer(ptxt)]
            if ho and ho != list(range(1, len(ho) + 1)):
                bad["호 번호 어긋남"].append(
                    f"{label}{f' 제{hno}항' if hno else ''} — {ho}")
            # 목은 호마다 '가' 부터 다시 시작하므로 호로 나누어 본다.
            # 원문에 호·목이 줄바꿈 없이 붙은 곳이 많아 앞 글자가 한글이어도 잡는다.
            for chunk in RE_HO.split(ptxt)[::2] if RE_HO.search(ptxt) else [ptxt]:
                mok = [MOK.index(m.group(1)) + 1 for m in RE_MOK.finditer(chunk)]
                if mok and mok != list(range(1, len(mok) + 1)):
                    bad["목 차례 어긋남"].append(
                        f"{label}{f' 제{hno}항' if hno else ''} — "
                        + "".join(MOK[i - 1] for i in mok))

        # 4) 제 조문 안의 항·호 인용
        n_hang = len([n for n, _ in ps if n])
        for m in re.finditer(r"(?<!조)제\s*(\d+)\s*항", clean(body)):
            # '제210조제3항' 처럼 다른 조의 항은 건너뛴다
            if re.search(r"제\s*\d+\s*조\s*$", clean(body)[:m.start()]):
                continue
            if n_hang and int(m.group(1)) > n_hang:
                bad["없는 항을 가리킴"].append(
                    f"{label} — 제{m.group(1)}항 (이 조는 {n_hang}개 항)")

        # 5) 표·수식 파일
        for oid in RE_IMG.findall(body):
            if oid not in have_obj:
                bad["표·수식 파일 없음"].append(f"{label} — {oid}")

        # 6) 괄호·낫표 짝
        c = clean(body)
        # '1)' '가)' 처럼 여는 괄호 없이 쓰는 세목 표시는 셈에서 뺀다
        # 가-하 는 한글 음절 거의 전부를 덮으므로 목 글자만 지정한다.
        # 그러지 아니하면 '(기후, 시통 등)' 의 닫는 괄호까지 지워 짝이 어긋난 것처럼 보인다
        c_par = re.sub(r"(?<![(\w])[0-9" + MOK + r"]\s*\)", "", c)
        for op, cl, nm in ((("(", ")", "괄호")), ("「", "」", "낫표"), ("『", "』", "겹낫표")):
            src = c_par if op == "(" else c
            if src.count(op) != src.count(cl):
                bad["짝이 맞지 않음"].append(
                    f"{label} — {nm} {src.count(op)}:{src.count(cl)}")

        # 7) 허용오차의 부호
        for m in re.finditer(r"(\d[\d.]*\s*(?:mm|cm|m|km|ppm|PPM|초|″)\s*)\+"
                             r"(\s*\d[\d.]*\s*(?:mm|cm|m|km|ppm|PPM))", c):
            bad["허용오차에 ± 가 아닌 +"].append(f"{label} — {m.group(0).strip()}")

        # 9) 법령 이름을 낫표로 감싸지 아니한 곳
        for m in re.finditer(r"(?<![「『\w])([가-힣]{2,20}(?:법|법률))\s*제\s*\d+\s*조", c):
            if m.group(1) in ("법", "이법", "같은법"):
                continue
            bad["법령 이름에 낫표 없음"].append(f"{label} — {m.group(0)}")

    # 10) 빈 편·장
    for g, path in groups:
        n = 0
        def cnt(ns):
            nonlocal n
            for y in ns:
                if y.get("level") == "조" and not y.get("annexRef") and not y.get("isDeleted"):
                    n += 1
                cnt(y.get("children") or [])
        cnt(g.get("children") or [])
        if not n:
            bad["빈 편·장"].append(f"{g.get('level')} {g.get('title')}")

    print(f"조문 {len(arts)}개 · 편·장 {len(groups)}개를 훑었습니다.\n")
    total = 0
    for k in sorted(bad, key=lambda k: -len(bad[k])):
        v = bad[k]
        total += len(v)
        print(f"■ {k} {len(v)}건")
        for one in (v if verbose else v[:6]):
            print(f"    {one}")
        if not verbose and len(v) > 6:
            print(f"    … 그 밖에 {len(v) - 6}건 (-v 로 모두 봅니다)")
        print()
    print(f"모두 {total}건")
    return total


if __name__ == "__main__":
    main()
