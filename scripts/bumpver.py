# -*- coding: utf-8 -*-
"""화면 파일의 캐시 꼬리표(?v=...)를 한꺼번에 갈아 준다.

index.html 과 js/ 아래 모든 import 에 같은 꼬리표가 박혀 있다. 하나만 갈면
브라우저가 나머지를 옛것으로 가져다 써, 고친 것이 화면에 나타나지 아니한다.
실제로 그런 일이 있었다 — index.html 만 갈았더니 detail.js 는 옛것이 돌았다.

사용:
  python scripts/bumpver.py            오늘 날짜로 새 꼬리표를 짓는다
  python scripts/bumpver.py 20260820a  꼬리표를 직접 준다
  python scripts/bumpver.py --check    지금 몇 가지가 섞여 있는지 본다
"""
import io, os, re, sys, time

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RE = re.compile(r"\?v=([0-9a-z]+)")


def files():
    out = [os.path.join(ROOT, "index.html")]
    for d, _, fs in os.walk(os.path.join(ROOT, "js")):
        out += [os.path.join(d, f) for f in fs if f.endswith(".js")]
    return [p for p in out if os.path.exists(p)]


def tags():
    seen = {}
    for p in files():
        s = io.open(p, encoding="utf-8").read()
        for t in RE.findall(s):
            seen.setdefault(t, []).append(os.path.relpath(p, ROOT))
    return seen


def nextver():
    """오늘 날짜 + a~z — 같은 날 여러 번 갈 수 있게 한다"""
    today = time.strftime("%Y%m%d")
    used = sorted(t[len(today):] for t in tags() if t.startswith(today))
    ch = "a"
    if used:
        last = used[-1] or "a"
        ch = chr(ord(last[-1]) + 1) if last[-1] < "z" else "z"
    return today + ch


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    seen = tags()
    if "--check" in sys.argv:
        for t, ps in sorted(seen.items(), key=lambda kv: -len(kv[1])):
            print("  %-12s %3d곳  %s" % (t, len(ps), ", ".join(sorted(set(ps))[:4])))
        print("\n%s" % ("섞여 있다 — bumpver.py 로 맞추십시오" if len(seen) > 1 else "한 가지로 맞아 있다"))
        sys.exit(1 if len(seen) > 1 else 0)

    new = args[0] if args else nextver()
    n = 0
    for p in files():
        s = io.open(p, encoding="utf-8").read()
        s2, k = RE.subn("?v=" + new, s)
        if k:
            io.open(p, "w", encoding="utf-8", newline="\n").write(s2)
            n += k
    print("꼬리표를 %s 로 맞추었다 — %d곳" % (new, n))
