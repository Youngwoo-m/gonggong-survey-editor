# -*- coding: utf-8 -*-
"""
공공측량 규정 개정 편집기 — 로컬 실행용 정적 서버

파이썬 기본 http.server 는 파일을 캐시하도록 응답해, 프로그램을 고쳐도
브라우저가 옛 화면을 계속 보여주는 일이 생긴다. 이 서버는 캐시를 끈다.

■ AI 도우미 —— Claude Code CLI 로 부른다

  화면의 AI 도우미는 API 키 없이 이 컴퓨터의 `claude` 명령(Claude Code CLI)
  으로 부른다. 쓰는 계정은 CLI 에 로그인한 계정이다.

    GET  /api/claude     CLI 가 있는지, 로그인했는지
    POST /api/claude     {system, user, model} → {text}

  ㆍ 빈 임시 폴더에서 도구를 모두 끄고(--tools "") 한 번만 묻는다. 세션을
    남기지 아니하고(--no-session-persistence) MCP 도 부르지 아니한다.
  ㆍ ANTHROPIC_* ㆍ CLAUDE* 환경변수는 지우고 부른다. API 키가 환경에 있어도
    그것을 쓰지 아니하고 CLI 로그인을 쓰게 하려는 것이다.
  ㆍ 다른 웹페이지가 이 주소로 몰래 묻지 못하게, 같은 주소에서 온 JSON 요청만
    받는다(Origin 이 이 서버와 같아야 함).
"""
import http.server
import json
import re
import shutil
import socketserver
import subprocess
import tempfile
import time
import os
import sys
import webbrowser

_nums = [a for a in sys.argv[1:] if a.isdigit()]
PORT = int(_nums[0]) if _nums else int(os.environ.get("PORT") or 8765)
NO_BROWSER = "--no-browser" in sys.argv       # 미리보기처럼 남이 띄울 때는 창을 열지 아니함
# 편집기는 한 벌이다. 개정 대상 규정(3종)은 화면 안 트리 최상위에 나란히 선다
# (data/targets.json). 예전에는 review/ · uav/ 로 화면이 갈라져 있었다.
PAGE = ""
ROOT = os.path.dirname(os.path.abspath(__file__))
TITLE = "공공측량 규정 개정 편집기"


CLAUDE = shutil.which("claude")
MODEL_OK = re.compile(r"^[A-Za-z0-9.\-\[\]]{1,60}$")
ASK_TIMEOUT = 600          # 큰 규정을 Opus 로 물으면 몇 분 걸린다
_status = {"at": 0, "val": None}


def clean_env():
    """API 키나 다른 세션의 접속 정보를 지운 환경 —— CLI 로그인을 쓰게 한다"""
    return {k: v for k, v in os.environ.items()
            if not (k.startswith("ANTHROPIC_") or k.startswith("CLAUDE"))}


def cli_status():
    """CLI 가 있는지, 로그인했는지 —— 1분 동안 기억한다"""
    if _status["val"] and time.time() - _status["at"] < 60:
        return _status["val"]
    if not CLAUDE:
        val = {"ok": False, "error": "claude 명령을 찾지 못했습니다. Claude Code 를 설치하십시오."}
    else:
        try:
            r = subprocess.run([CLAUDE, "auth", "status"], capture_output=True, timeout=60,
                               env=clean_env(), cwd=tempfile.gettempdir())
            st = json.loads(r.stdout.decode("utf-8", "replace") or "{}")
            if st.get("loggedIn"):
                val = {"ok": True, "email": st.get("email") or "", "method": st.get("authMethod") or ""}
            else:
                val = {"ok": False, "error": "Claude Code CLI 에 로그인되어 있지 않습니다. 터미널에서 claude auth login 을 실행하십시오."}
        except Exception as e:                      # noqa: BLE001
            val = {"ok": False, "error": "claude auth status 를 읽지 못했습니다: %s" % e}
    _status.update(at=time.time(), val=val)
    return val


def cli_ask(system, user, model):
    """claude -p 로 한 번 묻고 답 글을 돌려준다"""
    if not CLAUDE:
        raise RuntimeError("claude 명령을 찾지 못했습니다. Claude Code 를 설치하십시오.")
    with tempfile.TemporaryDirectory(prefix="pm-ai-") as wd:
        sp = os.path.join(wd, "system.txt")
        with open(sp, "w", encoding="utf-8") as f:
            f.write(system or "")
        args = [CLAUDE, "-p", "--output-format", "json", "--system-prompt-file", sp,
                "--tools", "", "--no-session-persistence", "--strict-mcp-config"]
        if model:
            args += ["--model", model]
        try:
            r = subprocess.run(args, input=(user or "").encode("utf-8"), capture_output=True,
                               timeout=ASK_TIMEOUT, env=clean_env(), cwd=wd)
        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude 가 %d초 안에 답하지 아니했습니다." % ASK_TIMEOUT)
    out = r.stdout.decode("utf-8", "replace").strip()
    try:
        d = json.loads(out)
    except ValueError:
        err = (r.stderr.decode("utf-8", "replace") or out).strip()
        raise RuntimeError("claude 가 알 수 없는 답을 냈습니다: %s" % err[:300])
    text = str(d.get("result") or "")
    if d.get("is_error"):
        _status["val"] = None                       # 로그인 상태를 다시 읽게 함
        if "401" in text or "authenticate" in text.lower():
            raise RuntimeError("Claude Code CLI 로그인이 만료되었습니다. 터미널에서 claude auth login 을 실행한 뒤 다시 시도하십시오.")
        raise RuntimeError("Claude 오류: %s" % text[:300])
    return text.strip()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    # ── /api/claude ────────────────────────────────────────────
    def _json(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _same_origin(self):
        """같은 주소의 화면에서 온 요청만 받는다"""
        origin = self.headers.get("Origin")
        host = self.headers.get("Host") or ""
        # 남의 이름을 이 컴퓨터로 돌려 대는 수(DNS rebinding)를 막으려 주소 이름도 본다
        if host.split(":")[0] not in ("127.0.0.1", "localhost", "[::1]"):
            return False
        return origin in (None, "http://" + host)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/claude":
            if not self._same_origin():
                return self._json(403, {"ok": False, "error": "다른 주소에서 온 요청은 받지 아니합니다."})
            return self._json(200, cli_status())
        return super().do_GET()

    def do_POST(self):
        if self.path.split("?")[0] != "/api/claude":
            return self._json(404, {"error": "없는 주소입니다."})
        if not self._same_origin() or "application/json" not in (self.headers.get("Content-Type") or ""):
            return self._json(403, {"error": "다른 주소에서 온 요청은 받지 아니합니다."})
        try:
            n = int(self.headers.get("Content-Length") or 0)
            q = json.loads(self.rfile.read(n).decode("utf-8"))
            model = str(q.get("model") or "")
            if model and not MODEL_OK.match(model):
                return self._json(400, {"error": "모델 이름이 올바르지 않습니다."})
            text = cli_ask(str(q.get("system") or ""), str(q.get("user") or ""), model)
            return self._json(200, {"text": text})
        except Exception as e:                      # noqa: BLE001
            return self._json(502, {"error": str(e)})

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        if "404" in (fmt % args):
            sys.stderr.write("  [없음] %s\n" % (fmt % args))


Handler.extensions_map.update({
    ".mjs": "text/javascript",
    ".js": "text/javascript",
    ".json": "application/json",
})


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    url = "http://127.0.0.1:%d/%s" % (PORT, PAGE)
    print()
    print("  " + TITLE)
    print("  " + "-" * 44)
    print("  주소 : %s" % url)
    print("  폴더 : %s" % ROOT)
    print("  종료 : 이 창을 닫거나 Ctrl+C")
    print()
    try:
        if not NO_BROWSER:
            webbrowser.open(url)
    except Exception:
        pass
    try:
        with Server(("127.0.0.1", PORT), Handler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  종료했습니다.")
    except OSError as e:
        print("\n  [오류] 포트 %d 를 열지 못했습니다: %s" % (PORT, e))
        print("  다른 포트로 실행하려면 :  python serve.py 8766")
        input("\n  Enter 를 누르면 닫힙니다.")
