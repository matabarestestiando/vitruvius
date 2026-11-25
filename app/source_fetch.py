"""Public HTTPS fetch with pinned DNS, bounded redirects, no cookies, credentials or scripts."""

from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin
import ipaddress, socket, ssl, http.client, tempfile
from pathlib import Path


class SourceAccessError(ValueError):
    pass


def url_parts(url):
    p = urlsplit(url)
    if (
        p.scheme != "https"
        or not p.hostname
        or p.username
        or p.password
        or p.port not in (None, 443)
    ):
        raise SourceAccessError(
            "Use una URL HTTPS pública sin credenciales ni puertos especiales"
        )
    return p


def public_address(host):
    addresses = list(
        dict.fromkeys(
            r[4][0] for r in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        )
    )
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise SourceAccessError(
            "Las direcciones privadas, locales y de metadatos no están permitidas"
        )
    return addresses[0]


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, timeout=30)
        self.address = address

    def connect(self):
        self.sock = self._context.wrap_socket(
            socket.create_connection((self.address, 443), self.timeout),
            server_hostname=self.host,
        )


class ArticleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.article = 0
        self.body = []
        self.preferred = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header", "form", "noscript"):
            self.skip += 1
        if tag in ("article", "main"):
            self.article += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header", "form", "noscript"):
            self.skip = max(0, self.skip - 1)
        if tag in ("article", "main"):
            self.article = max(0, self.article - 1)

    def handle_data(self, data):
        text = " ".join(data.split())
        if not self.skip and text:
            self.body.append(text)
            if self.article:
                self.preferred.append(text)

    def text(self):
        return "\n".join(self.preferred or self.body)


def fetch_public(url):
    current = url
    for _ in range(4):
        p = url_parts(current)
        host = p.hostname.encode("idna").decode()
        address = public_address(host)
        conn = PinnedHTTPS(host, address)
        try:
            path = p.path or "/"
            if p.query:
                path += "?" + p.query
            conn.request(
                "GET",
                path,
                headers={
                    "Host": host,
                    "User-Agent": "Vitruvius/0.1 owner-requested-source-import",
                    "Accept": "text/html,application/pdf,text/plain",
                },
            )
            response = conn.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                target = response.getheader("Location")
                if not target:
                    raise SourceAccessError("Redirección sin destino")
                current = urljoin(current, target)
                continue
            if response.status != 200:
                raise SourceAccessError(
                    "La fuente no permite recuperar el contenido públicamente"
                )
            content_type = (
                response.getheader("Content-Type", "").split(";")[0].strip().lower()
            )
            if content_type not in (
                "text/html",
                "application/xhtml+xml",
                "application/pdf",
                "text/plain",
                "text/markdown",
            ):
                raise SourceAccessError(
                    "El enlace no devuelve un artículo, texto o PDF compatible"
                )
            # Bounded network import; this is separate from owner file uploads.
            with tempfile.SpooledTemporaryFile(max_size=1024 * 1024) as stream:
                size = 0
                while block := response.read(65536):
                    size += len(block)
                    if size > 64 * 1024 * 1024:
                        raise SourceAccessError(
                            "El recurso remoto requiere carga directa de archivo"
                        )
                    stream.write(block)
                stream.seek(0)
                content = stream.read()
            if content_type == "application/pdf":
                return current, content_type, content
            text = content.decode("utf-8", errors="replace")
            if content_type in ("text/html", "application/xhtml+xml"):
                parser = ArticleText()
                parser.feed(text)
                text = parser.text()
            if len(text.strip()) < 100 or any(
                marker in text.lower()
                for marker in (
                    "enable javascript and cookies to continue",
                    "checking your browser",
                    "just a moment...",
                )
            ):
                raise SourceAccessError(
                    "No se obtuvo el artículo completo; aporte el texto autorizado o un PDF"
                )
            if len(text) > 200000:
                raise SourceAccessError(
                    "El artículo requiere carga directa para conservar su contenido completo"
                )
            return current, "text/plain", text.encode("utf-8")
        finally:
            conn.close()
    raise SourceAccessError("Demasiadas redirecciones")
