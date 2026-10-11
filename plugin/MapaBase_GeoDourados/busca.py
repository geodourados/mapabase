"""Busca de lotes, loteamentos e logradouros nas camadas do projeto aberto.

Só usa dados públicos presentes na base (inscrição, matrícula, nomes). Cada
item de resultado é um dict: {"rotulo": str, "layer": QgsVectorLayer, "fids": [int]}.
"""
import re
import unicodedata

from qgis.core import (
    QgsCoordinateTransform, QgsFeatureRequest, QgsGeometry, QgsProject, QgsRectangle,
)

from .camadas import camadas_principais
from .compat import E

TIPOS = [
    ("Inscrição", "inscricao"),
    ("Matrícula", "matricula"),
    ("Loteamento", "loteamento"),
    ("Logradouro (rua)", "logradouro"),
]
LIMITE = 300


def _norm(texto):
    texto = unicodedata.normalize("NFD", str(texto or ""))
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").lower().strip()


def _esc(texto):
    return str(texto).replace("'", "''")


def _tem(layer, campo):
    return layer.fields().indexOf(campo) >= 0


def _valor(feat, campo):
    try:
        v = feat[campo]
    except KeyError:
        return ""
    return "" if v is None or str(v) == "NULL" else str(v).strip()


def _rotulo_lote(feat):
    partes = [_valor(feat, "insc_imob") or "(sem inscrição)"]
    if _valor(feat, "matricula"):
        partes.append("Mat. " + _valor(feat, "matricula"))
    qd, lt = _valor(feat, "quadra_cartorio"), _valor(feat, "lote_cartorio")
    ql = " ".join(p for p in ((f"Q{qd}" if qd else ""), (f"L{lt}" if lt else "")) if p)
    if ql:
        partes.append(ql)
    return " — ".join(partes)


def _chaves_lote(feat):
    return {
        "inscricao": _valor(feat, "insc_imob"),
        "matricula": _valor(feat, "matricula"),
        "quadra": _valor(feat, "quadra_cartorio"),
        "lote": _valor(feat, "lote_cartorio"),
    }


def _buscar_lotes(layer, tipo, termo, exata):
    if tipo == "inscricao":
        campo = "insc_imob"
        digitos = re.sub(r"\D", "", termo)
        if not digitos:
            return [], "Digite os números da inscrição (com ou sem pontos)."
        valor = f"replace(\"insc_imob\", '.', '')"
        expr = f"{valor} = '{digitos}'" if exata else f"{valor} LIKE '{digitos}%'"
    else:
        campo = "matricula"
        t = _esc(termo.upper())
        expr = f"upper(\"matricula\") = '{t}'" if exata else f"upper(\"matricula\") LIKE '{t}%'"
    if not _tem(layer, campo):
        return [], f"A camada de lotes não tem o campo '{campo}'."
    req = QgsFeatureRequest().setFilterExpression(expr).setLimit(LIMITE)
    itens = [{"rotulo": _rotulo_lote(f), "layer": layer, "fids": [f.id()], "chaves": _chaves_lote(f)}
             for f in layer.getFeatures(req)]
    return itens, ""


def _buscar_por_nome(layer, campos_nome, termo, exata, rotulo_extra=None):
    campos = [c for c in campos_nome if _tem(layer, c)]
    if not campos:
        return [], "A camada não tem campo de nome."
    alvo = _norm(termo)
    palavras = alvo.split()
    req = QgsFeatureRequest().setFlags(E(QgsFeatureRequest, "Flag", "NoGeometry")).setSubsetOfAttributes(campos, layer.fields())
    grupos = {}
    for f in layer.getFeatures(req):
        textos = [_norm(_valor(f, c)) for c in campos]
        if exata:
            ok = any(t == alvo for t in textos)
        else:
            ok = any(all(re.search(r"(?<!\w)" + re.escape(p), t) for p in palavras) for t in textos if t)
        if not ok:
            continue
        nome = _valor(f, campos[0]) or _valor(f, campos[-1])
        chave = _norm(nome)
        g = grupos.setdefault(chave, {"rotulo": nome, "fids": []})
        g["fids"].append(f.id())
        if rotulo_extra and not g.get("extra"):
            g["extra"] = rotulo_extra(f)
    itens = []
    for g in sorted(grupos.values(), key=lambda x: _norm(x["rotulo"]))[:LIMITE]:
        rot = g["rotulo"] + (f"  ({g['extra']})" if g.get("extra") else "")
        itens.append({"rotulo": rot, "layer": layer, "fids": g["fids"]})
    return itens, ""


CRITERIOS_LOTE = [("Inscrição", "inscricao"), ("Matrícula", "matricula"), ("Quadra / Lote", "quadra_lote")]
CRITERIOS_NOME = [("Nome", "nome")]


def _natural(texto):
    """Ordem 'natural': 2 antes de 10; vazio por último."""
    texto = (texto or "").strip()
    if not texto:
        return [(1, 0, "")]
    return [(0, int(p), "") if p.isdigit() else (0, 0, p.lower()) for p in re.split(r"(\d+)", texto) if p]


def ordenar(itens, criterio, decrescente=False):
    """Ordena a lista de resultados (in place) e devolve a mesma lista."""
    def chave(it):
        c = it.get("chaves")
        if not c:
            return _natural(_norm(it["rotulo"]))
        if criterio == "matricula":
            return _natural(c["matricula"]) + _natural(c["inscricao"])
        if criterio == "quadra_lote":
            return _natural(c["quadra"]) + _natural(c["lote"]) + _natural(c["inscricao"])
        return _natural(c["inscricao"])
    itens.sort(key=chave, reverse=decrescente)
    return itens


def buscar(project, tipo, termo, exata):
    """Retorna (itens, mensagem)."""
    cam = camadas_principais(project)
    termo = termo.strip()
    if tipo in ("inscricao", "matricula"):
        if cam["lotes"] is None:
            return [], "Camada de lotes não encontrada no projeto aberto."
        itens, msg = _buscar_lotes(cam["lotes"], tipo, termo, exata)
    elif tipo == "loteamento":
        if cam["loteamentos"] is None:
            return [], "Camada de loteamentos não encontrada no projeto aberto."
        itens, msg = _buscar_por_nome(cam["loteamentos"], ["nome", "nome_anterior"], termo, exata)
    else:
        if cam["logradouros"] is None:
            return [], "Camada de logradouros não encontrada no projeto aberto."
        itens, msg = _buscar_por_nome(
            cam["logradouros"], ["nome_logradouro", "nome", "nome_anterior", "cep"], termo, exata,
            rotulo_extra=lambda f: ("CEP " + _valor(f, "cep")) if re.search(r"\d", _valor(f, "cep")) else "")
    if msg:
        return itens, msg
    if not itens:
        return [], "Nada encontrado."
    mais = f" (mostrando os {LIMITE} primeiros — refine a busca)" if len(itens) >= LIMITE else ""
    return itens, f"{len(itens)} resultado(s){mais}."


def lote_selecionado(project):
    lotes = camadas_principais(project)["lotes"]
    if lotes is None:
        return None, "Camada de lotes não encontrada no projeto aberto."
    sel = lotes.selectedFeatures()
    if len(sel) != 1:
        return None, "Selecione exatamente 1 lote no mapa."
    f = sel[0]
    return {"rotulo": _rotulo_lote(f), "layer": lotes, "fids": [f.id()], "chaves": _chaves_lote(f)}, ""


def zoom_itens(iface, itens, piscar=True):
    """Zoom na união dos itens, seleciona os lotes e pisca o contorno."""
    canvas = iface.mapCanvas()
    destino = canvas.mapSettings().destinationCrs()
    caixa = QgsRectangle()
    caixa.setMinimal()
    geoms = []
    for it in itens:
        layer = it["layer"]
        tr = QgsCoordinateTransform(layer.crs(), destino, QgsProject.instance())
        for f in layer.getFeatures(QgsFeatureRequest().setFilterFids(it["fids"])):
            g = QgsGeometry(f.geometry())
            if g.isNull():
                continue
            g.transform(tr)
            geoms.append(g)
            caixa.combineExtentWith(g.boundingBox())
        if layer.geometryType() == 2 and "insc_imob" in [fl.name() for fl in layer.fields()]:
            layer.removeSelection()
            layer.selectByIds(it["fids"])
    if not geoms:
        return False
    minimo = 0.0002 if destino.isGeographic() else 25.0
    if caixa.width() < minimo or caixa.height() < minimo:
        c = caixa.center()
        caixa = QgsRectangle(c.x() - minimo, c.y() - minimo, c.x() + minimo, c.y() + minimo)
    caixa.scale(1.5)
    canvas.setExtent(caixa)
    canvas.refresh()
    if piscar:
        canvas.flashGeometries(geoms, destino)
    return True
