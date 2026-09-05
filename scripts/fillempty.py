# -*- coding: utf-8 -*-
"""
서고 사본의 빈 조에 까닭을 채운다 (할일 ㉪).

  checklib 이 「제목도 본문도 없음」 으로 짚는 조가 있다. 색인이 빠뜨린 것이
  아니라 법이 그 번호를 비워 둔 자리다. 이를테면

    시설물의 안전 및 유지관리에 관한 특별법 시행령 제39조
      → [종전 제39조는 제17조의4로 이동 <2020.2.18>]

  법제처 Open API 는 이것을 <조문참고자료> 로 준다. gendata.py 가 그것을
  버리는 바람에 화면에는 번호만 남고 까닭이 사라진다. 그 글을 본문에 담는다.

사용:  python scripts/fillempty.py            (고칠 것만 보임)
       python scripts/fillempty.py --write    (자료에 담음)
"""
import json, os, io, re, sys, time, urllib.parse, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(os.path.dirname(HERE), "data")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0 Safari/537.36"}
WRITE = "--write" in sys.argv


def get(url, tries=3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read().decode("utf-8")
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2)


def walk(ns):
    for n in ns:
        yield n
        for m in walk(n.get("children") or []):
            yield m


def find_mst(name):
    """법령명으로 법령일련번호(MST)를 찾는다 — gendata.py 와 같은 길"""
    q = urllib.parse.quote(name)
    xml = get(f"https://www.law.go.kr/DRF/lawSearch.do?OC=test&target=law&query={q}&type=XML&display=100")
    norm = lambda s: re.sub(r"[\s·ㆍ・()]", "", s)
    names = re.findall(r"<법령명한글>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</법령명한글>", xml, re.S)
    seqs = re.findall(r"<법령일련번호>(\d+)</법령일련번호>", xml)
    for nm, sq in zip(names, seqs):
        if norm(nm) == norm(name):
            return sq
    return seqs[0] if seqs else None


def notes_of(mst):
    """조문번호 → 조문참고자료. 가지번호가 붙은 조는 건너뛴다."""
    xml = get(f"https://www.law.go.kr/DRF/lawService.do?OC=test&target=law&MST={mst}&type=XML")
    out = {}
    for a in re.findall(r"<조문단위[^>]*>.*?</조문단위>", xml, re.S):
        if re.search(r"<조문가지번호>\d", a):
            continue
        no = re.search(r"<조문번호>(\d+)</조문번호>", a)
        ref = re.search(r"<조문참고자료>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</조문참고자료>", a, re.S)
        if no and ref and ref.group(1).strip():
            out[no.group(1)] = ref.group(1).strip()
    return out


def main():
    lib = json.load(io.open(os.path.join(DATA, "library.json"), encoding="utf-8"))
    regs = lib.get("regulations") or []
    todo = {}                       # 규정id → [(마디, 조번호)]
    meta = {}
    for r in regs:
        f = os.path.join(DATA, r.get("file") or "")
        if not r.get("file") or not os.path.exists(f):
            continue
        d = json.load(io.open(f, encoding="utf-8"))
        empty = [n for n in walk(d.get("tree") or [])
                 if n.get("level") == "조"
                 and not (n.get("title") or "").strip()
                 and not (n.get("body") or "").strip()]
        if empty:
            todo[r["id"]] = empty
            meta[r["id"]] = (r.get("name") or "", f)

    if not todo:
        print("빈 조가 없습니다.")
        return

    for rid, nodes in todo.items():
        name, path = meta[rid]
        nos = ", ".join(f"제{n.get('no')}조" for n in nodes)
        print(f"■ {rid} 「{name}」 — 빈 조 {len(nodes)}개 : {nos}")
        try:
            mst = find_mst(name)
            notes = notes_of(mst) if mst else {}
        except Exception as e:
            print(f"    법제처에서 받지 못하였습니다 — {e}")
            continue

        got = 0
        for n in nodes:
            note = notes.get(str(n.get("no")))
            if not note:
                print(f"    제{n.get('no')}조 — 참고자료도 없음")
                continue
            print(f"    제{n.get('no')}조 ← {note}")
            n["body"] = note
            got += 1

        if got and WRITE:
            d = json.load(io.open(path, encoding="utf-8"))
            byno = {str(n.get("no")): n.get("body") for n in nodes if n.get("body")}
            for n in walk(d.get("tree") or []):
                if (n.get("level") == "조" and not (n.get("title") or "").strip()
                        and not (n.get("body") or "").strip()
                        and str(n.get("no")) in byno):
                    n["body"] = byno[str(n.get("no"))]
            # 서고 사본과 같은 꼴로 담는다 — 한 줄, 사이는 기본 공백.
            # 꼴이 어긋나면 고친 한 자리가 파일 전체 변경으로 잡힌다.
            io.open(path, "w", encoding="utf-8", newline="").write(
                json.dumps(d, ensure_ascii=False))
            print(f"    → {os.path.basename(path)} 에 {got}개를 담았습니다.")

    if not WRITE:
        print("\n담으려면 --write 를 붙여 다시 돌리십시오.")


if __name__ == "__main__":
    main()
