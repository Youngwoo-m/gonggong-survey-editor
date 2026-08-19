# -*- coding: utf-8 -*-
"""
품관원 검토의견 읽기

  99.참고자료\\품관원의견.2026.07.27\\품관원.이한.작업규정 변경(안)-2026.07.27_검토의견.hwpx

'3. 메모별 세부 검토결과 — 세부 검토표' 는
  번호 / 관련 조문 / 메모 요지 / 쟁점 분석 / 권고 개정방향 / 우선순위
여섯 칸으로 되어 있다. 표를 편 글줄에서 이 여섯 칸씩 끊어 읽는다.
"""
import re, zipfile

HEAD = {"번호", "관련 조문", "메모 요지", "쟁점 분석", "권고 개정방향", "우선"}


def lines_of(path):
    out = []
    with zipfile.ZipFile(path) as z:
        for n in sorted(x for x in z.namelist() if re.match(r"Contents/section\d+\.xml$", x)):
            xml = z.read(n).decode("utf-8", "replace")
            xml = re.sub(r"</hp:tc>", "\n", xml)
            xml = re.sub(r"</hp:tr>|</hp:p>", "\n", xml)
            xml = re.sub(r"<[^>]+>", "", xml)
            for ln in xml.split("\n"):
                ln = re.sub(r"[ \t]+", " ", ln).strip()
                if ln:
                    out.append(ln)
    return out


def read(path):
    """[{no, ref, memo, issue, fix, pri, articles:[조번호], chapters:[장이름]}, …]"""
    L = lines_of(path)
    rows, i = [], 0
    while i + 5 < len(L):
        if not re.fullmatch(r"\d{1,2}", L[i]) or L[i] in HEAD:
            i += 1
            continue
        ref = L[i + 1]
        if not re.match(r"^제\s*\d+\s*(조|장)|^제\s*\d+\s*장 전반", ref):
            i += 1
            continue
        r = {
            "no": int(L[i]), "ref": ref,
            "memo": L[i + 2], "issue": L[i + 3], "fix": L[i + 4],
            "pri": L[i + 5] if len(L[i + 5]) <= 2 else "",
        }
        # 세부 검토표만 받는다 — 우선순위 칸이 상·중·하 인 줄
        if r["pri"] not in ("상", "중", "하"):
            i += 1
            continue
        r["articles"] = sorted({int(x) for x in re.findall(r"제\s*(\d+)\s*조", ref)})
        r["chapters"] = re.findall(r"제\s*(\d+)\s*장", ref)
        rows.append(r)
        i += 6
    # 번호가 겹치면 뒤엣것을 버린다 (표가 두 쪽으로 나뉘어 머리글이 되풀이된다)
    seen, out = set(), []
    for r in rows:
        k = (r["no"], r["ref"])
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


PRI = {"상": "우선순위 상", "중": "우선순위 중", "하": "우선순위 하"}


def basis(r):
    """근거 줄 — 어느 검토의견이며 무엇을 지적했는지"""
    def one(k):
        return re.sub(r"\s+", " ", str(r.get(k) or "")).strip()
    head = f"[품관원] 검토의견 {r['no']}번"
    if one("ref"):
        head += f"({one('ref')})"
    bits = [b for b in (one("memo"), one("issue")) if b]
    return f"{head} — {' / '.join(bits)}" if bits else head


def cause(r):
    """사유 줄 — 그 의견을 어떻게 반영했는지"""
    fix = re.sub(r"\s+", " ", str(r.get("fix") or "")).strip()
    if not fix:
        return ""
    pri = f" (우선순위 {r['pri']})" if r.get("pri") in PRI else ""
    return f"검토의견 {r['no']}번을 반영하여 {fix}{pri}"


def sentence(r, limit=180):
    """조문 변경 사유에 넣을 한 문장 — 어느 의견인지 그대로 드러낸다"""
    def one(k):
        return re.sub(r"\s+", " ", str(r.get(k) or "")).strip()
    fix, memo, issue, ref = one("fix"), one("memo"), one("issue"), one("ref")
    head = f"[품관원] 검토의견 {r['no']}번"
    if ref:
        head += f"({ref})"
    bits = [head]
    if memo:
        bits.append(f"의견: {memo}")
    if issue:
        bits.append(f"문제점: {issue}")
    if fix:
        bits.append(f"반영: {fix}")
    if r.get("pri") in PRI:
        bits.append(f"우선순위 {r['pri']}")
    return ", ".join(bits[:1]) + " — " + " / ".join(bits[1:]) if len(bits) > 1 else bits[0]
