# -*- coding: utf-8 -*-
r"""HWPX 양식 얹기 — 양식 파일의 서식을 그대로 두고 글만 갈아 끼운다.

■ 왜 이렇게 하는가

  여태는 HTML 을 지어 한/글에게 넘겨 HWPX 로 저장하게 했다. 그러면 글꼴ㆍ쪽
  설정ㆍ표 테두리ㆍ칸 폭이 모두 한/글이 HTML 을 보고 짐작한 것이 된다. 양식과
  '비슷한' 문서일 뿐 양식 그대로는 아니다.

  이것은 Form 폴더의 양식 파일을 열어, 그 안의 문단과 표 칸을 **본으로 삼아**
  복제하며 글을 채운다. 문단모양ㆍ글자모양ㆍ테두리ㆍ칸 폭이 한 치도 어긋나지
  않는다.

■ 개정사유서와 무엇이 다른가

  개정사유서는 자리 수가 고정이라(187자리) 자리마다 글만 갈아 끼우면 되었다
  (Report\scripts\build_from_form.py).

  개정(안)과 신구대조표는 규정마다 조 수와 행 수가 다르다. 그래서 자리를 갈아
  끼우는 것으로는 모자라고, 본을 몇 번이든 **복제**해야 한다. 이 파일이 그
  복제를 맡는다.

■ 손댈 때 조심할 것

  ㆍ XML 을 다시 쓰지 아니한다 — 이름공간 접두사가 바뀌면 한/글이 거부한다.
    문자열을 자르고 붙이는 것으로만 다룬다.
  ㆍ <hp:linesegarray>(줄 배치 캐시)는 모두 걷어 낸다. 두면 한/글이 옛 줄
    자리를 그대로 믿어 글이 겹쳐 찍히거나 표가 통째로 밀린다.
  ㆍ 첫 문단에는 <hp:secPr>(쪽 설정)가 들어 있다. 지우면 안 된다.
  ㆍ mimetype 은 꾸러미의 맨 앞에 무압축으로 두어야 한다.
"""
import io
import os
import re
import subprocess
import sys
import zipfile

RE_T = re.compile(r"<hp:t(?:\s[^>]*)?>(.*?)</hp:t>", re.S)
RE_SEG = re.compile(r"<hp:linesegarray>.*?</hp:linesegarray>"
                    r"|<hp:linesegarray\s*/>", re.S)
# 뒤처리ㆍ검증 스크립트가 있는 자리. 이 컴퓨터에서는 hwpx 스킬 폴더지만,
# 웹에서 받은 꾸러미 안에서 돌 때에는 꾸러미가 제 안의 자리를 알려 준다
# (HWPX_SKILL 환경변수). 그래야 스킬이 깔리지 않은 PC 에서도 돈다.
SKILL = os.environ.get("HWPX_SKILL") or os.path.join(
    os.path.expanduser("~"), ".claude", "skills", "hwpx")


def esc(s):
    """글 안에 넣을 것. 큰따옴표는 건드리지 아니한다."""
    return (str(s or "").replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def unesc(s):
    return (s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))


def strip_seg(x):
    return RE_SEG.sub("", x)


def text_of(block):
    return unesc("".join(m.group(1) for m in RE_T.finditer(block)))


# ────────────────────────────────── 양식 파일
class Form:
    """양식 하나를 통째로 들고 있다가, 다 채운 뒤 한꺼번에 쓴다"""

    def __init__(self, path):
        self.path = path
        with zipfile.ZipFile(path) as z:
            self.names = z.namelist()
            self.blobs = {n: z.read(n) for n in self.names}
        self.sec = next(n for n in self.names
                        if re.match(r"Contents/section\d+\.xml$", n))
        self.xml = self.blobs[self.sec].decode("utf-8")
        self.hname = next((n for n in self.names
                           if n.endswith("Contents/header.xml")), None)
        self.hdr = self.blobs[self.hname].decode("utf-8") if self.hname else ""

    # ── 문단 훑기
    def paras(self, xml=None):
        """[(시작, 끝, 문단모양, 글자모양, 글, 통째)] — 표를 담은 문단도 낸다.

        표를 담은 문단은 안에 또 <hp:p> 가 있으므로 nested=True 로 알린다."""
        x = self.xml if xml is None else xml
        out = []
        for m in re.finditer(r"<hp:p\s[^>]*>", x):
            e = x.find("</hp:p>", m.end())
            if e < 0:
                continue
            span = x[m.end():e]
            nested = "<hp:p " in span
            if nested:                       # 표를 담은 문단은 끝을 다시 찾는다
                e = _match_close(x, m.end(), "<hp:p ", "</hp:p>")
                span = x[m.end():e]
            pid = re.search(r'paraPrIDRef="(\d+)"', m.group(0))
            cid = re.search(r'charPrIDRef="(\d+)"', span)
            out.append((m.start(), e + len("</hp:p>"),
                        pid.group(1) if pid else "",
                        cid.group(1) if cid else "",
                        text_of(span).strip(),
                        x[m.start():e + len("</hp:p>")], nested))
        return out

    def find_para(self, pred, xml=None):
        """조건에 맞는 첫 문단을 본으로 내준다"""
        for p in self.paras(xml):
            if pred(p):
                return p
        return None

    # ── 글자모양 새로 만들기
    def new_charpr(self, src_id, **attrs):
        """있는 글자모양을 본떠 새것을 만든다 → 새 id

        붉은 글씨가 필요한데 양식에 꼭 맞는 것이 없을 때 쓴다. 본이 되는
        글자모양을 그대로 베끼므로 글꼴과 크기가 본문과 같아진다."""
        m = re.search(r'<hh:charPr\b[^>]*\bid="%s"[^>]*>' % src_id, self.hdr)
        if not m:
            raise KeyError("글자모양 %s 가 없습니다" % src_id)
        e = self.hdr.find("</hh:charPr>", m.end()) + len("</hh:charPr>")
        blk = self.hdr[m.start():e]
        ids = [int(i) for i in re.findall(r'<hh:charPr\b[^>]*\bid="(\d+)"', self.hdr)]
        new = str(max(ids) + 1)
        blk = re.sub(r'(\bid=")\d+(")', r"\g<1>" + new + r"\g<2>", blk, count=1)
        for k, v in attrs.items():
            if re.search(r'\b%s="[^"]*"' % k, blk[:blk.find(">")]):
                blk = re.sub(r'(\b%s=")[^"]*(")' % k, r"\g<1>" + v + r"\g<2>",
                             blk, count=1)
            else:                            # 없던 속성이면 여는 태그에 붙인다
                i = blk.find(">")
                blk = blk[:i] + ' %s="%s"' % (k, v) + blk[i:]
        i = self.hdr.rfind("</hh:charProperties>")
        self.hdr = self.hdr[:i] + blk + self.hdr[i:]
        self.hdr = re.sub(r'(<hh:charProperties itemCnt=")(\d+)(")',
                          lambda m2: m2.group(1) + str(int(m2.group(2)) + 1)
                          + m2.group(3), self.hdr, count=1)
        return new

    # ── 쓰기
    def renumber(self):
        """문단 id 를 하나씩 새로 매긴다 — 본을 복제하면 id 가 겹친다.

        양식 자체도 id 가 겹치는 채로 한/글에서 잘 열리지만, 꾸러미 검증이
        겹침을 짚으므로 깨끗하게 매겨 둔다."""
        n = [0]

        def one(m):
            n[0] += 1
            return m.group(1) + str(n[0]) + m.group(3)

        self.xml = re.sub(r'(<hp:p id=")(\d+)(")', one, self.xml)
        return n[0]

    def save(self, dst, fix_ns=True):
        self.renumber()
        self.blobs[self.sec] = strip_seg(self.xml).encode("utf-8")
        if self.hname:
            self.blobs[self.hname] = self.hdr.encode("utf-8")
        for n in self.names:                 # 탐색기 미리보기도 새 글로
            if n.lower().endswith("prvtext.txt"):
                head = [t for _s, _e, _p, _c, t, _b, _n in self.paras()[:40] if t]
                self.blobs[n] = "\n".join(head).encode("utf-8")
        tmp = dst + ".tmp"
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as o:
            for n in self.names:
                o.writestr(n, self.blobs[n],
                           zipfile.ZIP_STORED if n == "mimetype"
                           else zipfile.ZIP_DEFLATED)
        if os.path.exists(dst):
            os.remove(dst)
        os.rename(tmp, dst)
        if fix_ns:
            p = os.path.join(SKILL, "scripts", "fix_namespaces.py")
            if os.path.exists(p):
                subprocess.run([sys.executable, p, dst],
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        return dst

    def validate(self):
        p = os.path.join(SKILL, "scripts", "validate_hwpx_package.py")
        if not os.path.exists(p):
            return None, "검증 스크립트가 없습니다"
        r = subprocess.run([sys.executable, p, self.path],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "") + (r.stderr or "")


def _match_close(x, pos, open_tag, close_tag):
    """pos 부터 훑어 짝이 맞는 닫는 태그 자리를 찾는다 (문단 속 문단 때문)"""
    depth, i = 0, pos
    while True:
        a = x.find(open_tag, i)
        b = x.find(close_tag, i)
        if b < 0:
            return len(x)
        if 0 <= a < b:
            depth += 1
            i = a + len(open_tag)
            continue
        if depth == 0:
            return b
        depth -= 1
        i = b + len(close_tag)


# ────────────────────────────────── 본을 복제해 문단 만들기
def remake(proto, runs):
    """본 문단을 그대로 베끼되 글만 갈아 끼운다.

    runs 는 [(글자모양 id 또는 None, 글), …] 이다. None 이면 본의 글자모양을
    그대로 쓴다. 신구대조표에서 고친 데만 붉게 하려고 여럿을 받는다."""
    proto = strip_seg(proto)
    i = proto.find(">") + 1
    open_p = proto[:i]
    m = re.search(r"<hp:run\b[^>]*?/?>", proto)
    open_r = m.group(0) if m else '<hp:run charPrIDRef="0">'
    # 본의 run 이 자기닫힘(<hp:run …/>)일 때가 있다 — 빈 문단이 그렇다.
    # 그대로 뒤에 <hp:t> 를 붙이면 태그가 어긋나므로 먼저 편다.
    if open_r.endswith("/>"):
        open_r = open_r[:-2] + ">"
    body = []
    for cid, t in runs:
        r = (re.sub(r'charPrIDRef="\d+"', 'charPrIDRef="%s"' % cid, open_r)
             if cid else open_r)
        body.append(r + "<hp:t>" + esc(t) + "</hp:t></hp:run>")
    if not body:                             # 빈 문단은 글 없는 run 하나로
        body.append(open_r[:-1] + "/>")
    return open_p + "".join(body) + "</hp:p>"


def retext(proto, text):
    """본 문단의 글만 갈아 끼운다 — 딸린 것을 지켜야 할 때 쓴다.

    첫 문단에는 <hp:secPr>(쪽 설정)가 run 안에 들어 있다. remake 는 run 을 새로
    짓느라 그것을 버리므로, 첫 문단만은 이 함수로 글자만 바꾼다. 쪽 설정을 잃으면
    세로/가로와 여백이 한/글 기본값으로 돌아간다."""
    proto = strip_seg(proto)
    done = [False]

    def one(_m):
        if done[0]:
            return "<hp:t></hp:t>"
        done[0] = True
        return "<hp:t>" + esc(text) + "</hp:t>"

    return RE_T.sub(one, proto)


def lines_to_paras(proto, lines, mark=None):
    """줄 여럿 → 문단 여럿. mark 를 주면 (글자모양, 글) 짝으로 받는다"""
    out = []
    for ln in lines:
        if isinstance(ln, list):
            out.append(remake(proto, ln))
        else:
            out.append(remake(proto, [(mark, ln)]))
    return "".join(out) or remake(proto, [])


# ────────────────────────────────── 표 만들기
def top_rows(tbl_xml):
    """겉 표의 <hp:tr> 만 — 칸 안에 또 표가 있어도 속지 않는다.

    신구대조표 양식은 칸 안에 표를 담고 있다(시료 보존방법 표 따위). 그것을
    가리지 않고 정규식으로 훑으면 속 표의 행까지 섞이고, 닫는 태그도 속 표의
    것을 집어 XML 이 어긋난다."""
    i = tbl_xml.find("<hp:tr>")
    out = []
    while i >= 0:
        e = _match_close(tbl_xml, i + len("<hp:tr>"), "<hp:tr>", "</hp:tr>")
        out.append(tbl_xml[i:e + len("</hp:tr>")])
        i = tbl_xml.find("<hp:tr>", e + len("</hp:tr>"))
    return out


def top_cells(tr_xml):
    """한 행의 <hp:tc> 만 — 마찬가지로 겹친 표에 속지 않는다"""
    i = tr_xml.find("<hp:tc ")
    out = []
    while i >= 0:
        e = _match_close(tr_xml, i + len("<hp:tc "), "<hp:tc ", "</hp:tc>")
        out.append(tr_xml[i:e + len("</hp:tc>")])
        i = tr_xml.find("<hp:tc ", e + len("</hp:tc>"))
    return out


class RowProto:
    """양식의 한 행을 본으로 삼아 새 행을 찍어 낸다"""

    def __init__(self, tr_xml):
        self.tcs = top_cells(tr_xml)
        self.widths = [int(re.search(r'<hp:cellSz width="(\d+)"', tc).group(1))
                       for tc in self.tcs]

    def para_proto(self, col=0):
        tc = self.tcs[min(col, len(self.tcs) - 1)]
        m = re.search(r"<hp:p\s[^>]*>", tc)
        e = tc.find("</hp:p>", m.end())
        return tc[m.start():e + len("</hp:p>")]

    def make(self, row_no, cols):
        """cols 는 칸마다의 문단 XML 묶음 → <hp:tr> 한 줄"""
        out = ["<hp:tr>"]
        for i, body in enumerate(cols):
            tc = self.tcs[min(i, len(self.tcs) - 1)]
            head = tc[:tc.find(">") + 1]
            sl = re.search(r"<hp:subList\b[^>]*>", tc).group(0)
            addr = '<hp:cellAddr colAddr="%d" rowAddr="%d"/>' % (i, row_no)
            span = '<hp:cellSpan colSpan="1" rowSpan="1"/>'
            sz = '<hp:cellSz width="%d" height="2000"/>' % self.widths[
                min(i, len(self.widths) - 1)]
            mg = re.search(r"<hp:cellMargin\b[^>]*/>", tc)
            out.append(head + sl + body + "</hp:subList>" + addr + span + sz
                       + (mg.group(0) if mg else ""))
            out.append("</hp:tc>")
        out.append("</hp:tr>")
        return "".join(out)


def table_span(xml, n=0):
    """n 번째 겉 <hp:tbl> 의 (시작, 끝) — 칸 안의 표를 끝으로 착각하지 않는다"""
    i = -1
    for _ in range(n + 1):
        i = xml.find("<hp:tbl ", i + 1)
        if i < 0:
            return None
    e = _match_close(xml, i + len("<hp:tbl "), "<hp:tbl ", "</hp:tbl>")
    return i, e + len("</hp:tbl>")


def retable(tbl_xml, rows_xml, row_cnt, unchar_over=10):
    """표의 행을 통째로 갈아 끼우고 행 수를 고친다.

    행이 많으면 '글자처럼 취급'(treatAsChar)을 푼다.

    한/글은 글자처럼 취급하는 표를 쪽 경계에서 쪼개지 못한다. 남은 자리에
    들어가지 못하면 통째로 다음 쪽으로 밀리고, 한 쪽에도 못 들어갈 만큼
    길면 아예 보이지 아니한다 — 작업규정 개정사유서에서 4ㆍ5절 표가
    제목만 남고 통째로 사라졌다.

    표에는 이미 pageBreak="CELL"(셀 단위로 나눔)과 textWrap="TOP_AND_BOTTOM"
    (자리 차지)이 걸려 있으므로, 글자처럼 취급만 풀면 생김새는 그대로 두고
    쪼개지기만 한다."""
    head = tbl_xml[:tbl_xml.find("<hp:tr>")]
    head = re.sub(r'(\browCnt=")\d+(")', r"\g<1>" + str(row_cnt) + r"\g<2>", head)
    if row_cnt > unchar_over:
        head = head.replace('treatAsChar="1"', 'treatAsChar="0"')
    return head + rows_xml + "</hp:tbl>"
