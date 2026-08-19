# -*- coding: utf-8 -*-
"""
원문에서부터 깨져 들어온 글자를 표시로 바꾼다.

「公共測量の手引」(국토지리원) PDF 는 그림·도해에 쓴 글꼴에 유니코드 표가
없어, 국토지리원이 내려 주는 원본에서부터 글자가 깨져 나온다(77쪽 가운데
74쪽, 6,102자). 내려받는 곳을 바꾸어도 같다. 그래서 깨진 자리를 지우고
표시를 남겨, 읽는 이가 번역이 잘못된 것으로 오해하지 않게 한다.

사용:  python scripts/markbroken.py [loc12 …]
"""
import io, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")

# 한국어·일본어·한자·라틴·기호 어디에도 들지 아니하는 글자 = 깨진 자리
RANGES = [(0x0000, 0x001f), (0x0900, 0x0dff), (0x0e80, 0x0fff), (0x1000, 0x10ff),
          (0x1200, 0x139f), (0x1600, 0x1aff), (0x1b00, 0x1cff), (0xa000, 0xa4cf),
          (0xe000, 0xf8ff), (0xfffd, 0xfffd)]
CLS = "".join(f"{chr(a)}-{chr(b)}" for a, b in RANGES)
JUNK = re.compile(f"[{CLS}]")
RUN = re.compile(f"(?:[{CLS}][^\\n]{{0,2}}){{2,}}[{CLS}]?")
MARK = "[원문 그림 속 글자 — 판독 불가]"


def clean(t):
    """깨진 글자가 이어지는 자리를 표시 하나로 갈음한다"""
    if not t:
        return t, 0
    n = len(JUNK.findall(t))
    if not n:
        return t, 0
    out = RUN.sub(MARK, t)          # 이어진 깨짐은 표시 하나로
    out = JUNK.sub("", out)         # 한두 자만 깨진 것은 그냥 지운다
    out = re.sub(r"(?:\s*%s\s*){2,}" % re.escape(MARK), f" {MARK} ", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out, n


def main(ids):
    for rid in ids:
        p = os.path.join(DATA, rid + ".json")
        doc = json.load(io.open(p, encoding="utf-8"))
        got = {"n": 0, "marks": 0}

        def rec(ns):
            for x in ns:
                for fld in ("body", "transBody", "origBody",
                            "title", "transTitle", "origTitle"):
                    t = x.get(fld)
                    if not t:
                        continue
                    new, n = clean(t)
                    if n:
                        x[fld] = new
                        got["n"] += n
                        got["marks"] += new.count(MARK)
                rec(x.get("children") or [])
        rec(doc["tree"])
        doc["note"] = ("국토지리원이 내려 주는 원본 PDF 의 그림·도해 글꼴에 유니코드 표가 "
                       f"없어 그 부분은 글자가 깨져 나옵니다. 깨진 자리는 '{MARK}' 로 "
                       "표시했습니다.")
        with io.open(p, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
        print(f"  {rid}  깨진 글자 {got['n']:,}자를 표시 {got['marks']}개로 갈음했습니다")

    lp = os.path.join(DATA, "library.json")
    lib = json.load(io.open(lp, encoding="utf-8"))
    for r in lib["regulations"]:
        if r["id"] in ids:
            r["note"] = "원본 PDF 의 그림·도해에 깨진 글자가 있어 그 자리를 표시로 갈음했습니다."
    with io.open(lp, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main(sys.argv[1:] or ["loc12"])
