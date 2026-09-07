# -*- coding: utf-8 -*-
r"""원고(Markdown)를 **양식 파일 위에** 얹어 한/글 문서(HWPX)를 만든다.

■ 왜 양식 위에 얹는가

  HWPX 를 새로 짜면 글꼴ㆍ쪽 설정ㆍ표 테두리ㆍ문단 간격이 모두 우리가 정한
  것이 된다. 그러면 양식과 '비슷한' 문서가 나올 뿐 양식 그대로는 아니다.

  양식 파일을 그대로 열어 글자만 갈아 끼우면 서식이 한 치도 어긋나지 않는다.
  Form\03.개정사유서\[양식] 작업규정 개정안_개정사유서.hwpx 는 일곱 절이 모두
  채워진 완성본이므로, 자리마다 우리 글을 넣기만 하면 된다.

■ 자리를 어떻게 맞추는가

  양식을 뜯어 보니 다행한 조건이 갖추어져 있었다.

      ㆍ 글이 든 문단마다 <hp:t> 조각이 꼭 하나씩이다 (187자리)
      ㆍ 네 글자 이상인 조각 가운데 겹치는 글이 하나도 없다

  그래서 XML 을 다시 쓰지 아니하고 <hp:t> 를 **나온 차례대로** 세어 그 자리의
  글만 갈아 끼운다. 이름공간 접두사도, 표 구조도, 문단 속성도 건드리지 않는다.

  자리 수가 어긋나면 아무것도 쓰지 않고 멈춘다 — 한 자리라도 밀리면 엉뚱한
  칸에 글이 들어가므로, 조용히 틀리느니 서는 편이 낫다.

■ 뒤처리와 검증 (hwpx 스킬 절차)

  1) 치환한 뒤 fix_namespaces.py 를 반드시 돌린다
  2) validate_hwpx_package.py 로 꾸러미를 본다
  3) 한/글(COM)로 열어 쪽수를 얻고 PDF 로 저장한다

사용:
  python Report\scripts\build_from_form.py 원고\무인비행장치_개정사유서.md
  python Report\scripts\build_from_form.py 원고\...md --out "D:\어느\폴더" --pdf
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                                   # …\prototype\Report
PROTO = os.path.dirname(ROOT)                                  # …\App\prototype
BASE = os.path.dirname(os.path.dirname(PROTO))                 # …\2026.공공측량.품관원
FORM = os.path.join(BASE, "Form")
SKILL = os.path.join(os.path.expanduser("~"), ".claude", "skills", "hwpx")

# 표를 다루는 연장은 편집기 쪽 것을 그대로 쓴다 — 두 벌을 두지 아니한다.
sys.path.insert(0, os.path.join(PROTO, "scripts"))
import formfill as FF                                          # noqa: E402

# 원고 이름 → 양식 파일. 새 원고를 넣을 때 여기에 한 줄 더 적는다.
TEMPLATES = {
    "개정사유서": os.path.join(FORM, "03.개정사유서",
                          "[양식] 작업규정 개정안_개정사유서.hwpx"),
}

RE_T = re.compile(r"<hp:t(\s[^>]*)?>(.*?)</hp:t>", re.S)
RE_SEG = re.compile(r"<hp:linesegarray>.*?</hp:linesegarray>"
                    r"|<hp:linesegarray\s*/>", re.S)


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def unesc(s):
    return (s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))


# ─────────────────────────────────── 원고 읽기
def read_md(path):
    """원고 → 자리에 넣을 글을 나온 차례대로.

    → (자리 목록, 표마다의 (자리 시작, 행 수, 열 수))

    양식의 <hp:t> 차례와 같아야 한다 —
      제목 · 절 이름 · 문단 · (표가 나오면 머리행부터 칸 차례로) · …
    표를 담은 문단은 제 글이 없으므로 자리를 차지하지 않는다."""
    md = re.sub(r"<!--.*?-->", "", io.open(path, encoding="utf-8").read(), flags=re.S)
    slots, para, table = [], [], []
    # 표마다 (자리 목록에서 시작한 곳, 행 수, 열 수) — 양식의 표를 이만큼
    # 늘리거나 줄이려는 것이다. 원고가 양식보다 조문을 많이 담을 때 쓴다.
    tables = []

    def flush_para():
        if para:
            slots.append(" ".join(para))
            para.clear()

    def flush_table():
        if not table:
            return
        rows = [r for r in table
                if not re.fullmatch(r"\s*\|[\s:|-]+\|\s*", r)]
        at, ncol = len(slots), 0
        for r in rows:
            cells = [c.strip() for c in r.strip().strip("|").split("|")]
            ncol = max(ncol, len(cells))
            slots.extend(cells)
        tables.append((at, len(rows), ncol))
        table.clear()

    for raw in md.split("\n"):
        s = raw.strip()
        if s.startswith("|") and s.endswith("|"):
            flush_para()
            table.append(s)
            continue
        flush_table()
        if not s:
            flush_para()
            continue
        if s.startswith("#"):
            flush_para()
            slots.append(s.lstrip("#").strip())
        elif s.startswith("- "):
            flush_para()
            slots.append(s[2:].strip())
        else:
            para.append(s)
    flush_para()
    flush_table()
    return ([re.sub(r"\*\*(.+?)\*\*", r"\1", x) for x in slots], tables)


# ─────────────────────────────────── 치환
def leaf_paras(xml):
    """[(문단 시작, 문단 끝, 문단모양 id, 글)] — 표를 담은 문단은 뺀다"""
    out = []
    for m in re.finditer(r"<hp:p\s[^>]*>", xml):
        e = xml.find("</hp:p>", m.end())
        if e < 0:
            continue
        span = xml[m.end():e]
        if "<hp:p " in span:              # 안에 또 문단이 있으면 표를 담은 것
            continue
        pid = re.search(r'paraPrIDRef="(\d+)"', m.group(0))
        txt = "".join(t.group(2) for t in RE_T.finditer(span)).strip()
        out.append((m.start(), e + len("</hp:p>"),
                    pid.group(1) if pid else "", unesc(txt)))
    return out


RE_HEAD = re.compile(r"^\d+\.\s")


def keep_heads_with_next(head_xml, sec_xml):
    """절 제목의 문단모양에 '다음 문단과 함께'를 켠다 → (고친 xml, 켠 수)

    양식의 표는 '글자처럼 취급'(treatAsChar=1)이라 쪽을 넘겨 쪼개지지 못하고,
    남은 자리에 못 들어가면 통째로 다음 쪽으로 밀린다. 그러면 바로 앞의 절
    제목만 앞 쪽에 홀로 남아 「4. 조항별 개정 사유」 한 줄짜리 빈 쪽이 생긴다.

    제목을 뒤 문단과 묶어 두면 제목도 함께 넘어가 그 빈 쪽이 없어진다.
    표의 배치 속성을 건드리는 것보다 훨씬 얌전한 손질이다."""
    ids = set()
    for b, _e, pid, txt in leaf_paras(sec_xml):
        if pid and RE_HEAD.match(txt):
            ids.add(pid)
    n = 0
    out = head_xml
    for pid in ids:
        m = re.search(r'<hh:paraPr\b[^>]*\bid="%s"[^>]*>' % pid, out)
        if not m:
            continue
        e = out.find("</hh:paraPr>", m.end())
        blk = out[m.start():e]
        new = re.sub(r'(<hh:breakSetting\b[^>]*?\bkeepWithNext=")0(")',
                     r"\g<1>1\g<2>", blk, count=1)
        if new != blk:
            out = out[:m.start()] + new + out[e:]
            n += 1
    return out, n


def unchain_tables(xml):
    """긴 표가 쪽을 넘겨 쪼개지도록 '글자처럼 취급'을 푼다 → (xml, 푼 수)

    양식의 표는 treatAsChar=1 이다. 그러면 표가 글자 하나처럼 다루어져 쪽을
    넘겨 쪼개지지 못한다. 남은 자리에 못 들어가면 통째로 다음 쪽으로 밀리고,
    바로 앞의 절 제목만 홀로 남아 한 줄짜리 빈 쪽이 생긴다.

    표에는 이미 pageBreak="CELL"(쪽 경계에서 셀 단위로 나눔)과
    textWrap="TOP_AND_BOTTOM"(자리 차지)이 걸려 있으므로, 글자처럼 취급만
    풀면 생김새는 그대로 두고 쪼개지기만 한다.

    쪽에 다 들어가는 짧은 표는 건드리지 아니한다 — 바꿀 까닭이 없다."""
    LONG = 10                      # 이보다 행이 많으면 쪼개질 수 있게 둔다
    n = 0
    out, tail = [], 0
    for m in re.finditer(r"<hp:tbl\s[^>]*>", xml):
        tag = m.group(0)
        rows = re.search(r'rowCnt="(\d+)"', tag)
        if not rows or int(rows.group(1)) < LONG:
            continue
        e = xml.find(">", xml.find("<hp:pos ", m.end()))
        pos = xml[xml.find("<hp:pos ", m.end()):e + 1]
        if 'treatAsChar="1"' not in pos:
            continue
        b = xml.find("<hp:pos ", m.end())
        out.append(xml[tail:b])
        out.append(pos.replace('treatAsChar="1"', 'treatAsChar="0"'))
        tail = e + 1
        n += 1
    out.append(xml[tail:])
    return "".join(out), n


def fit_tables(xml, want):
    """양식의 표를 원고의 행 수에 맞춘다 → (고친 xml, [(양식 행, 원고 행), …])

    양식은 187자리로 굳어 있다. 4절 「조항별 개정 사유」는 11개 조, 5절
    「별표 개정 및 신설 사유」는 15건까지밖에 담지 못한다. 무인비행장치는
    그 안에 들었으나, 작업규정(고치는 조 105개ㆍ별표 61건)과 성과심사
    규정은 들지 아니한다. 그래서 원고를 쓸 수 없었다.

    마지막 자료 행을 본으로 삼아 그만큼 찍어 내거나 잘라 낸다. 폭ㆍ병합ㆍ
    여백이 그 행의 것 그대로이므로 서식이 어긋나지 아니한다. 칸 안의 글은
    어차피 뒤에서 자리마다 갈아 끼우므로 여기서는 자리만 맞춘다.

    편집기 쪽 formfill 을 그대로 쓴다 — 표를 다루는 연장을 두 벌 두지
    아니한다(scripts/formdocs.py 도 같은 것을 쓴다)."""
    done = []
    for n, (_at, rows_want, _ncol) in enumerate(want):
        span = FF.table_span(xml, n)
        if not span:
            break
        tbl = xml[span[0]:span[1]]
        trs = FF.top_rows(tbl)
        done.append((len(trs), rows_want))
        if len(trs) == rows_want or rows_want < 2 or len(trs) < 2:
            continue
        keep = trs[:rows_want]
        proto = trs[-1]
        for i in range(len(trs), rows_want):        # 모자라면 찍어 낸다
            keep.append(re.sub(r'(<hp:cellAddr\s[^>]*\browAddr=")\d+(")',
                               r"\g<1>%d\g<2>" % i, proto))
        xml = (xml[:span[0]]
               + FF.retable(tbl, "".join(keep), rows_want)
               + xml[span[1]:])
    return xml, done


def drop_empty_bullets(xml, touched):
    """우리가 고친 불릿 바로 뒤에 붙은 빈 불릿을 걷어 낸다.

    양식의 6절 끝에 글 없는 불릿 문단이 하나 있었다. 그 자리는 치환 대상이
    아니어서(글이 없으므로) 그대로 남았고, 문서에 빈 동그라미로 찍혔다.

    빈 문단이라고 다 걷어 내면 안 된다 — 표 안의 빈 칸이나 사이를 띄우는 빈
    줄까지 사라진다. 그래서 바로 앞 문단이 (가) 우리가 고친 것이고 (나) 문단
    모양이 같은 것일 때에만 걷어 낸다. 그것이 곧 같은 목록의 빈 항목이다."""
    paras = leaf_paras(xml)
    cuts = []
    for i, (b, e, pid, txt) in enumerate(paras):
        if txt or i == 0:
            continue
        pb, pe, ppid, ptxt = paras[i - 1]
        if ppid and ppid == pid and ptxt in touched:
            cuts.append((b, e))
    for b, e in reversed(cuts):
        xml = xml[:b] + xml[e:]
    return xml, len(cuts)


def fill(tpl_path, dst_path, slots, tables=()):
    """양식의 <hp:t> 자리에 글을 차례대로 넣는다 → (자리 수, 바꾼 수)

    tables 는 원고가 쓴 표마다의 (자리 시작, 행 수, 열 수)다. 자리를 세기
    앞서 양식의 표를 그 행 수에 맞춘다."""
    with zipfile.ZipFile(tpl_path) as z:
        names = z.namelist()
        blobs = {n: z.read(n) for n in names}

    sec = next((n for n in names
                if re.match(r"Contents/section\d+\.xml$", n)), None)
    if not sec:
        raise SystemExit("양식에 본문 파트가 없습니다")
    xml = blobs[sec].decode("utf-8")

    xml, fitted = fit_tables(xml, tables)
    for i, (was, now) in enumerate(fitted):
        if was != now:
            print(f"   표 {i + 1} — 양식 {was}행을 원고에 맞추어 {now}행으로")

    spots = [m for m in RE_T.finditer(xml) if m.group(2).strip()]
    if len(spots) != len(slots):
        raise SystemExit(
            f"자리 수가 맞지 않습니다 — 양식 {len(spots)}자리, 원고 {len(slots)}자리.\n"
            f"  표의 행 수는 원고에 맞추었으므로, 남은 어긋남은 문단 수입니다.\n"
            f"  한 자리라도 밀리면 엉뚱한 칸에 글이 들어가므로 아무것도\n"
            f"  쓰지 않고 멈춥니다.")

    out, last, changed, touched = [], 0, 0, set()
    for m, new in zip(spots, slots):
        old = unesc(m.group(2))
        if old.strip() != new.strip():
            changed += 1
            touched.add(new.strip())
        out.append(xml[last:m.start(2)])
        out.append(esc(new))
        last = m.end(2)
    out.append(xml[last:])
    xml = "".join(out)

    # 줄 배치 캐시(<hp:linesegarray>)를 모두 걷어 낸다.
    #
    # 양식에는 한/글이 계산해 둔 줄마다의 자리가 들어 있다. 글이 길어져 줄이
    # 늘면 한/글이 그 캐시를 그대로 믿어 어긋난다. 두 가지로 나타났다.
    #
    #   ㆍ 1쪽 4문단 — 늘어난 마지막 줄이 앞줄 위에 겹쳐 찍혔다
    #   ㆍ 5쪽      — 표를 담은 문단이 옛 높이를 붙들어 표가 통째로 다음
    #                 쪽으로 밀리고 제목만 남은 빈 쪽이 생겼다
    #
    # 처음에는 글을 바꾼 문단만 걷어 냈으나, 표를 담은 문단은 제 글이 없어
    # 걸러지지 않았다. 어차피 글이 절반 넘게 바뀌므로 모두 걷어 내고 한/글이
    # 열 때 다시 재도록 둔다.
    xml = RE_SEG.sub("", xml)
    xml, dropped = drop_empty_bullets(xml, touched)
    xml, freed = unchain_tables(xml)

    blobs[sec] = xml.encode("utf-8")

    hdr = next((n for n in names if n.endswith("Contents/header.xml")
                or n == "Contents/header.xml"), None)
    kept = 0
    if hdr:
        h2, kept = keep_heads_with_next(blobs[hdr].decode("utf-8"), xml)
        blobs[hdr] = h2.encode("utf-8")

    # 미리보기 글도 갈아 준다 — 안 그러면 탐색기 미리보기가 옛 글을 보인다.
    # PrvText.txt 는 UTF-8 이다(UTF-16 으로 읽어 헛것을 본 적이 있다).
    for n in names:
        if n.lower().endswith("prvtext.txt"):
            blobs[n] = "\n".join(slots[:40]).encode("utf-8")

    tmp = dst_path + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as o:
        for n in names:                      # mimetype 은 맨 앞ㆍ무압축이라야 한다
            o.writestr(n, blobs[n],
                       zipfile.ZIP_STORED if n == "mimetype" else zipfile.ZIP_DEFLATED)
    if os.path.exists(dst_path):
        os.remove(dst_path)
    os.rename(tmp, dst_path)
    return len(spots), changed, dropped, kept, freed


def run(script, *args):
    """스킬 스크립트를 부른다 — exec 로 읽어 돌리면 __main__ 가림 때문에 안 돈다"""
    p = os.path.join(SKILL, "scripts", script)
    if not os.path.exists(p):
        return None, f"{script} 이(가) 없습니다"
    r = subprocess.run([sys.executable, p, *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def arg(name, dflt=None):
    i = sys.argv.index(name) if name in sys.argv else -1
    return sys.argv[i + 1] if 0 <= i < len(sys.argv) - 1 else dflt


def main():
    src = next((a for a in sys.argv[1:] if a.lower().endswith(".md")), None)
    if not src:
        sys.exit("원고(.md)를 주십시오")
    if not os.path.isabs(src):
        src = os.path.join(ROOT, src)
    if not os.path.exists(src):
        sys.exit(f"원고가 없습니다 — {src}")

    kind = next((k for k in TEMPLATES if k in os.path.basename(src)), None)
    if not kind:
        sys.exit("어느 양식을 쓸지 알 수 없습니다 — 원고 이름에 "
                 + " 또는 ".join(TEMPLATES) + " 가 들어가야 합니다")
    tpl = TEMPLATES[kind]
    if not os.path.exists(tpl):
        sys.exit(f"양식이 없습니다 — {tpl}")

    slots, tables = read_md(src)
    title = slots[0] if slots else os.path.splitext(os.path.basename(src))[0]
    out_dir = arg("--out", os.path.join(ROOT, "출력"))
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, title + ".hwpx")

    print(f"양식 : {os.path.relpath(tpl, BASE)}")
    print(f"원고 : {os.path.relpath(src, BASE)}  ({len(slots)}자리)")

    # 임시 자리에서 만들고, 검증을 마친 뒤에 옮긴다
    work = tempfile.mkdtemp(prefix="formdoc_")
    try:
        tmp = os.path.join(work, "out.hwpx")
        n, changed, dropped, kept, freed = fill(tpl, tmp, slots, tables)
        print(f"치환 : {n}자리 가운데 {changed}자리를 갈았습니다"
              f" · 빈 불릿 {dropped}개 걷어 냄"
              f" · 제목 {kept}종을 다음 문단과 묶음"
              f" · 긴 표 {freed}개를 쪼갤 수 있게 풀었습니다")

        code, log = run("fix_namespaces.py", tmp)
        print(f"이름공간 : {'손질함' if code == 0 else '건너뜀'}"
              + (f" ({log.splitlines()[-1][:60]})" if log else ""))

        code, log = run("validate_hwpx_package.py", tmp)
        print(f"꾸러미 검증 : {'통과' if code == 0 else '실패'}")
        if code not in (0, None):
            print(log[:1200])
            sys.exit("꾸러미 검증에 걸렸습니다 — 옮기지 않았습니다")

        shutil.move(tmp, dst)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print(f"\n만들었습니다 — {dst}  ({os.path.getsize(dst) // 1024}KB)")

    if "--pdf" in sys.argv:
        ps1 = os.path.join(SKILL, "scripts", "render_hwpx_to_pdf.ps1")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-File", ps1, "-Paths", dst,
                            "-OutputDirectory", out_dir],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        print("한/글 열기ㆍPDF : " + ((r.stdout or r.stderr or "").strip()[-400:]))


if __name__ == "__main__":
    main()
