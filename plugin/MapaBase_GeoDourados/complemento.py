"""Complemento IBGE e Rural: GeoPackage separado da base oficial (dados externos: IBGE, CAR, INCRA, FUNAI...).

Fica numa Release própria (tag `complemento`) e é baixado para <pasta da base>\\Complemento, junto com o .qlr
que monta os grupos e estilos no QGIS (o .qlr aponta para o .gpkg por caminho relativo).
"""
import json
import os
import urllib.error
import urllib.request

from .sync import HEADERS, DEFAULT_DIR, get_local_paths, _http_date_para_iso, _rm

BASE_URL = "https://github.com/geodourados/mapabase/releases/download/complemento/"
GPKG = "GeoDourados_IBGE_Rural.gpkg"
QLR = "GeoDourados_IBGE_Rural.qlr"
NOME_GRUPO = "Complemento – IBGE e Rural"


def pasta(install_dir=None):
    return os.path.join(get_local_paths(install_dir)["dir"], "Complemento")


def caminho_gpkg(install_dir=None):
    return os.path.join(pasta(install_dir), GPKG)


def instalado(install_dir=None):
    return os.path.exists(caminho_gpkg(install_dir)) and os.path.exists(os.path.join(pasta(install_dir), QLR))


def _arq_versao(install_dir=None):
    return caminho_gpkg(install_dir) + ".versao.json"


def versao_local(install_dir=None):
    try:
        with open(_arq_versao(install_dir), encoding="utf-8") as f:
            return json.load(f)["atualizado_em"]
    except Exception:
        return None


def info_remota():
    """(atualizado_em ISO, tamanho) do GPKG na Release, ou None sem rede."""
    try:
        req = urllib.request.Request(BASE_URL + GPKG, headers=HEADERS, method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as r:
            lm = r.headers.get("Last-Modified")
            if lm:
                cl = r.headers.get("Content-Length")
                return _http_date_para_iso(lm), int(cl) if cl else None
    except Exception:
        pass
    return None


def verificar(install_dir=None):
    """(estado, mensagem): estado = 'nao_instalado' | 'atualizar' | 'ok' | 'sem_rede'."""
    if not instalado(install_dir):
        return "nao_instalado", "Complemento não instalado."
    remoto = info_remota()
    if remoto is None or not remoto[0]:
        return "sem_rede", "Instalado (não foi possível checar atualização)."
    local = versao_local(install_dir)
    if local is None:
        return "ok", "Instalado."
    from datetime import datetime
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    if (datetime.strptime(remoto[0], fmt) - datetime.strptime(local, fmt)).total_seconds() > 120:
        return "atualizar", f"Nova versão disponível (publicada em {remoto[0][:10]})."
    return "ok", "Atualizado."


def _baixar_arquivo(nome, destino, cb, p0, p1):
    tmp = destino + ".tmp"
    req = urllib.request.Request(BASE_URL + nome, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        baixado = 0
        with open(tmp, "wb") as f:
            while True:
                chunk = resp.read(262144)
                if not chunk:
                    break
                f.write(chunk)
                baixado += len(chunk)
                if cb:
                    frac = baixado / total if total else 0.5
                    cb(p0 + int((p1 - p0) * frac), f"Baixando {nome}... {baixado / 1_048_576:.0f} / {total / 1_048_576:.0f} MB")
    if os.path.getsize(tmp) < 10_000:
        _rm(tmp)
        raise RuntimeError(f"Arquivo {nome} baixado inválido.")
    if os.path.exists(destino):
        os.remove(destino)
    os.rename(tmp, destino)


def baixar(install_dir=None, progress_callback=None):
    """Baixa o .qlr e o .gpkg. Retorna (ok, erro)."""
    d = pasta(install_dir)
    os.makedirs(d, exist_ok=True)
    remoto = info_remota()
    try:
        if progress_callback:
            progress_callback(3, "Conectando ao GitHub...")
        _baixar_arquivo(QLR, os.path.join(d, QLR), progress_callback, 3, 8)
        _baixar_arquivo(GPKG, os.path.join(d, GPKG), progress_callback, 8, 96)
        if remoto and remoto[0]:
            with open(_arq_versao(install_dir), "w", encoding="utf-8") as f:
                json.dump({"atualizado_em": remoto[0]}, f)
        return True, ""
    except urllib.error.HTTPError as e:
        return False, f"Erro HTTP {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return False, f"Sem conexão com a internet: {e.reason}"
    except Exception as e:
        _rm(os.path.join(d, GPKG + ".tmp"))
        return False, str(e)


def adicionar_ao_projeto(project, install_dir=None):
    """Carrega o .qlr (grupos, estilos e serviços online) num grupo do projeto aberto.
    Camadas pesadas entram desligadas (só os limites municipais ficam visíveis)."""
    from qgis.core import QgsLayerDefinition, QgsLayerTree
    arq = os.path.join(pasta(install_dir), QLR)
    if not os.path.exists(arq):
        return False, "Complemento não instalado. Baixe primeiro."
    raiz = project.layerTreeRoot()
    if raiz.findGroup(NOME_GRUPO) is not None:
        return False, f'O grupo "{NOME_GRUPO}" já está no projeto.'
    grupo = raiz.addGroup(NOME_GRUPO)
    ok, msg = QgsLayerDefinition.loadLayerDefinition(arq, project, grupo)
    if not ok:
        raiz.removeChildNode(grupo)
        return False, f"Não foi possível carregar as camadas: {msg}"

    def configurar(no, nivel):
        for filho in no.children():
            if QgsLayerTree.isGroup(filho):
                filho.setExpanded(False)
                configurar(filho, nivel + 1)
            else:
                filho.setItemVisibilityChecked(False)
    configurar(grupo, 0)
    for filho in grupo.children():
        if QgsLayerTree.isGroup(filho) and filho.name() == "Limites":
            for camada in filho.findLayers():
                camada.setItemVisibilityChecked(True)
    grupo.setExpanded(True)
    return True, f'Grupo "{NOME_GRUPO}" adicionado — ligue as camadas que quiser usar.'
