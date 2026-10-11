"""Camadas online (XYZ/WMS/ArcGIS) mais usadas — mesmas do projeto Fonte.

Servem para abrir o plugin num projeto em branco e puxar a imagem de fundo
com um clique. Exigem internet.
"""
from qgis.core import QgsProject, QgsRasterLayer

# tipo: "base" = imagem de fundo (vai pro fim da árvore, embaixo das camadas vetoriais);
#       "sobreposicao" = camada transparente (vai pro topo).
SERVICOS = [
    {
        "nome": "Google Satellite",
        "descricao": "Imagem de satélite",
        "tipo": "base",
        "provider": "wms",
        "fonte": "crs=EPSG:3857&format&type=xyz&url=https://mt1.google.com/vt/lyrs%3Ds%26x%3D%7Bx%7D%26y%3D%7By%7D%26z%3D%7Bz%7D",
    },
    {
        "nome": "Raster/Ortofoto_2018",
        "descricao": "Ortofoto 2018 (GeoPortal da Prefeitura)",
        "tipo": "base",
        "provider": "arcgismapserver",
        "fonte": " format='JPGPNG' layer='' url='https://geoportal.dourados.ms.gov.br/server/rest/services/Raster/Ortofoto_2018/ImageServer'",
    },
    {
        "nome": "Google Roads",
        "descricao": "Ruas e rótulos sobre a imagem",
        "tipo": "sobreposicao",
        "provider": "wms",
        "fonte": "crs=EPSG:3857&format&type=xyz&url=https://mt1.google.com/vt/lyrs%3Dh%26x%3D%7Bx%7D%26y%3D%7By%7D%26z%3D%7Bz%7D&zmax=19&zmin=0",
    },
    {
        "nome": "Google Traffic",
        "descricao": "Trânsito em tempo real",
        "tipo": "sobreposicao",
        "provider": "wms",
        "fonte": "crs=EPSG:3857&format&type=xyz&url=https://mt1.google.com/vt?lyrs%3Dh@159000000,traffic%7Cseconds_into_week:-1%26style%3D3%26x%3D%7Bx%7D%26y%3D%7By%7D%26z%3D%7Bz%7D&zmax=19&zmin=0",
    },
    {
        "nome": "Waze (World)",
        "descricao": "Mapa de tráfego do Waze",
        "tipo": "sobreposicao",
        "provider": "wms",
        "fonte": "crs=EPSG:3857&format&type=xyz&url=https://worldtiles3.waze.com/tiles/%7Bz%7D/%7Bx%7D/%7By%7D.png&zmax=20&zmin=0",
    },
]


def _norm(fonte):
    return " ".join((fonte or "").split())


def camada_no_projeto(project, servico):
    """Camada já existente no projeto com a mesma fonte (ou mesmo nome), ou None."""
    alvo = _norm(servico["fonte"])
    for layer in project.mapLayers().values():
        if isinstance(layer, QgsRasterLayer) and (
                _norm(layer.source()) == alvo or layer.name() == servico["nome"]):
            return layer
    return None


def adicionar(project, servico):
    """Adiciona o serviço ao projeto. Retorna (ok, mensagem)."""
    if camada_no_projeto(project, servico) is not None:
        return False, f'"{servico["nome"]}" já está no projeto.'
    layer = QgsRasterLayer(servico["fonte"], servico["nome"], servico["provider"])
    if not layer.isValid():
        return False, f'Não foi possível carregar "{servico["nome"]}" (sem internet ou serviço fora do ar).'
    project.addMapLayer(layer, False)
    raiz = project.layerTreeRoot()
    if servico["tipo"] == "sobreposicao":
        raiz.insertLayer(0, layer)
    else:
        raiz.addLayer(layer)
    return True, f'"{servico["nome"]}" adicionada.'
