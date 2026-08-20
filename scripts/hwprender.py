# -*- coding: utf-8 -*-
"""한글 COM 을 한 번만 띄워 문서 여럿을 PDF (와 .hwp) 로 뽑는다.

hwp2pdf.ps1 에 목록 파일을 넘겨 주는 잔심부름꾼이다. 다른 스크립트에서

    from hwprender import render
    render([...경로...], also_hwp=True)

처럼 부른다.
"""
import io, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PS1 = os.path.join(HERE, "hwp2pdf.ps1")


def render(paths, outdir=None, also_hwp=False, quiet=False):
    """돌려주는 것 — {이름: 쪽수} 와 실패한 것들의 목록"""
    paths = [os.path.abspath(p) for p in paths]
    if not paths:
        return {}, []
    fd, lst = tempfile.mkstemp(suffix=".txt", text=True)
    os.close(fd)
    io.open(lst, "w", encoding="utf-8", newline="\n").write("\n".join(paths))
    args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", PS1,
            "-ListFile", lst]
    if outdir:
        args += ["-OutDir", os.path.abspath(outdir)]
    if also_hwp:
        args += ["-AlsoHwp"]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
    os.unlink(lst)

    pages, bad = {}, []
    for ln in (r.stdout or "").splitlines():
        f = ln.split("\t")
        if f[0] == "OK" and len(f) >= 3:
            pages[f[1]] = int(f[2])
        elif f[0] == "FAIL" and len(f) >= 3:
            bad.append((f[1], f[2]))
    if not quiet and (bad or r.returncode not in (0, 2)):
        sys.stderr.write((r.stdout or "")[-1500:] + (r.stderr or "")[-1500:])
    return pages, bad


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    pg, bad = render(sys.argv[1:])
    for k, v in pg.items():
        print("   %-24s %d쪽" % (k, v))
    for k, m in bad:
        print("   실패 %-20s %s" % (k, m))
