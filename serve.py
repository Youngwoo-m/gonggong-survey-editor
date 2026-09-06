# -*- coding: utf-8 -*-
"""
공공측량 규정 개정 편집기 — 로컬 실행용 정적 서버

파이썬 기본 http.server 는 파일을 캐시하도록 응답해, 프로그램을 고쳐도
브라우저가 옛 화면을 계속 보여주는 일이 생긴다. 이 서버는 캐시를 끈다.
"""
import http.server
import socketserver
import os
import sys
import webbrowser

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
# 편집기는 한 벌이다. 개정 대상 규정(3종)은 화면 안 트리 최상위에 나란히 선다
# (data/targets.json). 예전에는 review/ · uav/ 로 화면이 갈라져 있었다.
PAGE = ""
ROOT = os.path.dirname(os.path.abspath(__file__))
TITLE = "공공측량 규정 개정 편집기"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

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
