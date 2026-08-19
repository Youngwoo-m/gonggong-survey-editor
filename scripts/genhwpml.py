# -*- coding: utf-8 -*-
"""
법제처에서 내려받은 고시 원문(HWPML) → 현행규정 조문 트리 JSON

국가법령정보센터의 [한글] 내려받기는 이름만 .hwp 이고 속은 HWPML 2.1 (XML) 이다.
공개 API 와 견주면 이 파일이 낫다 — API 는 조문을 한 줄로 주어 항·호의 줄바꿈이
사라지지만, 원문 파일은 항과 호가 저마다 한 문단이다. 얼개를 추측으로 되살릴
까닭이 없어진다. 본문에 박힌 도해도 파일 안에 그대로 들어 있다.

사용:
    python scripts/genhwpml.py reg12 "..\\관련규정\\하위규정\\무인비행장치 측량 작업규정(...).hwp"
    python scripts/genhwpml.py reg12 <파일> --dry     (파일을 고치지 않고 견주기만)

하는 일
  1. 문단을 뽑는다 (머리말·쪽수·목차·부칙은 버린다)
  2. 본문에 박힌 그림을 꺼내 data/objects/<규정id>/ 에 두고 <img id> 자리표시를 남긴다
  3. gendata.build_tree 로 편·장·절·관·조 트리를 만든다 (본문은 원문 줄 그대로)
  4. 지금 data/regNN.json 과 견주어 글자가 달라진 곳을 알린다
  5. 조문 트리만 갈아 끼운다 — 별표 목록·출처·번호 등 나머지는 그대로 둔다
"""
import io, os, re, sys, json, html, base64

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "data")
sys.path.insert(0, HERE)
import gendata as G


def is_hwpml(path):
    """법제처 내려받기는 이름만 .hwp 이고 속은 XML — 옛 HWP 이진과 가른다"""
    head = io.open(path, "rb").read(8)
    return head[:5] == b"<?xml"


def read(path):
    return io.open(path, encoding="utf-8", errors="replace").read()


# ───────────── 원문 문단 뽑기 ─────────────
def paragraphs(path):
    """원문 문단을 (글자, 그림번호들) 로 차례대로 돌려준다

    HWPML 에서는 그림이 <IMAGE BinItem="n"> 으로 문단에 박혀 있다. 글자가 없는
    문단이라도 그림이 있으면 버리지 아니한다 — 본문의 도해가 그런 꼴이다.
    옛 HWP 이진(관보 원본 등)은 hwp5.py 로 글자만 읽는다.
    """
    if not is_hwpml(path):
        import hwp5
        return [(l.strip(), []) for l in hwp5.text_lines(path) if l.strip()]
    part = read(path).split("<BODY", 1)
    body = part[1] if len(part) > 1 else part[0]
    out = []
    for p in re.findall(r"<P\b[^>]*>(.*?)</P>", body, re.S):
        pics = [int(x) for x in re.findall(r'<IMAGE\b[^>]*\bBinItem="(\d+)"', p)]
        p = re.sub(r"<TAB\b[^>]*/?>", " ", p)
        t = "".join(re.findall(r"<TEXT\b[^>]*>(.*?)</TEXT>", p, re.S))
        t = html.unescape(re.sub(r"<[^>]+>", "", t))
        t = t.replace("\xa0", " ").strip()
        if t or pics:
            out.append((t, pics))
    return out


# ───────────── 본문에 박힌 그림 ─────────────
MAGIC = ((b"GIF8", "gif"), (b"\x89PNG", "png"), (b"\xff\xd8\xff", "jpg"), (b"BM", "bmp"))


def binaries(path):
    """BinItem 차례(1부터) → (그림 바이트, 확장자)"""
    if not is_hwpml(path):
        return {}                     # 옛 HWP 이진에서는 그림을 꺼내지 않는다
    raw = read(path)
    ref = {}
    for i, m in enumerate(re.finditer(r"<BINITEM\b[^>]*>", raw), start=1):
        did = re.search(r'BinData="(\d+)"', m.group(0))
        fmt = re.search(r'Format="(\w+)"', m.group(0))
        if did:
            ref[i] = (int(did.group(1)), (fmt.group(1) if fmt else "bin").lower())
    store = {}
    for m in re.finditer(r'<BINDATA\b[^>]*\bId="(\d+)"[^>]*>(.*?)</BINDATA>', raw, re.S):
        try:
            store[int(m.group(1))] = base64.b64decode(re.sub(r"\s+", "", m.group(2)))
        except Exception:
            pass
    out = {}
    for i, (did, fmt) in ref.items():
        b = store.get(did)
        if not b:
            continue
        for head, ext in MAGIC:              # 적힌 형식과 실제가 다를 때가 있다
            if b.startswith(head):
                fmt = ext
                break
        out[i] = (b, fmt)
    return out


# 쪽머리·쪽번호처럼 본문이 아닌 줄
NOISE = re.compile(r"^(법제처|국가법령정보센터|[-\s/\d]*)$")
# 담당부서 — "국토지리정보원(지리정보과), 031-210-2722"
DEPT = re.compile(r"^[^\s].*\([^)]*\)\s*,\s*[\d\-]{9,}$")
RE_HEAD = re.compile(r"^제\s*\d+\s*(편|장|절|관)\b")
RE_BOCHIK = re.compile(r"^부\s*칙\b")
RE_IMG = re.compile(r'<img\s+id="([\w.-]+)"\s*>(?:</img>)?')


def body_lines(paras, title=""):
    """머리말·목차·부칙을 걷어 내고 (본문 문단, 부칙 문단) 을 돌려준다

    목차는 '제3조(적용)' 처럼 괄호에서 끝나고, 본문은 그 뒤에 조문이 이어진다.
    그러므로 '내용이 딸린 첫 조문' 을 찾고, 그 앞의 편·장 머리까지 거슬러
    올라가면 목차와 본문의 경계가 잡힌다.
    """
    # 그림만 있고 글자가 없는 문단(본문 도해)은 쪽번호와 생김새가 같다 — 그림이
    # 있으면 남긴다. 머리말의 기관 로고는 본문 시작 앞이라 아래에서 잘려 나간다.
    keep = [(t, p) for (t, p) in paras
            if p or not (NOISE.match(t) or DEPT.match(t) or t == title)]
    first = None
    for i, (t, _) in enumerate(keep):
        m = G.RE_JO.match(t)
        if m and (m.group(4) or "").strip():
            first = i
            break
    if first is None:
        raise SystemExit("  [오류] 본문 조문을 찾지 못했습니다.")
    start = first
    while start > 0 and RE_HEAD.match(keep[start - 1][0]):
        start -= 1
    body, bochik = [], []
    for item in keep[start:]:
        if bochik or RE_BOCHIK.match(item[0]):
            bochik.append(item)
        else:
            body.append(item)
    return body, bochik


def to_lines(body, pics, out_dir, save=True):
    """(글자, 그림) 문단을 build_tree 가 받는 줄로 바꾸고, 그림은 파일로 꺼낸다"""
    lines, made = [], {}
    for text, ids in body:
        marks = []
        for b in ids:
            if b not in pics:
                continue
            key = f"pic{len(made) + 1}"
            made[key] = pics[b]
            marks.append(f'<img id="{key}"></img>')
        s = (text + "".join(marks)).strip()
        if s:
            lines.append(s)
    if save and made:
        os.makedirs(out_dir, exist_ok=True)
        for key, (raw, ext) in made.items():
            io.open(os.path.join(out_dir, f"{key}.{ext}"), "wb").write(raw)
    return lines, made


# ───────────── 지금 자료와 견주기 ─────────────
def flat(tree, lv="조"):
    out = []

    def rec(ns):
        for n in ns:
            if n["level"] == lv:
                out.append(n)
            rec(n.get("children") or [])
    rec(tree)
    return out


# 따옴표는 원문과 API 가 서로 다르게 쓴다 — 글자 대조에서는 같게 본다
QUOTE = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
bare = lambda s: re.sub(r"\s+", "", RE_IMG.sub("", s or "")).translate(QUOTE)


def compare(old, new):
    """(글자까지 같은 조문 수, 다른 조문 목록, 줄 얼개만 달라진 조문 수)"""
    o = {x["legacyNo"]: x for x in flat(old)}
    n = {x["legacyNo"]: x for x in flat(new)}
    diff, layout, same = [], 0, 0
    for k, nn in n.items():
        oo = o.get(k)
        if not oo:
            diff.append((k, "새 조문 (지금 자료에 없음)"))
            continue
        if bare(oo["title"]) != bare(nn["title"]):
            diff.append((k, f"제목  {oo['title']!r} → {nn['title']!r}"))
        elif bare(oo["body"]) != bare(nn["body"]):
            diff.append((k, "본문 글자가 다름"))
        elif oo["body"] != nn["body"]:
            layout += 1
        else:
            same += 1
    for k in o:
        if k not in n:
            diff.append((k, "없어진 조문 (원문 파일에 없음)"))
    return same, diff, layout


def main(sid, path, dry=False):
    jf = os.path.join(OUT, sid + ".json")
    doc = json.load(io.open(jf, encoding="utf-8"))
    out_dir = os.path.join(OUT, "objects", sid)

    body, bochik = body_lines(paragraphs(path), doc.get("name", ""))
    lines, made = to_lines(body, binaries(path), out_dir, save=not dry)

    tree = G.build_tree(lines)
    G.renumber(tree)
    stats = {k: G.count(tree, k) for k in G.LEVELS}
    same, diff, layout = compare(doc["tree"], tree)

    print(f"\n  {doc['name']} — {os.path.basename(path)}")
    print(f"  원문 문단 {len(lines)}줄 · 그림 {len(made)}개 (부칙 {len(bochik)}줄은 넣지 않습니다)")
    print("  얼개 " + " · ".join(f"{k} {stats[k]}" for k in G.LEVELS if stats[k])
          + "   (지금 자료: "
          + " · ".join(f"{k} {doc['stats'][k]}" for k in G.LEVELS if doc["stats"].get(k)) + ")")
    print(f"  대조  글자까지 같음 {same} · 줄 얼개만 달라짐 {layout} · 글자가 다름 {len(diff)}")
    for k, why in diff[:40]:
        print(f"        {k}  {why}")
    if len(diff) > 40:
        print(f"        … 그 밖 {len(diff) - 40}건")
    if dry:
        print("\n  --dry — 파일은 고치지 않았습니다.")
        return

    doc["tree"] = tree
    doc["stats"] = stats
    doc["textSource"] = "법제처 국가법령정보센터 원문(HWPML) — " + os.path.basename(path)
    with io.open(jf, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"\n  {sid}.json 의 조문 트리를 원문으로 갈아 끼웠습니다. (별표·출처 등은 그대로)")

    if made:
        # 본문 그림 색인 — 표·수식으로 이미 바꾸어 둔 것은 건드리지 않는다
        ip = os.path.join(out_dir, "index.json")
        index = json.load(io.open(ip, encoding="utf-8")) if os.path.exists(ip) else {}
        where = {}
        for n in flat(tree):
            for k in RE_IMG.findall(n["body"] or ""):
                where[k] = n["legacyNo"]
        for key, (_, ext) in made.items():
            jo = where.get(key, "")
            index[key] = {"kind": "image", "article": jo,
                          "file": f"{key}.{ext}", "preview": f"원문 그림 ({jo})"}
        with io.open(ip, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
        print(f"  본문 그림 {len(made)}개를 objects/{sid}/ 에 두고 색인했습니다.")

    lp = os.path.join(OUT, "library.json")
    lib = json.load(io.open(lp, encoding="utf-8"))
    for e in lib["regulations"]:
        if e["id"] == sid:
            e["stats"] = stats
            e["textSource"] = doc["textSource"]
    with io.open(lp, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)
    print("  library.json 의 얼개·출처도 함께 고쳤습니다.")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) < 2:
        print(__doc__)
        raise SystemExit(1)
    main(a[0], a[1], dry="--dry" in sys.argv)
