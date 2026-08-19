# -*- coding: utf-8 -*-
"""
개편안 초안 전체 검증 — 사람이 눈으로 훑기 어려운 것을 기계가 짚는다.

  1) 빈 본문 조문
  2) 항 번호가 어긋난 조문 (①②③ 순서·건너뜀)
  3) 본문이 가리키는 '제N항' 이 그 조문에 없는 경우
  4) 본문이 가리키는 '제N조' 가 개편안에 없는 경우 (현행 번호 기준)
  5) 색인에 없는 <img id>
  6) 목록에 없는 별표·별지를 가리키는 조문
  7) 제목이 같은 조문이 한 장 안에 둘 이상
  8) 사유가 비어 있는 신설·수정·이동 조문
  9) 정의 조문 밖에 남은 용어 정의

사용:  python scripts/checkdraft.py
"""
import io, json, os, re, sys, collections

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
MARK = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
RE_IMG = re.compile(r'<img\s+id="([\w.-]+)"')
RE_HANG = re.compile(r"제\s*(\d+)\s*항")
RE_JO = re.compile(r"(?<![가-힣A-Za-z])제\s*(\d+)\s*조")
RE_ANX = re.compile(r"별(표|지)\s*제?\s*(\d+)")
DEFP = re.compile(r'["“]([^"”]{1,40})["”]\s*(?:이란|란|이라 함은|라 함은)')


def rows(tree):
    out = []
    def walk(ns, part, chap, anx):
        for x in ns:
            if x.get("isDeleted"):      # 없앤 것을 모아 둔 묶음은 세지 않는다
                continue
            a = anx or bool(x.get("isAnnex"))
            lv = x.get("level")
            if lv == "편":
                walk(x.get("children") or [], x["title"], "", a)
            elif lv == "장":
                walk(x.get("children") or [], part, x["title"], a)
            elif lv == "조":
                out.append({"part": part, "chap": chap, "anx": a, "n": x})
            else:
                walk(x.get("children") or [], part, chap, a)
    walk(tree, "", "", False)
    return out


def paras(body):
    body = (body or "").strip()
    if not body or body[0] not in MARK:
        return []
    out, cur = [], ""
    for ch in body:
        if ch in MARK and cur.strip():
            out.append(cur.strip())
            cur = ch
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def main():
    d = json.load(io.open(os.path.join(DATA, "draft2025.json"), encoding="utf-8"))
    idx = json.load(io.open(os.path.join(DATA, "objects", "reg01", "index.json"),
                            encoding="utf-8"))
    rs = rows(d["tree"])
    arts = [r for r in rs if not r["anx"]]
    annex = [r for r in rs if r["anx"]]
    # 본문의 '제N조' 인용은 개편안의 조 번호를 가리킨다. 번호를 다시 매길 때
    # 본문의 인용도 함께 옮기므로(gendraft2025.py) 지금 번호로 확인한다.
    have_jo = {f"제{r['n'].get('no')}조" for r in arts}
    was_jo = {str(r["n"].get("legacyNo") or "").replace(" ", "") for r in arts}
    have_anx = {str(r["n"].get("legacyNo") or "").replace(" ", "") for r in annex}
    bad = collections.OrderedDict()
    def add(k, s):
        bad.setdefault(k, []).append(s)

    for r in arts:
        n = r["n"]
        no = n.get("legacyNo") or "신설"
        who = f"{no} 「{n['title']}」 [{r['part']}>{r['chap']}]"
        body = n.get("body") or ""
        # 출처 표시 <현행 제N조 「…」> 는 인용이 아니라 꼬리표다
        probe = re.sub(r"<[^<>]{0,80}>", " ", body)

        if not body.strip():
            add("빈 본문", who)

        ps = paras(body)
        if ps:
            want = [MARK[i] for i in range(len(ps))]
            got = [p[0] for p in ps]
            if got != want:
                add("항 번호 어긋남", f"{who} — {''.join(got)}")
            for m in RE_HANG.finditer(probe):
                if re.search(r"제\s*\d+\s*조(?:의\s*\d+)?\s*$", probe[:m.start()]):
                    continue          # '제210조제3항' 은 그 조의 항이다
                if int(m.group(1)) > len(ps):
                    add("없는 항을 가리킴", f"{who} — 제{m.group(1)}항 (전체 {len(ps)}항)")
        else:
            for m in RE_HANG.finditer(probe):
                if re.search(r"제\s*\d+\s*조(?:의\s*\d+)?\s*$", probe[:m.start()]):
                    continue
                add("없는 항을 가리킴", f"{who} — 제{m.group(1)}항 (항 구분 없음)")

        for m in RE_JO.finditer(probe):
            # 다른 법령을 가리키는 인용은 뺀다 (「…」 제N조, 시행규칙 제N조 …)
            i = m.start()
            pre = probe[max(0, i - 40):i]
            if "」" in pre or re.search(r"(법|법률|령|시행령|시행규칙|규칙|규정|지침|기준)\s*$", pre.rstrip()):
                continue
            cite = f"제{m.group(1)}조"
            if cite in have_jo:
                continue
            if cite in was_jo:
                add("인용이 현행 번호로 남음", f"{who} — {cite}")
            else:
                add("없는 조를 가리킴", f"{who} — {cite}")

        for i in RE_IMG.findall(body):
            if i not in idx:
                add("색인에 없는 표·그림", f"{who} — {i}")

        for g, k in RE_ANX.findall(probe):
            if f"별{g}{k}" not in have_anx:
                add("없는 별표·별지를 가리킴", f"{who} — 별{g} {k}")

        if n.get("status") in ("신설", "수정", "이동", "이동·수정") and not (n.get("reason") or "").strip():
            add("사유 없음", f"{who} [{n['status']}]")

        if n["title"] != "정의" and not n["title"].endswith("의 정의"):
            got = DEFP.findall(probe)
            if got:
                add("정의 조문 밖의 용어 정의", f"{who} — {', '.join(got[:4])}")

    seen = collections.defaultdict(list)
    for r in arts:
        seen[(r["part"], r["chap"], re.sub(r"\s+", "", r["n"]["title"]))].append(
            r["n"].get("legacyNo") or "신설")
    for (p, c, t), v in seen.items():
        if len(v) > 1:
            add("한 장 안에 같은 제목", f"{p}>{c} 「{t}」 — {', '.join(v)}")

    total = sum(len(v) for v in bad.values())
    print(f"조문 {len(arts)} · 별표·별지 {len(annex)} 를 검증했습니다. 지적 {total}건\n")
    for k, v in bad.items():
        print(f"■ {k} ({len(v)})")
        for s in v[:40]:
            print("   ", s)
        if len(v) > 40:
            print(f"    … 그 밖에 {len(v) - 40}건")
        print()
    return total


if __name__ == "__main__":
    main()
