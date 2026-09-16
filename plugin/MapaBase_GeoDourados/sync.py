"""
Lógica de sincronização com a base pública do GitHub
(github.com/geodourados/mapabase). Substitui o antigo downloader.py, que
baixava do Google Drive — a distribuição oficial agora é via GitHub.
"""
import glob
import os
import re
import urllib.error
import urllib.request

GPKG_FILENAME = "Mapa_GeoDourados.gpkg"
PROJETO_NOME = "GeoDourados-Offline"
PASTA_MEUS_PROJETOS = "MeusProjetos"
DEFAULT_DIR = r"C:\GeoDourados-Offline"

URL_GPKG = "https://github.com/geodourados/mapabase/releases/download/latest/Mapa_GeoDourados.gpkg"

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


def obter_tamanho_remoto():
    """Tamanho do GPKG publicado — via HEAD, não baixa nada."""
    try:
        req = urllib.request.Request(URL_GPKG, headers=HEADERS, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as r:
            cl = r.headers.get("Content-Length")
            if cl:
                return int(cl)
    except Exception:
        pass
    return None


def verificar_atualizacao_disponivel(install_dir=None):
    """Retorna (tem_atualizacao: bool, mensagem: str)."""
    paths = get_local_paths(install_dir)
    if not os.path.exists(paths["gpkg"]):
        return True, "Base não instalada nesta pasta."

    local_size = os.path.getsize(paths["gpkg"])
    remoto_size = obter_tamanho_remoto()

    if remoto_size is None:
        return False, "Não foi possível checar (sem conexão?)."

    if abs(remoto_size - local_size) > 1024:
        diff_mb = abs(remoto_size - local_size) / 1_048_576
        return True, (
            f"Nova versão disponível "
            f"(local: {local_size/1_048_576:.0f} MB | remoto: {remoto_size/1_048_576:.0f} MB)"
        )

    return False, "Atualizado."


def baixar_gpkg(dest_path, progress_callback=None):
    tmp_path = dest_path + ".tmp"
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

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
