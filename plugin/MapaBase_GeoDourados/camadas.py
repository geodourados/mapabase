"""Localiza as camadas do projeto pela TABELA de origem, não pelo nome de exibição.

Funciona nos dois projetos: o oficial offline (fonte GeoPackage, "...|layername=tabela")
e o projeto Fonte (PostgreSQL, tabela do banco).
"""
import re

from qgis.core import QgsDataSourceUri, QgsVectorLayer

TABELA_LOTES = "lotes_fiscais"
TABELA_LOTEAMENTOS = "loteamentos"
# Duas camadas do projeto apontam pra mesma tabela eixo_viario (filtros diferentes);
# no GPKG a de logradouros vira "4_logradouros  atual_e_anterior". O id da camada
# é o mesmo nos dois projetos, então é a forma estável de achá-la.
TABELA_LOGRADOUROS_GPKG = "4_logradouros  atual_e_anterior"
ID_LOGRADOUROS = "eixo_viario20201025220825010"


def tabela_da_camada(layer):
    origem = layer.source() or ""
    m = re.search(r"layername=([^|]+)", origem)
    if m:
        return m.group(1)
    try:
        return QgsDataSourceUri(origem).table() or ""
    except Exception:
        return ""


def resolver_layer(project, tabela, id_prefixo=None):
    candidatas = []
    for layer in project.mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue
        if (id_prefixo and layer.id().startswith(id_prefixo)) or tabela_da_camada(layer) == tabela:
            candidatas.append(layer)
    validas = [l for l in candidatas if l.isValid()]
    return (validas or candidatas or [None])[0]


def camadas_principais(project):
    return {
        "lotes": resolver_layer(project, TABELA_LOTES),
        "loteamentos": resolver_layer(project, TABELA_LOTEAMENTOS),
        "logradouros": resolver_layer(project, TABELA_LOGRADOUROS_GPKG, id_prefixo=ID_LOGRADOUROS),
    }
