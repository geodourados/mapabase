"""Validador de CEP: confere o formato, procura na base de logradouros de
Dourados (campo `cep`) e consulta os Correios (via ViaCEP) quando há internet."""
import json
import re
import urllib.request

from qgis.core import QgsFeatureRequest

from .camadas import camadas_principais

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) GeoDouradosPlugin/2.0"}


def normalizar(texto):
    """8 dígitos do CEP, ou None se o formato não serve."""
    digitos = re.sub(r"\D", "", texto or "")
    return digitos if len(digitos) == 8 else None


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
