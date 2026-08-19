# -*- coding: utf-8 -*-
"""
본문이 첨부파일에만 있는 고시를 색인한다.

국가법령정보센터의 어떤 고시는 조문 자리에 "자세한 내용은 상단 메뉴를
이용하십시오" 라고만 적고, 실제 기준은 첨부파일(전문 ZIP) 에 담아 둔다.
KCS·KDS 가 그러하다. 그 첨부를 내려받아 풀고, 안에 든 HWP·HWPX 를
글줄로 바꾸어 genlocal 과 같은 방법으로 구조를 세운다.

사용:  python scripts/addattach.py
출력:  data/locNN.json · library.json 갱신
"""
import io, json, os, re, subprocess, sys, tempfile, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gendata as G
import genlocal as L

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

# (검색어, 목록에 올릴 이름, 기관, 종류, 구분)
ITEMS = [
    ("건설공사 측량 표준시방서", "건설공사 측량 표준시방서 (KCS 12 00 00)",
     "국토교통부", "표준시방서", "sub"),
    ("건설측량 설계기준", "건설측량 설계기준 (KDS 12 00 00)",
     "국토교통부", "설계기준", "sub"),
    ("공간정보 제공 수수료", "공간정보 제공 수수료 조정",
     "국토지리정보원", "고시", "sub"),
]


def fetch_bin(url):
    import urllib.request
    req = urllib.request.Request(url, headers=G.UA)
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def attachments(seq):
    j = json.loads(G.get("https://www.law.go.kr/DRF/lawService.do?OC=test"
                         f"&target=admrul&ID={seq}&type=JSON"))
    root = j.get("AdmRulService") or j
    att = root.get("첨부파일") or {}
    links = att.get("첨부파일링크") or []
    names = att.get("첨부파일명") or []
    if isinstance(links, str):
        links, names = [links], [names]
    body = root.get("조문내용") or ""
    if isinstance(body, list):
        body = "\n".join(str(x) for x in body)
    return list(zip(names, links)), str(body)


def lines_from(path):
    """파일 하나에서 글줄을 뽑는다 (ZIP 이면 안쪽에서 가장 큰 문서를 고른다)"""
    if path.lower().endswith(".zip"):
        out = []
        with zipfile.ZipFile(path) as z:
            cand = [n for n in z.namelist()
                    if re.search(r"\.(hwp|hwpx|docx|pdf)$", n, re.I)]
            cand.sort(key=lambda n: z.getinfo(n).file_size, reverse=True)
            tmp = tempfile.mkdtemp(prefix="attach_")
            for n in cand[:3]:
                p = os.path.join(tmp, os.path.basename(n))
                io.open(p, "wb").write(z.read(n))
                try:
                    got = L.extract_lines(p)
                except Exception:
                    got = []
                if len(got) > len(out):
                    out = got
        return out
    return L.extract_lines(path)


def flat(op, meta, lines):
    """조문도 목차도 없는 짧은 고시를 한 덩이로 담는다"""
    doc = dict(meta)
    doc.pop("path", None)
    doc.update({
        "promulgated": "", "annex": [], "annexTree": [], "indexMode": "전문",
        "stats": {"편": 1, "장": 0, "절": 0, "관": 0, "조": 0,
                  "별표": 0, "별지": 0, "변경": 0},
        "tree": [{
            "id": "flat-" + meta["id"], "level": "편", "no": 1, "branch": 0,
            "title": meta["name"], "body": "\n".join(lines), "status": "유지",
            "legacyNo": "", "reason": "", "sourceRef": None, "history": [],
            "children": [], "collapsed": False,
        }],
    })
    with io.open(op, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))


def main():
    libpath = os.path.join(DATA, "library.json")
    lib = json.load(io.open(libpath, encoding="utf-8"))
    tmp = tempfile.mkdtemp(prefix="addattach_")
    ok, fail = 0, []

    for q, name, org, kind, cat in ITEMS:
        try:
            hit = G.find("admrul", q)
            if not hit:
                raise RuntimeError("검색 결과 없음")
            files, body = attachments(hit["seq"])
            lines = []
            for fn, url in files:
                if "이유서" in fn:                      # 제·개정 이유서는 본문이 아니다
                    continue
                p = os.path.join(tmp, fn)
                io.open(p, "wb").write(fetch_bin(url))
                got = lines_from(p)
                if len(got) > len(lines):
                    lines = got
            if len(lines) < 20:                        # 첨부가 없으면 조문내용이라도 쓴다
                lines = [x.strip() for x in re.split(r"[\n]+", body) if x.strip()]
            if len(lines) < 3:
                raise RuntimeError("본문을 얻지 못했습니다")

            sid = L.next_id(lib)
            meta = {"id": sid, "name": name, "org": org, "kind": kind,
                    "no": hit.get("no") or "-", "effective": hit.get("ef") or "",
                    "lang": "ko", "category": cat, "source": "", "path": ""}
            lp, mp = os.path.join(tmp, "l.json"), os.path.join(tmp, "m.json")
            op = os.path.join(DATA, sid + ".json")
            io.open(lp, "w", encoding="utf-8").write(json.dumps(lines, ensure_ascii=False))
            io.open(mp, "w", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False))
            r = subprocess.run(["node", os.path.join(HERE, "buildlocal.mjs"), lp, mp, op],
                               capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
            if r.returncode != 0:
                msg = (r.stderr or r.stdout).strip()
                if "구조를 찾지 못했습니다" not in msg:
                    raise RuntimeError(msg[:160])
                # 조문도 목차도 없는 짧은 고시 — 한 덩이로 담는다
                flat(op, meta, lines)

            doc = json.load(io.open(op, encoding="utf-8"))
            doc["source"] = ("https://www.law.go.kr/LSW/admRulInfoP.do?admRulSeq="
                             + str(hit["seq"]))
            doc["attachments"] = [{"name": n, "url": u} for n, u in files]
            with io.open(op, "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))

            e = {k: doc[k] for k in ("id", "name", "org", "kind", "no", "effective",
                                     "lang", "category", "source", "stats")}
            e["file"] = sid + ".json"
            e["hasFullText"] = True
            e["indexMode"] = doc.get("indexMode", "")
            lib["regulations"] = [x for x in lib["regulations"]
                                  if G.norm(x["name"]) != G.norm(name) and x["id"] != sid]
            lib["regulations"].append(e)
            ok += 1
            print(f"  OK  {sid}  {doc.get('indexMode','')} 기준 · 편 {doc['stats'].get('편',0)} "
                  f"장 {doc['stats'].get('장',0)} 항목 {doc['stats'].get('조',0):>4}   {name}")
        except Exception as ex:
            fail.append((name, str(ex)))
            print(f"  [오류] {name}: {ex}")

    with io.open(libpath, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)
    print(f"\n색인 {ok}종 / 실패 {len(fail)}종")
    for n, e in fail:
        print(f"   - {n} : {e}")


if __name__ == "__main__":
    main()
