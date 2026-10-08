"""MapBiomas – Coleção 11 (uso e cobertura da terra, 1985–2025), lida direto do serviço público do MapBiomas.

Não baixa nada: o QGIS lê só a parte visível do COG pela internet (/vsicurl). Dados: MapBiomas, CC BY 4.0.
"""
from qgis.core import QgsPalettedRasterRenderer, QgsRasterLayer
from qgis.PyQt.QtGui import QColor

URL = ("https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/collection11/lulc/coverage/"
       "brazil_coverage/brazil_coverage-col11_{ano}.tif")
ANOS = (1985, 2025)
PROP = "mapabase/mapbiomas_ano"
GRUPO = "MapBiomas"

# (código, nome, cor) – legenda oficial da Coleção (classes sem nome conhecido aqui saem como "classe N")
CLASSES = [
    (3, "Formação florestal", "#1f8d49"), (4, "Formação savânica", "#7dc975"), (5, "Mangue", "#04381d"),
    (6, "Floresta alagável", "#026975"), (49, "Restinga arbórea", "#02d659"),
    (11, "Campo alagado e área pantanosa", "#519799"), (12, "Formação campestre", "#d6bc74"),
    (32, "Apicum", "#fc8114"), (29, "Afloramento rochoso", "#ffaa5f"), (50, "Restinga herbácea", "#ad5100"),
    (15, "Pastagem", "#edde8e"), (39, "Soja", "#f5b3c8"), (20, "Cana", "#db7093"), (40, "Arroz", "#c71585"),
    (62, "Algodão", "#ff69b4"), (41, "Outras lavouras temporárias", "#f54ca9"), (46, "Café", "#d68fe2"),
    (47, "Citrus", "#9932cc"), (35, "Dendê", "#9065d0"), (48, "Outras lavouras perenes", "#e6ccff"),
    (9, "Silvicultura", "#7a5900"), (21, "Mosaico de usos", "#ffefc3"),
    (23, "Praia, duna e areal", "#ffa07a"), (24, "Área urbanizada", "#d4271e"), (30, "Mineração", "#9c0027"),
    (75, "Usina fotovoltaica", "#c12100"), (25, "Outras áreas não vegetadas", "#db4d4f"),
    (33, "Rio, lago e oceano", "#2532e4"), (31, "Aquicultura", "#091077"),
    (77, "Classe 77", "#d6bc74"), (84, "Classe 84", "#d6bc74"), (91, "Classe 91", "#db4d4f"),
]


def _configurar():
    """Leitura remota do COG: usa o repositório de certificados do Windows (redes com inspeção SSL, como a da
    Prefeitura, têm uma autoridade própria que o GDAL sozinho não conhece) e só pede o que for preciso."""
    from osgeo import gdal
    for chave, valor in (("GDAL_HTTP_USE_CAPI_STORE", "YES"), ("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR"),
                         ("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif"), ("GDAL_HTTP_MULTIPLEX", "YES"),
                         ("VSI_CACHE", "TRUE"), ("GDAL_CACHEMAX", "256")):
        gdal.SetConfigOption(chave, valor)


def _fonte(ano):
    _configurar()
    return "/vsicurl/" + URL.format(ano=ano)


def _estilo(layer):
    classes = [QgsPalettedRasterRenderer.Class(c, QColor(cor), nome) for c, nome, cor in CLASSES]
    layer.setRenderer(QgsPalettedRasterRenderer(layer.dataProvider(), 1, classes))
    layer.triggerRepaint()


def camadas(project):
    return [l for l in project.mapLayers().values()
            if isinstance(l, QgsRasterLayer) and l.customProperty(PROP) is not None]


def adicionar(project, ano):
    """Adiciona a camada do ano (ou troca o ano da que já existe). Retorna (ok, mensagem)."""
    ano = max(ANOS[0], min(ANOS[1], int(ano)))
    nome = f"MapBiomas Col. 11 – {ano}"
    existentes = camadas(project)
    if existentes:
        camada = existentes[0]
        camada.setDataSource(_fonte(ano), nome, "gdal")
        if not camada.isValid():
            return False, "Não foi possível abrir o MapBiomas (sem internet ou serviço fora do ar)."
        camada.setName(nome)
        camada.setCustomProperty(PROP, ano)
        _estilo(camada)
        return True, f"Camada atualizada para {ano}."
    camada = QgsRasterLayer(_fonte(ano), nome, "gdal")
    if not camada.isValid():
        return False, "Não foi possível abrir o MapBiomas (sem internet ou serviço fora do ar)."
    camada.setCustomProperty(PROP, ano)
    _estilo(camada)
    project.addMapLayer(camada, False)
    raiz = project.layerTreeRoot()
    grupo = raiz.findGroup(GRUPO) or raiz.insertGroup(0, GRUPO)
    grupo.insertLayer(0, camada).setExpanded(False)
    return True, f"Camada MapBiomas {ano} adicionada (grupo \"{GRUPO}\")."
