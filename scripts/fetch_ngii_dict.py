# -*- coding: utf-8 -*-
"""국토지리정보원 「공간정보 용어사전」을 받아 둔다.

  https://www.ngii.go.kr/kor/board/list.do?board_code=dictionary

고시를 만드는 기관이 스스로 내는 사전이므로, 국가공간정보 표준용어집
(KS X ISO 계열)과 함께 용어의 잣대로 삼는다. 둘이 갈리는 자리가 있다 —
표준용어집은 '지상 기준점' 으로 띄우는데 이 사전은 '기준점측량' 으로
붙인다. 그럴 때 어느 쪽을 따를지는 사람이 정한다.

받은 것은 data/용어사전_국토지리정보원.json 으로 둔다.
  { "source", "fetched", "count", "terms": [{ko, hanja, en}] }

사용:  python scripts/fetch_ngii_dict.py
"""
import io, json, os, re, sys, time, urllib.parse, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "data")
URL = ("https://www.ngii.go.kr/kor/board/list.do?board_code=dictionary"
       "&maxRows=%d&currentPage=%d&srchKey=ABCE&srchValue=")
UA = {"User-Agent": "Mozilla/5.0"}
PER = 100


def get(u):
    for i in range(3):
        try:
            return urllib.request.urlopen(
                urllib.request.Request(u, headers=UA), timeout=30).read().decode("utf-8", "replace")
        except Exception:
            if i == 2:
                raise
            time.sleep(1.5)


def rows_of(html):
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        td = [re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        td = [re.sub(r"\s+", " ", x).replace("&nbsp;", " ").strip() for x in td]
        if len(td) >= 4 and td[0].isdigit():
            out.append({"no": int(td[0]), "ko": td[1], "hanja": td[2], "en": td[3]})
    return out


if __name__ == "__main__":
    seen, page = {}, 1
    while True:
        html = get(URL % (PER, page))
        rs = rows_of(html)
        if not rs:
            break
        new = 0
        for r in rs:
            if r["no"] not in seen:
                seen[r["no"]] = r
                new += 1
        print("  %3쪽 · 받은 줄 %3d · 새로 %3d · 누적 %4d"
              .replace("%3쪽", "%3d쪽") % (page, len(rs), new, len(seen)))
        if new == 0:
            break
        page += 1
        time.sleep(0.4)

    terms = [seen[k] for k in sorted(seen, reverse=True)]
    doc = {
        "source": "https://www.ngii.go.kr/kor/board/list.do?board_code=dictionary",
        "name": "국토지리정보원 공간정보 용어사전",
        "org": "국토지리정보원",
        "fetched": time.strftime("%Y-%m-%d"),
        "count": len(terms),
        "terms": [{"ko": t["ko"], "hanja": t["hanja"], "en": t["en"]} for t in terms],
    }
    p = os.path.join(OUT, "용어사전_국토지리정보원.json")
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print("\n%s — 표제어 %d개" % (os.path.basename(p), len(terms)))
