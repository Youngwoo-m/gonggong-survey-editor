# -*- coding: utf-8 -*-
"""
국가법령정보센터에 원문이 없는 규정을 '파일에서' 색인해 배포본에 심는다.

앱의 [파일 열기] 와 같은 결과를 내려고, 글줄만 파이썬으로 뽑고
구조화·번역은 앱과 같은 모듈(core/structure.js, core/translate.js)에 맡긴다.

  PDF  → PyMuPDF
  HWP  → hwp5.py (OLE2 이진)
  HWPX·DOCX → ZIP 안의 XML
  HTML → 태그 제거

사용:  python scripts/genlocal.py            (전부)
       python scripts/genlocal.py kds        (묶음 이름만)
"""
import io, json, os, re, subprocess, sys, tempfile, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hwp5

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
REG = os.path.join(os.path.dirname(ROOT), "관련규정")     # App\관련규정


# ───────────────────────── 글줄 뽑기 ─────────────────────────
def lines_pdf(path):
    import fitz
    out = []
    with fitz.open(path) as doc:
        for page in doc:
            for ln in page.get_text("text").split("\n"):
                ln = ln.strip()
                if ln:
                    out.append(ln)
    return out


def lines_zipxml(path, inner):
    out = []
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if re.match(inner, n)]
        for n in sorted(names):
            xml = z.read(n).decode("utf-8", "replace")
            xml = re.sub(r"</w:p>|</hp:p>", "\n", xml)
            xml = re.sub(r"<[^>]+>", "", xml)
            for ln in xml.split("\n"):
                ln = re.sub(r"\s+", " ", ln).strip()
                if ln:
                    out.append(ln)
    return out


def lines_html(path):
    s = io.open(path, encoding="utf-8", errors="replace").read()
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)</(p|div|li|tr|h[1-6]|br)\s*>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&")
          .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    return [re.sub(r"\s+", " ", x).strip() for x in s.split("\n") if x.strip()]


def extract_lines(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return lines_pdf(path)
    if ext == ".hwp":
        return hwp5.text_lines(path)
    if ext == ".hwpx":
        return lines_zipxml(path, r"Contents/section\d+\.xml$")
    if ext == ".docx":
        return lines_zipxml(path, r"word/document\.xml$")
    if ext in (".html", ".htm"):
        return lines_html(path)
    if ext == ".txt":
        return [x.strip() for x in io.open(path, encoding="utf-8", errors="replace") if x.strip()]
    raise RuntimeError(f"다룰 수 없는 형식: {ext}")


# ───────────────────────── 심을 목록 ─────────────────────────
#   (묶음, 이름, 소관, 종류, 시행, 언어, 구분, 상대경로)
ITEMS = [
    # ── 건설측량 설계기준 (KDS) — 국가건설기준센터
    ("kds", "KDS 12 10 05 설계측량 일반", "국토지리정보원", "설계기준", "20241115", "ko", "kds",
     r"건설측량_설계기준\KDS 12 10 05 설계측량 일반_개정.hwp"),
    ("kds", "KDS 12 20 05 도로 및 철도 설계측량", "국토지리정보원", "설계기준", "20241115", "ko", "kds",
     r"건설측량_설계기준\KDS 12 20 05 도로 및 철도 설계측량_개정.hwp"),
    ("kds", "KDS 12 20 10 단지조성 설계측량", "국토지리정보원", "설계기준", "20230102", "ko", "kds",
     r"건설측량_설계기준\KDS 12 20 10 단지조성 설계측량.hwp"),
    ("kds", "KDS 12 20 15 하천 및 댐 설계측량", "국토지리정보원", "설계기준", "20230102", "ko", "kds",
     r"건설측량_설계기준\KDS 12 20 15 하천 및 댐 설계측량.hwp"),
    ("kds", "KDS 12 20 20 상·하수도 설계측량", "국토지리정보원", "설계기준", "20230102", "ko", "kds",
     r"건설측량_설계기준\KDS 12 20 20 상·하수도 설계측량.hwp"),
    ("kds", "KDS 12 20 25 농업기반시설 설계측량", "국토지리정보원", "설계기준", "20230102", "ko", "kds",
     r"건설측량_설계기준\KDS 12 20 25 농업기반시설 설계측량.hwp"),
    ("kds", "KDS 12 20 30 교량 설계측량", "국토지리정보원", "설계기준", "20230102", "ko", "kds",
     r"건설측량_설계기준\KDS 12 20 30 교량 설계측량.hwp"),
    ("kds", "KDS 12 20 35 터널 설계측량", "국토지리정보원", "설계기준", "20230102", "ko", "kds",
     r"건설측량_설계기준\KDS 12 20 35 터널 설계측량.hwp"),
    ("kds", "KDS 12 20 40 건축 설계측량", "국토지리정보원", "설계기준", "20230102", "ko", "kds",
     r"건설측량_설계기준\KDS 12 20 40 건축 설계측량.hwp"),
    ("kds", "KDS 12 30 05 3차원 디지털 설계측량", "국토지리정보원", "설계기준", "20230102", "ko", "kds",
     r"건설측량_설계기준\KDS 12 30 05 3차원 디지털 설계측량.hwp"),

    # ── 안전관리 매뉴얼 (제6편 안전관리의 바탕 자료)
    ("safety", "측량 안전관리 매뉴얼 (2026.1)", "공간정보품질관리원", "매뉴얼", "202601", "ko", "safety",
     r"안전관리규정\측량안전관리매뉴얼.2026.01.pdf"),
    ("safety", "지적측량 안전매뉴얼", "한국국토정보공사", "매뉴얼", "2021", "ko", "safety",
     r"안전관리규정\지적측량 안전매뉴얼.pdf"),

    # ── 국외 관련규정
    ("intl", "作業規程の準則 (일본 국토지리원 2025)", "일본 국토지리원", "준칙", "2025", "ja", "intl",
     r"국외관련규정\일본_작업규정의준칙_2025\00_作業規程の準則_전문.pdf"),
    ("intl", "公共測量の手引 (일본 2026년도판)", "일본 국토지리원", "안내서", "2026", "ja", "intl",
     r"국외관련규정\일본_작업규정의준칙_2025\公共測量の手引_2026년도판.pdf"),
    ("intl", "ASPRS Positional Accuracy Standards Ed.2 v2", "ASPRS", "표준", "2024", "en", "intl",
     r"국외관련규정\2024_ASPRS_Positional_Accuracy_Standards_Edition2_Version2.0_영문원본.pdf"),
    ("intl", "USGS Lidar Base Specification 2025 rev.A", "USGS", "표준", "2025", "en", "intl",
     r"국외관련규정\미국_USGS_FGDC\USGS_Lidar_Base_Specification_2025_revA.docx"),
    ("intl", "FGDC-STD-007.3-1998 NSSDA", "FGDC", "표준", "1998", "en", "intl",
     r"국외관련규정\미국_USGS_FGDC\FGDC-STD-007.3-1998_NSSDA_Geospatial_Positioning_Accuracy_Standards_Part3.pdf"),
    ("intl", "Cadastral Survey Rules 2021 전환 안내 (LINZ)", "LINZ", "안내서", "2021", "en", "intl",
     r"국외관련규정\뉴질랜드_LINZ\LINZ_Transitioning_from_RCS2010_to_CSR2021_v4.0.pdf"),
    ("intl", "WA Main Roads Geodetic Control Survey Standard", "WA Main Roads", "표준", "2020", "en", "intl",
     r"국외관련규정\호주_ICSM_SP1\WA-MainRoads_Geodetic-Control-Survey-Standard.pdf"),
]


def next_id(lib, prefix="loc"):
    used = {r["id"] for r in lib["regulations"]}
    i = 0
    while True:
        i += 1
        sid = f"{prefix}{i:02d}"
        if sid not in used:
            return sid


if __name__ == "__main__":
    want = set(a for a in sys.argv[1:] if a)
    libpath = os.path.join(DATA, "library.json")
    lib = json.load(io.open(libpath, encoding="utf-8"))
    by_name = {r["name"]: r for r in lib["regulations"]}

    tmp = tempfile.mkdtemp(prefix="genlocal_")
    ok, fail = 0, []
    for grp, name, org, kind, ef, lang, cat, rel in ITEMS:
        if want and grp not in want:
            continue
        path = os.path.join(REG, rel)
        if not os.path.exists(path):
            fail.append((name, "파일 없음"))
            print(f"  [파일없음] {name}")
            continue
        try:
            lines = extract_lines(path)
            if len(lines) < 20:
                raise RuntimeError(f"글줄이 너무 적습니다 ({len(lines)}줄) — 표지만 있는 파일로 보입니다")

            prev = by_name.get(name)
            sid = prev["id"] if prev and str(prev["id"]).startswith("loc") else next_id(lib)
            meta = {"id": sid, "name": name, "org": org, "kind": kind, "no": "-",
                    "effective": ef, "lang": lang, "category": cat,
                    "source": "", "path": rel}

            lp = os.path.join(tmp, "lines.json")
            mp = os.path.join(tmp, "meta.json")
            op = os.path.join(DATA, sid + ".json")
            io.open(lp, "w", encoding="utf-8").write(json.dumps(lines, ensure_ascii=False))
            io.open(mp, "w", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False))

            r = subprocess.run(["node", os.path.join(HERE, "buildlocal.mjs"), lp, mp, op],
                               capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
            if r.returncode != 0:
                raise RuntimeError((r.stderr or r.stdout).strip()[:160])
            info = json.loads(r.stdout.strip().splitlines()[-1])

            doc = json.load(io.open(op, encoding="utf-8"))
            e = {k: doc[k] for k in ("id", "name", "org", "kind", "no", "effective",
                                     "lang", "category", "source", "stats")}
            e["file"] = sid + ".json"
            e["hasFullText"] = True
            e["indexMode"] = doc.get("indexMode", "")
            e["localFile"] = rel
            if doc.get("translated"):
                e["translated"] = doc["translated"]
            # 목록에 있던 '파일만 보유' 항목은 갈아 끼운다
            lib["regulations"] = [x for x in lib["regulations"]
                                  if x["name"] != name and x["id"] != sid]
            lib["regulations"].append(e)
            by_name[name] = e
            ok += 1
            tr = f" · 한글 대역 {info['translated']}%" if info.get("translated") else ""
            print(f"  OK  {sid}  {info['mode']:>2} 기준 · "
                  f"편 {doc['stats'].get('편', 0)} 장 {doc['stats'].get('장', 0)} "
                  f"항목 {doc['stats'].get('조', 0):>4}{tr}   {name}")
        except Exception as ex:
            fail.append((name, str(ex)))
            print(f"  [오류] {name}: {ex}")

    with io.open(libpath, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)

    print(f"\n심은 규정 {ok}종 / 실패 {len(fail)}종")
    for n, why in fail:
        print(f"   - {n}: {why}")
