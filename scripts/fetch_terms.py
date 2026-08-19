# -*- coding: utf-8 -*-
"""국가공간정보 표준용어집을 공간정보표준통합지원시스템에서 받아 온다.
   https://gsqm.lx.or.kr/gis/term/termSearchList.do  (한국국토정보공사 LX)"""
import io, sys, time, json, urllib.parse, urllib.request, re, html
sys.stdout.reconfigure(encoding="utf-8")

URL = "https://gsqm.lx.or.kr/gis/term/termSearchList.do"
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
TAG = re.compile(r"<[^>]+>")

def text(s):
    s = TAG.sub(" ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

def page(n):
    body = urllib.parse.urlencode({
        "currentPage": n, "chosung": "", "sortType": "",
        "searchKeyword": "", "orderType": ""}).encode()
    req = urllib.request.Request(URL, data=body, headers={
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        h = r.read().decode("utf-8", "replace")
    i = h.find('id="calList"')
    if i < 0: return []
    seg = h[i:h.find("</table>", i)]
    out = []
    for tr in ROW.findall(seg):
        c = [text(x) for x in CELL.findall(tr)]
        if len(c) < 7 or not c[1] or c[1] == "한글용어": continue
        out.append({"no": c[0], "ko": c[1], "en": c[2], "def": c[3],
                    "std": c[4], "stat": c[5], "at": c[6]})
    return out

terms, seen = [], set()
total = int(sys.argv[1]) if len(sys.argv) > 1 else 245
for p in range(1, total + 1):
    try:
        got = page(p)
    except Exception as e:
        print(f"  {p}쪽 실패: {e}", file=sys.stderr); time.sleep(1); continue
    if not got: break
    for t in got:
        k = (t["ko"], t["en"], t["std"])
        if k in seen: continue
        seen.add(k); terms.append(t)
    if p % 40 == 0: print(f"  {p}쪽 … 누적 {len(terms)}", flush=True)
    time.sleep(0.05)

io.open("표준용어집.json", "w", encoding="utf-8").write(
    json.dumps({"source": URL, "org": "한국국토정보공사(LX) 공간정보표준통합지원시스템",
                "title": "국가공간정보 표준용어", "count": len(terms),
                "terms": terms}, ensure_ascii=False, indent=1))
print(f"\n받은 용어 {len(terms)}건 → 표준용어집.json")
