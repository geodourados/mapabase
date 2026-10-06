"""
Lógica de sincronização com a base pública do GitHub
(github.com/geodourados/mapabase). Substitui o antigo downloader.py, que
baixava do Google Drive — a distribuição oficial agora é via GitHub.
"""
import glob
import json
import os
import re
import urllib.error
import urllib.request

GPKG_FILENAME = "Mapa_GeoDourados.gpkg"
PROJETO_NOME = "GeoDourados-Offline"
PASTA_MEUS_PROJETOS = "MeusProjetos"
DEFAULT_DIR = r"C:\GeoDourados-Offline"

URL_GPKG = "https://github.com/geodourados/mapabase/releases/download/latest/Mapa_GeoDourados.gpkg"
URL_API_RELEASE = "https://api.github.com/repos/geodourados/mapabase/releases/tags/latest"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GeoDouradosPlugin/2.0"}


def get_local_paths(install_dir=None):
    d = install_dir or DEFAULT_DIR
    return {
        "dir": d,
        "gpkg": os.path.join(d, GPKG_FILENAME),
        "meus_projetos_dir": os.path.join(d, PASTA_MEUS_PROJETOS),
    }


def slug_nome_projeto(nome):
    """Nome digitado pelo usuário -> nome de arquivo seguro."""
    nome = nome.strip()
    nome = re.sub(r'[\\/:*?"<>|]', "", nome)  # caracteres inválidos em nome de arquivo no Windows
    return nome[:80]  # limite razoável


def listar_meus_projetos(install_dir=None):
    """Nomes (sem extensão) dos projetos personalizados salvos, mais recente primeiro."""
    paths = get_local_paths(install_dir)
    pasta = paths["meus_projetos_dir"]
    if not os.path.exists(pasta):
        return []
    arquivos = [f for f in os.listdir(pasta) if f.lower().endswith(".qgz")]
    arquivos.sort(key=lambda f: os.path.getmtime(os.path.join(pasta, f)), reverse=True)
    return [os.path.splitext(f)[0] for f in arquivos]


def caminho_meu_projeto(nome, install_dir=None):
    paths = get_local_paths(install_dir)
    return os.path.join(paths["meus_projetos_dir"], f"{slug_nome_projeto(nome)}.qgz")


def _arquivo_versao(gpkg_path):
    return gpkg_path + ".versao.json"


def _http_date_para_iso(texto):
    from email.utils import parsedate_to_datetime
    return parsedate_to_datetime(texto).strftime("%Y-%m-%dT%H:%M:%SZ")


def obter_info_remota():
    """(atualizado_em ISO-8601 UTC, tamanho) do GPKG na Release, sem baixar.
    O tamanho sozinho NAO serve: o GPKG tem paginas de tamanho fixo e
    versoes diferentes costumam ter exatamente os mesmos bytes.
    Fonte principal: HEAD no proprio arquivo (Last-Modified) — sem limite de
    consultas. A API do GitHub so e usada de reserva: ela limita 60
    consultas/hora por IP, e numa rede com varios computadores atras do
    mesmo IP estoura e a checagem falharia sem aviso."""
    try:
        req = urllib.request.Request(URL_GPKG, headers=HEADERS, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as r:
            lm = r.headers.get("Last-Modified")
            if lm:
                cl = r.headers.get("Content-Length")
                return _http_date_para_iso(lm), int(cl) if cl else None
    except Exception:
        pass
    try:
        req = urllib.request.Request(URL_API_RELEASE, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            dados = json.load(r)
        for a in dados.get("assets", []):
            if a.get("name") == GPKG_FILENAME:
                return a.get("updated_at"), a.get("size")
    except Exception:
        pass
    return None


def _versao_local(gpkg_path):
    """Data (ISO-8601 UTC) do asset remoto que gerou este arquivo local;
    sem registro (instalação antiga), usa a data de modificação do arquivo."""
    from datetime import datetime, timezone
    try:
        with open(_arquivo_versao(gpkg_path), encoding="utf-8") as f:
            return json.load(f)["atualizado_em"]
    except Exception:
        mtime = os.path.getmtime(gpkg_path)
        return datetime.fromtimestamp(mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _registrar_versao(gpkg_path, atualizado_em):
    try:
        with open(_arquivo_versao(gpkg_path), "w", encoding="utf-8") as f:
            json.dump({"atualizado_em": atualizado_em}, f)
    except Exception:
        pass


def verificar_atualizacao_disponivel(install_dir=None):
    """Retorna (tem_atualizacao: bool, mensagem: str)."""
    paths = get_local_paths(install_dir)
    if not os.path.exists(paths["gpkg"]):
        return True, "Base não instalada nesta pasta."

    remoto = obter_info_remota()
    if remoto is None or not remoto[0]:
        return False, "Não foi possível checar (sem conexão?)."

    local = _versao_local(paths["gpkg"])
    # Tolerancia: Last-Modified e updated_at (API) diferem em alguns segundos.
    from datetime import datetime
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    if (datetime.strptime(remoto[0], fmt) - datetime.strptime(local, fmt)).total_seconds() > 120:
        return True, f"Nova versão disponível (publicada em {remoto[0][:10]})."
    return False, "Atualizado."


def baixar_gpkg(dest_path, progress_callback=None):
    tmp_path = dest_path + ".tmp"
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    info_remota = obter_info_remota()  # antes do download: se publicar no meio, ficará "desatualizado" e baixa de novo

    try:
        if progress_callback:
            progress_callback(3, "Conectando ao GitHub...")

        req = urllib.request.Request(URL_GPKG, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 262144

            with open(tmp_path, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        mb_d = downloaded / 1_048_576
                        if total > 0:
                            pct = 5 + int((downloaded / total) * 90)
                            mb_t = total / 1_048_576
                            progress_callback(min(pct, 95), f"Baixando... {mb_d:.1f} / {mb_t:.0f} MB")
                        else:
                            progress_callback(50, f"Baixando... {mb_d:.1f} MB")

        size = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
        if size < 1_000_000:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return False, f"Arquivo baixado inválido ({size} bytes)."

        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(tmp_path, dest_path)
        if info_remota and info_remota[0]:
            _registrar_versao(dest_path, info_remota[0])
        return True, ""

    except urllib.error.HTTPError as e:
        _rm(tmp_path)
        return False, f"Erro HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        _rm(tmp_path)
        return False, f"Sem conexão com a internet: {e.reason}"
    except Exception as e:
        _rm(tmp_path)
        return False, str(e)


def _rm(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def detectar_qgis_exe():
    """Localiza o executável do QGIS (instalador standalone ou OSGeo4W)."""
    base = r"C:\Program Files"
    pattern = os.path.join(base, "QGIS*", "bin", "qgis-bin.exe")
    encontrados = sorted(glob.glob(pattern), reverse=True)
    if encontrados:
        return encontrados[0]

    for raiz in (r"C:\OSGeo4W", r"C:\OSGeo4W64"):
        for nome in ("qgis-bin.exe", "qgis-ltr-bin.exe"):
            p = os.path.join(raiz, "bin", nome)
            if os.path.exists(p):
                return p

    return None
