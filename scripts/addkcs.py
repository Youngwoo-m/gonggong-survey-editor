# -*- coding: utf-8 -*-
"""
KCS 12 00 00 전문 ZIP 안의 하위 표준시방서를 낱낱이 색인한다.

고시 첨부 ZIP 에 KCS 12 10 05·12 20 05·12 20 10·12 20 15·12 20 20 다섯 가지가
따로 들어 있는데, 목록에는 상위 고시 하나만 있었다. KDS 하위 기준 열 가지가
낱낱이 색인되어 있는 것과 맞추어 이들도 따로 세운다.

사용:  python scripts/addkcs.py
"""
import io, json, os, re, subprocess, sys, tempfile, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gendata as G
import genlocal as L

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")


def main():
    libpath = os.path.join(DATA, "library.json")
    lib = json.load(io.open(libpath, encoding="utf-8"))
    hit = G.find("admrul", "건설공사 측량 표준시방서")
    j = json.loads(G.get("https://www.law.go.kr/DRF/lawService.do?OC=test"
                         f"&target=admrul&ID={hit['seq']}&type=JSON"))
    att = (j.get("AdmRulService") or j).get("첨부파일") or {}
    zip_url = next((u for n, u in zip(att.get("첨부파일명") or [],
                                      att.get("첨부파일링크") or [])
                    if n.lower().endswith(".zip")), None)
    if not zip_url:
        print("전문 ZIP 을 찾지 못했습니다"); return

    raw = urllib.request.urlopen(
        urllib.request.Request(zip_url, headers=G.UA), timeout=180).read()
    tmp = tempfile.mkdtemp(prefix="kcs_")
    zp = os.path.join(tmp, "kcs.zip")
    io.open(zp, "wb").write(raw)

    ok, fail = 0, []
    with zipfile.ZipFile(zp) as z:
        for info in z.infolist():
            fn = os.path.basename(info.filename)
            m = re.match(r"(KCS \d{2} \d{2} \d{2})\s+(.+?)(?:_제정|_개정)?\.(hwpx?|docx)$", fn)
            if not m or "12 00 00" in m.group(1):     # 상위 고시는 이미 색인했다
                continue
            code, title = m.group(1), m.group(2).strip()
            name = f"{code} {title}"
            try:
                p = os.path.join(tmp, fn)
                io.open(p, "wb").write(z.read(info))
                lines = L.extract_lines(p)
                if len(lines) < 20:
                    raise RuntimeError(f"글줄이 너무 적습니다 ({len(lines)}줄)")

                sid = L.next_id(lib)
                meta = {"id": sid, "name": name, "org": "국토교통부",
                        "kind": "표준시방서", "no": hit.get("no") or "-",
                        "effective": hit.get("ef") or "", "lang": "ko",
                        "category": "kds", "source": "", "path": ""}
                lp, mp = os.path.join(tmp, "l.json"), os.path.join(tmp, "m.json")
                op = os.path.join(DATA, sid + ".json")
                io.open(lp, "w", encoding="utf-8").write(json.dumps(lines, ensure_ascii=False))
                io.open(mp, "w", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False))
                r = subprocess.run(["node", os.path.join(HERE, "buildlocal.mjs"), lp, mp, op],
                                   capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
                if r.returncode != 0:
                    raise RuntimeError((r.stderr or r.stdout).strip()[:140])

                doc = json.load(io.open(op, encoding="utf-8"))
                doc["source"] = ("https://www.law.go.kr/LSW/admRulInfoP.do?admRulSeq="
                                 + str(hit["seq"]))
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
                print(f"  OK  {sid}  편 {doc['stats'].get('편',0)} 장 {doc['stats'].get('장',0)}   {name}")
            except Exception as ex:
                fail.append((name, str(ex)))
                print(f"  [오류] {name}: {ex}")

    with io.open(libpath, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)
    print(f"\n색인 {ok}종 / 실패 {len(fail)}종")


if __name__ == "__main__":
    main()
