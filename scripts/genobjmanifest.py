# -*- coding: utf-8 -*-
"""data/objects/manifest.json 을 다시 짓는다.

화면은 규정마다 index.json 과 annex-index.json 을 부른다. 없는 자리까지
무턱대고 부르면 콘솔이 404 로 뒤덮여 정작 봐야 할 오류가 묻히므로,
무엇이 있는지 미리 적어 둔다.

genobjects.py 로 표ㆍ수식을 새로 뽑았거든 이것을 한 번 돌린다.

사용:  python scripts/genobjmanifest.py
"""
import io, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "data", "objects")

man = {}
for d in sorted(os.listdir(BASE)):
    p = os.path.join(BASE, d)
    if not os.path.isdir(p):
        continue
    man[d] = {"index": os.path.exists(os.path.join(p, "index.json")),
              "annex": os.path.exists(os.path.join(p, "annex-index.json"))}

out = os.path.join(BASE, "manifest.json")
io.open(out, "w", encoding="utf-8", newline="\n").write(
    json.dumps(man, ensure_ascii=False, separators=(",", ":")))
print("manifest.json — 자리 %d개 (본문 색인 %d · 별표 색인 %d)" % (
    len(man), sum(v["index"] for v in man.values()), sum(v["annex"] for v in man.values())))
