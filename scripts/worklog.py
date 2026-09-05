# -*- coding: utf-8 -*-
r"""편집기 작업내역을 날짜별로 정리한다 —— 작업진도 보고에 쓴다.

■ 내는 것

  D:\11.연구사업\2026년도\2026.공공측량.품관원\05.주간및월간보고와보안점검\편집기작업내역

    YYYY-MM-DD.md                  그날 하루 (커밋마다 제목ㆍ글ㆍ바꾼 파일)
    월별\편집기작업내역_YYYY-MM.md    그 달 간추림
    편집기작업내역.md                모든 날의 차례

  저장소에 담은 것만 적는다. 손에만 있는 일은 기계가 알 수 없다.

  python scripts\worklog.py           정리하여 담는다
  python scripts\worklog.py --print   담지 아니하고 오늘치를 보여만 준다
"""
import io
import os
import re
import subprocess
import sys
import collections
import datetime

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
PROTO = os.path.dirname(HERE)
APP = os.path.dirname(PROTO)
BASE = os.path.dirname(APP)
OUT = os.path.join(BASE, "05.주간및월간보고와보안점검", "편집기작업내역")
NL = chr(10)
DRY = "--print" in sys.argv
SEP = "\x1e"
FOOT = "`scripts/worklog.py` 가 커밋 이력에서 지은 것임."
# 함께 지은 이를 적은 꼬리는 보고에 싣지 아니한다
RE_TRAILER = re.compile(r"(?m)^(?:Co-Authored-By|🤖 Generated with).*$")


def git(*args):
    r = subprocess.run(["git"] + list(args), cwd=PROTO, capture_output=True)
    return r.stdout.decode("utf-8", "replace")


def commits():
    raw = git("log", "--date=format:%Y-%m-%d %H:%M", "--numstat", "--reverse",
              "--pretty=format:%s%%H|%%ad|%%an|%%s|%%b\x1f" % SEP)
    out = []
    for block in raw.split(SEP):
        if not block.strip():
            continue
        head, _, rest = block.partition("\x1f")
        sha, when, who, subject, body = (head.split("|", 4) + [""] * 5)[:5]
        files = []
        add = rem = 0
        for ln in rest.split(NL):
            m = re.match(r"^(\d+|-)\t(\d+|-)\t(.+)$", ln.strip(NL))
            if not m:
                continue
            files.append(m.group(3))
            if m.group(1).isdigit():
                add += int(m.group(1))
            if m.group(2).isdigit():
                rem += int(m.group(2))
        body = RE_TRAILER.sub("", body).strip(NL).rstrip()
        out.append({"sha": sha[:7], "날짜": when[:10], "때": when[11:],
                    "이": who, "제목": subject, "글": body,
                    "파일": files, "더함": add, "지움": rem})
    return out


def where(files):
    """주로 손댄 곳 —— 그 파일이 담긴 폴더로 센다. 뿌리에 있으면 파일 이름으로."""
    c = collections.Counter()
    for f in files:
        d = "/".join(os.path.dirname(f).split("/")[:2])
        c[d or os.path.basename(f)] += 1
    return " ㆍ ".join("%s(%d)" % (k, v) for k, v in c.most_common(6))


def day_page(date, items):
    uniq = {f for it in items for f in it["파일"]}
    add = sum(it["더함"] for it in items)
    rem = sum(it["지움"] for it in items)
    L = ["# 편집기 작업내역 —— %s" % date, "",
         "공공측량 규정 개정 편집기의 그날 커밋 이력임.", "",
         "| 항목 | 값 |", "|---|---|",
         "| 커밋 | %d건 |" % len(items),
         "| 손댄 파일 | %d개 |" % len(uniq),
         "| 더한 줄 | %s |" % format(add, ","),
         "| 지운 줄 | %s |" % format(rem, ","),
         "| 주로 손댄 곳 | %s |" % where([f for it in items for f in it["파일"]]),
         "", "## 커밋", ""]
    for i, it in enumerate(items, 1):
        L += ["### %d. %s" % (i, it["제목"]), "",
              "`%s` ㆍ %s ㆍ %s" % (it["sha"], it["때"], it["이"]), ""]
        if it["글"]:
            L += [it["글"], ""]
        L += ["바꾼 파일 %d개 (+%s / -%s)"
              % (len(it["파일"]), format(it["더함"], ","), format(it["지움"], ",")), ""]
        for f in it["파일"][:20]:
            L.append("- `%s`" % f)
        if len(it["파일"]) > 20:
            L.append("- 그 밖 %d개." % (len(it["파일"]) - 20))
        L.append("")
    L += ["---", "", FOOT, ""]
    return NL.join(L)


def month_page(ym, byday):
    days = sorted((d for d in byday if d.startswith(ym)), reverse=True)
    n = sum(len(byday[d]) for d in days)
    L = ["# 편집기 작업내역 —— %s" % ym, "",
         "그 달에 저장소에 담은 것을 날마다 간추린 것임. 자세한 것은 날짜별 파일에 있음.", "",
         "- 담은 날 %d일 ㆍ 담은 것 %d건." % (len(days), n), "",
         "| 날짜 | 건 | 파일 | 더함 | 지움 |", "|---|---:|---:|---:|---:|"]
    for d in days:
        items = byday[d]
        L.append("| [%s](../%s.md) | %d | %d | %s | %s |"
                 % (d, d, len(items), len({f for it in items for f in it["파일"]}),
                    format(sum(it["더함"] for it in items), ","),
                    format(sum(it["지움"] for it in items), ",")))
    L.append("")
    for d in days:
        L.append("### %s" % d)
        L.append("")
        for it in byday[d]:
            L.append("- `%s` %s" % (it["sha"], it["제목"]))
        L.append("")
    L += ["---", "", FOOT, ""]
    return NL.join(L)


def index_page(byday):
    L = ["# 편집기 작업내역 —— 차례", "",
         "지은 때 : %s" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    ledger = os.path.join(APP, "개정안")
    rows = []
    for reg in ("작업규정", "성과심사 규정", "무인비행장치 규정"):
        p = os.path.join(ledger, reg)
        if not os.path.isdir(p):
            continue
        key = lambda s: [int(t) for t in re.findall(r"\d+", s)]
        best = {}
        for x in os.listdir(p):
            m = re.match(r"개정안_(v[A-Z]-\d+)", x)
            if m and (m.group(1) not in best or key(x) > key(best[m.group(1)])):
                best[m.group(1)] = x
        for ser in sorted(best):
            rows.append("| %s | `%s` |" % (reg, best[ser].replace("개정안_", "")))
    if rows:
        L += ["## 지금 서 있는 자리", "", "| 규정 | 최신 판 |", "|---|---|"] + rows + [""]
    L += ["- 담은 날 %d일 ㆍ 담은 것 %d건."
          % (len(byday), sum(len(v) for v in byday.values())), "",
          "| 날짜 | 건 | 한 일 |", "|---|---:|---|"]
    for d in sorted(byday, reverse=True):
        first = byday[d][0]["제목"]
        more = " 외 %d건" % (len(byday[d]) - 1) if len(byday[d]) > 1 else ""
        L.append("| [%s](%s.md) | %d | %s%s |" % (d, d, len(byday[d]), first, more))
    L += ["", "---", "", FOOT, ""]
    return NL.join(L)


def main():
    byday = collections.OrderedDict()
    for it in commits():
        byday.setdefault(it["날짜"], []).append(it)

    if DRY:
        d = max(byday)
        print(day_page(d, byday[d])[:3000])
        return

    os.makedirs(os.path.join(OUT, "월별"), exist_ok=True)
    for d, items in byday.items():
        io.open(os.path.join(OUT, "%s.md" % d), "w", encoding="utf-8", newline="").write(
            day_page(d, items))
    for ym in sorted({d[:7] for d in byday}):
        io.open(os.path.join(OUT, "월별", "편집기작업내역_%s.md" % ym), "w",
                encoding="utf-8", newline="").write(month_page(ym, byday))
    io.open(os.path.join(OUT, "편집기작업내역.md"), "w", encoding="utf-8", newline="").write(
        index_page(byday))
    print("담았습니다 — %s" % OUT)
    print("  날 %d일 ㆍ 건 %d건 ㆍ 달 %d개"
          % (len(byday), sum(len(v) for v in byday.values()), len({d[:7] for d in byday})))


if __name__ == "__main__":
    main()
