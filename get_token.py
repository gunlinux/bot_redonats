import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

from donats import settings

SCOPE = 'oauth-user-show oauth-donation-subscribe'

TOKEN: dict = {}


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        if 'access_token' in query:
            TOKEN.update(query)
            body = b'<h1>OK, you can close this tab</h1>'
            threading.Thread(target=self.server.shutdown).start()
        else:
            # implicit flow puts the token in the URL fragment, which is never
            # sent to the server — forward it via a query string redirect
            body = (
                b"<script>"
                b"const p = new URLSearchParams(location.hash.slice(1));"
                b"location.href = '/?' + p.toString();"
                b"</script>"
            )
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # keep the console clean
        pass


def main() -> None:
    redirect = settings.DA_REDIRECT_URI
    host = urlparse(redirect).hostname or '127.0.0.1'
    port = urlparse(redirect).port or 8080

    server = HTTPServer((host, port), CallbackHandler)
    authorize_url = (
        'https://www.donationalerts.com/oauth/authorize?'
        + urlencode(
            {
                'client_id': settings.DA_CLIENT_ID,
                'redirect_uri': redirect,
                'response_type': 'token',
                'scope': SCOPE,
            }
        )
    )
    print(f'Open in browser and authorize:\n{authorize_url}\n')
    print(f'Waiting for the redirect to {redirect} ...')
    webbrowser.open(authorize_url)

    server.serve_forever()
    server.server_close()

    token = TOKEN['access_token'][0]
    expires_at = ''
    if TOKEN.get('expires_in'):
        expires_at = int(time.time()) + int(TOKEN['expires_in'][0])

    print('\nAdd these lines to .env (production):')
    print(f'DA_ACCESS_TOKEN={token}')
    if expires_at:
        print(f'DA_TOKEN_EXPIRES_AT={expires_at}')


if __name__ == '__main__':
    main()
