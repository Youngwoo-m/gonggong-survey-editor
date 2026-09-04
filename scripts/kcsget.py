# -*- coding: utf-8 -*-
r"""건설공사 측량 표준시방서(KCS) 전문을 내려받아 `App\관련규정` 에 넣는다.

■ 왜 따로 받는가

  국가법령정보센터의 KCS 고시 본문은 껍데기이다. 글자가 441자뿐이며
  「자세한 내용은 첨부파일을 이용하십시오」 라고만 적혀 있다. 실제 시방서는
  고시에 딸린 압축파일 안에 있다.

      건설공사 측량 표준시방서(KCS 12 00 00) 제정 전문.zip
          KCS 12 00 00 건설공사 측량_제정.hwpx
          KCS 12 10 05 건설공사 측량 일반_제정.hwpx
          KCS 12 20 05 토공사 측량_제정.hwpx
          KCS 12 20 10 배수공사 측량_제정.hwpx
          KCS 12 20 15 옹벽 및 흙막이 가시설물공사 측량_제정.hwpx
          KCS 12 20 20 포장공사 측량_제정.hwpx

  서고의 loc22~loc26 다섯 편이 바로 이 압축파일 안에 있다. 규칙명으로는
  검색되지 아니하므로 고시의 첨부파일을 거쳐야 한다.

■ 첨부파일 목록을 어떻게 얻는가

      POST /LSW/admRulAttFlList.do   admRulSeq=<일련번호>
      GET  /LSW/flDownload.do?flSeq=<파일번호>

■ 이름

  압축 안의 이름은 KCS 번호가 앞에 있어 이미 좋다. 뒤에 고시 정보를 붙여
  모아 둔 다른 파일과 꼴을 맞춘다.

      KCS 12 10 05 건설공사 측량 일반(국토지리정보원고시)(제2024-5556호)(20241121).hwpx

  PDF 는 만들지 아니한다. `건설측량_설계기준` 의 KDS 열한 편도 hwpx 만
  있으므로 그 관례를 따른다.

  python scripts\kcsget.py            무엇을 받을지 보여만 준다
  python scripts\kcsget.py --write    받아서 담는다
"""
import io
import os
import re
import sys
import urllib.request
import zipfile

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
APP = os.path.dirname(ROOT)
BOX = os.path.join(APP, "관련규정")
DEST = os.path.join(BOX, "건설측량_설계기준")
NL = chr(10)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
SITE = "https://www.law.go.kr"

# (행정규칙 일련번호, 고시 발령기관ㆍ종류, 발령번호, 시행일)
NOTICES = [
    ("2100000256822", "국토지리정보원고시", "2024-5556", "20241121"),
    ("2100000283748", "국토지리정보원고시", "2026-3671", "20260812"),
    ("2100000256824", "국토지리정보원고시", "2024-5556", "20241121"),   # KDS
]
RE_FL = re.compile(r'flDownload\.do\?flSeq=(\d+)')
BAD = re.compile(r'[\\/:*?"<>|]')


def get(url, ref=None, data=None):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    req.add_header("Referer", ref or SITE + "/")
    if data is not None:
        req.add_header("Content-Type",
                       "application/x-www-form-urlencoded; charset=UTF-8")
        data = data.encode("utf-8")
    with urllib.request.urlopen(req, data, timeout=180) as r:
        return r.read(), r.headers


def attachments(seq):
    """고시의 첨부파일 [(파일번호, 이름), …]"""
    ref = SITE + "/LSW/admRulInfoP.do?admRulSeq=" + seq
    body, _h = get(SITE + "/LSW/admRulAttFlList.do", ref, "admRulSeq=" + seq)
    t = body.decode("utf-8", "replace")
    out = []
    for m in re.finditer(
            r'flDownload\.do\?flSeq=(\d+)[^>]*>\s*([^<]{4,120}?)\s*<', t):
        out.append((m.group(1), " ".join(m.group(2).split())))
    if not out:
        out = [(x, "") for x in RE_FL.findall(t)]
    return out, ref


def zipnames(z):
    """압축 안 이름을 한글이 깨지지 않게 읽는다"""
    for i in z.infolist():
        n = i.filename
        if not (i.flag_bits & 0x800):          # UTF-8 표시가 없으면 cp949 이다
            try:
                n = n.encode("cp437").decode("cp949")
            except Exception:
                pass
        yield i, n


def main():
    write = "--write" in sys.argv
    jobs = []
    for seq, org, no, ef in NOTICES:
        atts, ref = attachments(seq)
        zips = [a for a in atts if a[1].lower().endswith(".zip")] or atts[:1]
        for fseq, fname in zips:
            body, h = get(SITE + "/LSW/flDownload.do?flSeq=" + fseq, ref)
            if body[:2] != b"PK":
                print("압축이 아님 : %s" % fname)
                continue
            z = zipfile.ZipFile(io.BytesIO(body))
            for info, name in zipnames(z):
                if not name.lower().endswith((".hwpx", ".hwp", ".pdf")):
                    continue
                stem, ext = os.path.splitext(os.path.basename(name))
                # 고시 첨부의 이름 끝에 붙은 「_제정」ㆍ「_개정」 은 이
                # 고시가 무엇을 하였는가를 적은 것이지 문서명이 아니다.
                stem = re.sub(r"_(제정|개정)$", "", stem).strip()
                out = "%s(%s)(제%s호)(%s)%s" % (BAD.sub("_", stem), org, no,
                                               ef, ext)
                jobs.append((z.read(info), out, info.file_size))

    print("받을 파일 %d개" % len(jobs))
    for _b, out, size in jobs:
        print("   %9d bytes  %s" % (size, out))
    if not write:
        print()
        print("표시만 한 것임. 받으려면 --write 를 붙일 것.")
        return

    os.makedirs(DEST, exist_ok=True)
    n = 0
    for body, out, _s in jobs:
        io.open(os.path.join(DEST, out), "wb").write(body)
        n += 1
    print()
    print("담았습니다 — %d개  (%s)" % (n, os.path.relpath(DEST, APP)))


if __name__ == "__main__":
    main()
