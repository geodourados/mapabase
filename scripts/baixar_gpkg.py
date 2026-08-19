"""
Baixa o GeoPackage público (Mapa_GeoDourados.gpkg) do Google Drive.
Independente do plugin QGIS — usado pela rotina automática (GitHub Actions).
"""
import http.cookiejar
import os
import re
import sys
import urllib.error
import urllib.request

from config import GDRIVE_FILE_ID, GPKG_LOCAL_PATH

URL_DIRECT = f"https://drive.usercontent.google.com/download?id={GDRIVE_FILE_ID}&export=download&authuser=0"
URL_CONFIRM = f"https://drive.usercontent.google.com/download?id={GDRIVE_FILE_ID}&export=download&authuser=0&confirm=t"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def baixar(dest_path):
    tmp_path = dest_path + ".tmp"
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    req1 = urllib.request.Request(URL_DIRECT, headers=HEADERS)
    with opener.open(req1, timeout=30) as r1:
        content_type = r1.headers.get("Content-Type", "")
        first_bytes = r1.read(4096)

    is_html = (
        b"<!DOCTYPE" in first_bytes or b"<html" in first_bytes
        or b"confirm" in first_bytes or "text/html" in content_type
    )

    if is_html:
        token_match = re.search(rb"confirm=([0-9A-Za-t_\-]+)", first_bytes)
        if token_match:
            token = token_match.group(1).decode()
            url_final = (
                f"https://drive.usercontent.google.com/download"
                f"?id={GDRIVE_FILE_ID}&export=download&confirm={token}&authuser=0"
            )
        else:
            url_final = URL_CONFIRM
        req2 = urllib.request.Request(url_final, headers=HEADERS)
    else:
        req2 = urllib.request.Request(URL_DIRECT, headers=HEADERS)

    with opener.open(req2, timeout=300) as resp, open(tmp_path, "wb") as f:
        while True:
            chunk = resp.read(262144)
            if not chunk:
                break
            f.write(chunk)

    size = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
    if size < 1_000_000:
        os.remove(tmp_path)
        raise RuntimeError(f"Arquivo baixado inválido ({size} bytes).")

    if os.path.exists(dest_path):
        os.remove(dest_path)
    os.rename(tmp_path, dest_path)
    return dest_path


if __name__ == "__main__":
    try:
        caminho = baixar(GPKG_LOCAL_PATH)
        print(f"OK: GPKG salvo em {caminho} ({os.path.getsize(caminho) / 1_048_576:.1f} MB)")
    except (urllib.error.URLError, RuntimeError) as e:
        print(f"ERRO: {e}", file=sys.stderr)
        sys.exit(1)
