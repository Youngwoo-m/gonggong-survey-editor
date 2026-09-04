# -*- coding: utf-8 -*-
r"""국가법령정보센터에서 서고에 없는 법령을 내려받아 `App\관련규정` 에 넣는다.

■ 어떻게 내려받는가

  공개 OpenAPI 는 서버 IP 등록이 필요하여 쓸 수 없다. 대신 화면이 실제로
  쓰는 저장 경로를 그대로 부른다. 브라우저에서 저장 단추를 눌러 확인한
  주소이다.

      법령      POST /LSW//lsHwpxSave.do        application/hwp+zip
                POST /LSW//lsPdfPrint.do        application/pdf
      행정규칙  POST /LSW//admRulHwpxSave.do
                POST /LSW//admRulPdfPrint.do

  본문은 `lsiSeq`(또는 `admRulSeq`) 와 `efYd` 와 `joAllCheck=Y` 넷이면
  충분하다. 화면이 보내는 조문 목록 전체를 흉내 낼 필요가 없다.

■ 어떤 이름으로 담는가

  이미 모아 둔 파일과 같은 꼴로 맞춘다.

      도로법(법률)(제21172호)(20260603).hwpx
      측량기기 성능검사 규정(국토지리정보원고시)(제2023-2626호)(20230612).hwpx

  종류와 번호와 시행일은 본문 머리의 「[시행 …] [법률 제…호, …]」 줄에서
  뽑는다.

  python scripts\lawget.py            어디에 있는지 찾아만 본다
  python scripts\lawget.py --write    내려받아 담는다
"""
import io
import os
import re
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# ROOT 는 App\prototype 이므로 App 은 그 부모 한 단계뿐이다.
APP = os.path.dirname(ROOT)
BOX = os.path.join(APP, "관련규정")
NL = chr(10)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
SITE = "https://www.law.go.kr"

# (서고 id, 찾을 이름, 넣을 폴더)
WANT = [
    ("reg54", "국토의 계획 및 이용에 관한 법률", "지하시설물관련법령"),
    ("reg55", "도시철도법", "지하시설물관련법령"),
    ("reg56", "철도의 건설 및 철도시설 유지관리에 관한 법률", "지하시설물관련법령"),
    ("reg57", "시설물의 안전 및 유지관리에 관한 특별법 시행령", "지하시설물관련법령"),
    ("reg58", "고압가스 안전관리법", "지하시설물관련법령"),
    ("reg59", "위험물안전관리법", "지하시설물관련법령"),
    ("reg60", "화학물질관리법", "지하시설물관련법령"),
    ("reg61", "지하안전관리에 관한 특별법", "지하시설물관련법령"),
    ("reg65", "전자정부법", "지하시설물관련법령"),
    ("reg66", "공공기록물 관리에 관한 법률", "지하시설물관련법령"),
    ("reg67", "공공기록물 관리에 관한 법률 시행령", "지하시설물관련법령"),
    ("reg68", "형법", "지하시설물관련법령"),
    ("reg69", "항공안전법 시행규칙", "지하시설물관련법령"),
    ("reg70", "고압가스 안전관리법 시행령", "지하시설물관련법령"),
    ("reg71", "고압가스 안전관리법 시행규칙", "지하시설물관련법령"),
    ("reg50", "지도도식규칙", "하위규정"),
    ("reg51", "수치지도 작성 작업규칙", "하위규정"),
    ("reg52", "지형도 도식적용규정", "하위규정"),
    ("reg62", "도로기반시설물의 정보 및 시스템 유지관리 지침", "하위규정"),
    ("reg64", "지방자치단체의 도로 및 상·하수도의 시설물관리를 위한 "
              "범용프로그램의 기본설계서 및 품질인증기준", "하위규정"),
    ("reg53", "산업안전보건기준에 관한 규칙", "상위법령"),
    ("reg63", "훈령ㆍ예규 등의 발령 및 관리에 관한 규정", "기타관련규정"),
]

RE_IFRAME = re.compile(r'src="(/LSW/+(?:lsInfoP|admRulInfoP)\.do\?[^"]+)"')
RE_TITLE = re.compile(r"\[\s*시행\s*([^\]]{4,24})\]\s*\[([^\],]{2,30})\s*"
                      r"제\s*([0-9\-]+)\s*호")
RE_TAG = re.compile(r"<[^>]+>")
BAD = re.compile(r'[\\/:*?"<>|]')


def get(url, ref=None, data=None):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    req.add_header("Referer", ref or SITE + "/")
    if data is not None:
        req.add_header("Content-Type",
                       "application/x-www-form-urlencoded; charset=UTF-8")
        data = data.encode("utf-8")
    with urllib.request.urlopen(req, data, timeout=90) as r:
        return r.read(), r.headers.get("Content-Type", "")


def find(name):
    """이름으로 법령 또는 행정규칙을 찾아 (갈래, 일련번호, 시행일, 참조주소)"""
    for kind, path in (("법령", "법령"), ("행정규칙", "행정규칙")):
        url = "%s/%s/%s" % (SITE, urllib.parse.quote(path),
                            urllib.parse.quote(name))
        try:
            body, _ct = get(url)
        except Exception:
            continue
        m = RE_IFRAME.search(body.decode("utf-8", "replace"))
        if not m:
            continue
        src = m.group(1)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(src).query)
        seq = (q.get("lsiSeq") or q.get("admRulSeq") or [None])[0]
        if not seq:
            continue
        return (kind, seq, (q.get("efYd") or [""])[0],
                (q.get("chrClsCd") or ["010202"])[0], SITE + src)
    return None


def ymd(s):
    """「2025. 10. 1.」 을 20251001 로.

    숫자만 뽑아 붙이면 안 된다. 「2025. 10. 1.」 은 2025101 일곱 자가 되어
    2025-01-01 인지 2025-10-01 인지 가릴 수 없다. 반드시 점으로 끊는다.
    """
    p = [x for x in re.split(r"[^0-9]+", str(s or "")) if x]
    if len(p) < 3:
        return ""
    return "%04d%02d%02d" % (int(p[0]), int(p[1]), int(p[2]))


def meta(ref):
    """본문 머리에서 (종류, 번호, 시행일 8자리) 를 뽑는다"""
    body, _ct = get(ref)
    t = " ".join(RE_TAG.sub(" ", body.decode("utf-8", "replace")).split())
    m = RE_TITLE.search(t)
    if not m:
        return None
    return (m.group(2).strip().replace(" ", ""), m.group(3).strip(),
            ymd(m.group(1)))


def grab(kind, seq, efyd, chrcls, ref):
    """hwpx 와 pdf 를 받아 (hwpx, pdf) 로 돌려준다"""
    if kind == "법령":
        # 법령은 POST 이고 본문에 시행일이 있어야 한다. 시행일이 틀리면
        # 서버가 「XML 파싱중 오류」 라는 HTML 을 돌려준다.
        eps = ("lsHwpxSave.do?trSeq=%s&efDvPop=&nwJoYnInfo=&lastCheck=Y"
               "&efGubun=&ancYnChk=0" % seq,
               "lsPdfPrint.do?ancYnChk=0&efGubun=")
        data = "lsiSeq=%s&chrClsCd=%s&efYd=%s&joAllCheck=Y" % (seq, chrcls, efyd)
    else:
        # 행정규칙은 GET 이며 일련번호 하나면 된다
        eps = ("admRulHwpxSave.do?admRulSeq=%s&langType=Ko&chrClsCd=%s"
               % (seq, chrcls),
               "admRulPdfPrint.do?admRulSeq=%s" % seq)
        data = None
    out = []
    for ep in eps:
        try:
            body, ct = get(SITE + "/LSW/" + ep, ref, data)
        except Exception as e:
            out.append((None, str(e)))
            continue
        ok = (body[:2] == b"PK") if "hwp" in ep.lower() else (body[:4] == b"%PDF")
        out.append((body if ok else None, ct))
    return out


def from_library(rid):
    """이름으로 못 찾으면 서고 자료에 적힌 원본 주소를 쓴다.

    「지방자치단체의 도로 및 상ㆍ하수도의 …」 처럼 규칙명 검색에 걸리지 않는
    것이 있다. 서고를 세울 때 적어 둔 `source` 가 가장 확실한 열쇠이다.
    """
    p = os.path.join(ROOT, "data", rid + ".json")
    if not os.path.exists(p):
        return None, None
    import json
    d = json.load(io.open(p, encoding="utf-8"))
    src = d.get("source") or ""
    m = re.search(r"(admRulSeq|lsiSeq)=(\w+)", src)
    if not m:
        return None, None
    kind = "행정규칙" if m.group(1) == "admRulSeq" else "법령"
    got = (kind, m.group(2), d.get("effective") or "", "010202", src)
    gu = (d.get("org") or "") + (d.get("kind") or "")
    no = re.sub(r"^0+(?=[0-9])", "", str(d.get("no") or ""))
    return got, (gu.replace(" ", ""), no, d.get("effective") or "")


def main():
    write = "--write" in sys.argv
    rows = []
    for rid, name, folder in WANT:
        got = find(name)
        if not got:
            got, mt = from_library(rid)
            if got:
                rows.append((rid, name, folder, got, mt))
                continue
            rows.append((rid, name, folder, None, "찾지 못함"))
            continue
        kind, seq, efyd, chrcls, ref = got
        mt = meta(ref)
        rows.append((rid, name, folder, (kind, seq, efyd, chrcls, ref), mt))
        time.sleep(0.3)

    print("%-7s %-9s %-10s %-12s %s" % ("id", "갈래", "일련번호", "시행일", "이름"))
    for rid, name, folder, got, mt in rows:
        if not got:
            print("%-7s %-9s %s" % (rid, "못 찾음", name[:40]))
            continue
        kind, seq, efyd, _c, _r = got
        gu = mt[0] if isinstance(mt, tuple) else "?"
        no = mt[1] if isinstance(mt, tuple) else "?"
        ef = mt[2] if isinstance(mt, tuple) else efyd
        print("%-7s %-9s %-10s %-12s %s (%s 제%s호)"
              % (rid, kind, seq, ef, name[:34], gu, no))

    if not write:
        print()
        print("찾아만 본 것임. 내려받으려면 --write 를 붙일 것.")
        return

    print()
    done, fail = 0, []
    for rid, name, folder, got, mt in rows:
        if not got or not isinstance(mt, tuple):
            fail.append((rid, name, "정보를 얻지 못함"))
            continue
        kind, seq, efyd, chrcls, ref = got
        gu, no, ef = mt
        stem = "%s(%s)(제%s호)(%s)" % (BAD.sub("_", name), gu, no, ef)
        d = os.path.join(BOX, folder)
        os.makedirs(d, exist_ok=True)
        pair = grab(kind, seq, efyd or ef, chrcls, ref)
        for (body, ct), ext in zip(pair, (".hwpx", ".pdf")):
            if not body:
                fail.append((rid, name + ext, str(ct)[:40]))
                continue
            p = os.path.join(d, stem + ext)
            io.open(p, "wb").write(body)
            done += 1
            print("   %-7s %8d bytes  %s" % (rid, len(body),
                                             os.path.basename(p)[:66]))
        time.sleep(0.4)
    print()
    print("받은 파일 %d개, 실패 %d건" % (done, len(fail)))
    for r in fail:
        print("   %s" % (r,))


if __name__ == "__main__":
    main()
