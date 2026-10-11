"""Validador de CEP: confere o formato, procura na base de logradouros de
Dourados (campo `cep`) e consulta os Correios (via ViaCEP) quando há internet."""
import json
import re
import urllib.request

from qgis.core import QgsFeatureRequest, QgsGeometry

from .camadas import camadas_principais

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GeoDouradosPlugin/2.0"}


def normalizar(texto):
    """8 dígitos do CEP, ou None se o formato não serve."""
    digitos = re.sub(r"\D", "", texto or "")
    return digitos if len(digitos) == 8 else None


_MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "em", "a", "o"}


def padronizar(nome):
    """Padrão de escrita dos nomes de rua (base do mapa e Correios): Iniciais Maiúsculas, com
    de/da/do/das/dos/e em minúsculas. Siglas romanas (II, III, IV...) ficam em maiúsculas."""
    import re
    palavras = []
    for i, p in enumerate((nome or "").strip().split()):
        base = p.lower()
        if re.fullmatch(r"[ivxlcdm]+", base) and len(base) > 1 and base not in _MINUSCULAS:
            palavras.append(p.upper())
        elif i > 0 and base in _MINUSCULAS:
            palavras.append(base)
        else:
            palavras.append("-".join(x[:1].upper() + x[1:] for x in base.split("-")))
    return " ".join(palavras)


def formatar(cep8):
    return f"{cep8[:5]}-{cep8[5:]}"


def buscar_local(project, cep8):
    """Nomes dos logradouros da base que têm esse CEP (lista, possivelmente vazia)."""
    layer = camadas_principais(project)["logradouros"]
    if layer is None or layer.fields().indexOf("cep") < 0:
        return []
    req = QgsFeatureRequest().setFilterExpression(f"replace(\"cep\", '-', '') = '{cep8}'")
    nomes = set()
    for f in layer.getFeatures(req):
        for campo in ("nome_logradouro", "nome"):
            if layer.fields().indexOf(campo) >= 0 and f[campo] not in (None, "") and str(f[campo]) != "NULL":
                nomes.add(str(f[campo]).strip())
                break
    return sorted(nomes)


def consultar_correios(cep8):
    """Dados do CEP (dict) ou None se não existe. Levanta exceção se não houver rede."""
    req = urllib.request.Request(f"https://viacep.com.br/ws/{cep8}/json/", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=8) as r:
        dados = json.load(r)
    return None if dados.get("erro") else dados


# ── CEP a partir do mapa (eixo viário clicado / frente do lote) ──────────────
def _cep_do_valor(valor):
    if valor is None or str(valor) in ("", "NULL"):
        return None
    return normalizar(str(valor))


def _nome_eixo(layer, feat):
    for campo in ("nome_logradouro", "nome"):
        if layer.fields().indexOf(campo) >= 0 and feat[campo] not in (None, "") and str(feat[campo]) != "NULL":
            return str(feat[campo]).strip()
    return "(sem nome)"


def _para_crs(geom_ou_pt, crs_origem, crs_destino, project):
    from qgis.core import QgsCoordinateTransform, QgsGeometry
    if crs_origem == crs_destino:
        return geom_ou_pt
    tr = QgsCoordinateTransform(crs_origem, crs_destino, project)
    g = QgsGeometry(geom_ou_pt)
    g.transform(tr)
    return g


def eixo_no_ponto(project, ponto_geom, crs_ponto, tolerancia):
    """Eixo viário mais próximo do ponto clicado (QgsGeometry de ponto em crs_ponto),
    dentro da tolerância (unidades do crs_ponto). Retorna dict ou None."""
    from qgis.core import QgsFeatureRequest, QgsGeometry
    layer = camadas_principais(project)["logradouros"]
    if layer is None:
        return None
    pt = _para_crs(ponto_geom, crs_ponto, layer.crs(), project)
    p = pt.asPoint()
    # tolerância na unidade da camada (mesma unidade nos CRS usados aqui; se mudar, margem generosa)
    rect = pt.buffer(tolerancia, 4).boundingBox()
    melhor = None
    for f in layer.getFeatures(QgsFeatureRequest().setFilterRect(rect)):
        if f.geometry().isNull():
            continue
        dist = f.geometry().distance(pt)
        if dist <= tolerancia and (melhor is None or dist < melhor["distancia"]):
            melhor = {"nome": _nome_eixo(layer, f), "cep8": _cep_do_valor(f["cep"]) if layer.fields().indexOf("cep") >= 0 else None,
                      "distancia": dist, "geom": QgsGeometry_copia(f.geometry()), "crs": layer.crs()}
    return melhor


def QgsGeometry_copia(g):
    from qgis.core import QgsGeometry
    return QgsGeometry(g)


def _testada(lote, rua_geom, dist, folga):
    """Metros da divisa do lote que correm ao longo da rua (testada): trecho do contorno do lote
    dentro de uma faixa em volta do eixo, com raio = distância do lote ao eixo + folga."""
    contorno = QgsGeometry_copia(lote)
    contorno = QgsGeometry(contorno.constGet().boundary())      # polígono -> linha (divisa)
    faixa = rua_geom.buffer(dist + folga, 8)
    return contorno.intersection(faixa).length()


def eixos_da_frente(project, geom_lote, crs_lote, folga=6.0):
    """Eixos viários que fazem frente ao lote, ordenados pela MENOR TESTADA (trecho de divisa do lote
    voltado para a rua). Lote de esquina tem duas frentes: a de menor testada vem primeiro.
    Lista de dicts com nome, cep8, distancia, testada, geom, crs."""
    from qgis.core import QgsFeatureRequest, QgsGeometry
    layer = camadas_principais(project)["logradouros"]
    if layer is None:
        return []
    lote = _para_crs(geom_lote, crs_lote, layer.crs(), project)
    achados = []
    for raio in (60, 150, 400):
        rect = lote.boundingBox()
        rect.grow(raio)
        achados = []
        for f in layer.getFeatures(QgsFeatureRequest().setFilterRect(rect)):
            if f.geometry().isNull():
                continue
            achados.append({"nome": _nome_eixo(layer, f),
                            "cep8": _cep_do_valor(f["cep"]) if layer.fields().indexOf("cep") >= 0 else None,
                            "distancia": f.geometry().distance(lote),
                            "geom": QgsGeometry_copia(f.geometry()), "crs": layer.crs()})
        if achados:
            break
    achados.sort(key=lambda r: r["distancia"])
    if not achados:
        return []
    corte = achados[0]["distancia"] + folga
    juntos = {}
    for r in achados:
        if r["distancia"] > corte:
            break
        r["testada"] = _testada(lote, r["geom"], r["distancia"], folga)
        chave = (r["nome"], r["cep8"])
        if chave in juntos:                      # mesma rua em vários trechos: soma a testada
            juntos[chave]["testada"] += r["testada"]
            juntos[chave]["distancia"] = min(juntos[chave]["distancia"], r["distancia"])
        else:
            juntos[chave] = r
    saida = list(juntos.values())
    reais = [r for r in saida if r["testada"] >= 2.0]      # ignora quem só encosta na quina
    saida = reais or saida
    saida.sort(key=lambda r: (r["testada"], r["distancia"]))
    return saida
