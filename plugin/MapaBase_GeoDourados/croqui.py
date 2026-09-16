"""
Gera o croqui (PDF) do lote selecionado — mesmo mecanismo (atlas do
QGIS filtrado pelo lote) usado pelo plugin interno "GeoDourados -
Cadastro Fiscal", simplificado pra funcionar 100% offline (sem BETHA/CAC,
sem PostgreSQL) e disparado pela seleção normal de feição no mapa, não
por uma ferramenta de identificação própria.
"""
import os
import re
import socket

NOME_LAYOUT_CROQUI = "GeoDourados - Croqui A4 (Uso Público - Offline)"
NOME_LAYER_GPKG_LOTES = "lotes_fiscais"

# Mesma lista de escalas cadastrais padrão usada no Cadastro Fiscal —
# "escala da tela" arredonda pra próxima dessa lista, pra nunca cortar
# o lote fora da folha.
ESCALAS_CROQUI = [100, 125, 150, 200, 250, 300, 400, 500, 750, 1000, 1250, 1500,
                  2000, 2500, 5000, 10000, 20000, 25000, 50000, 100000]


def obter_ip_local():
    """IP local da máquina (rede/estação) — não tenta geolocalizar, só
    identifica de qual estação o croqui saiu."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        return "desconhecido"


def obter_base_atualizada_em(gpkg_path):
    """Lê a data/hora de geração gravada no GPKG pelo exportar_gpkg.py
    (tabela geodourados_metadata) — se não existir (base antiga, gerada
    antes dessa funcionalidade), mostra "desconhecida" em vez de quebrar."""
    import sqlite3
    try:
        conn = sqlite3.connect(gpkg_path)
        cur = conn.cursor()
        cur.execute("SELECT valor FROM geodourados_metadata WHERE chave='gerado_em'")
        row = cur.fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception:
        pass
    return "desconhecida"


def resolver_layer_lotes(project):
    """Acha a camada de lotes pelo NOME DA TABELA dentro do GPKG
    (lotes_fiscais), não pelo nome de exibição — funciona mesmo que o
    usuário tenha renomeado a camada no projeto oficial."""
    for layer in project.mapLayers().values():
        if layer.type() != layer.VectorLayer:
            continue
        origem = layer.source() or ""
        if f"layername={NOME_LAYER_GPKG_LOTES}" in origem:
            return layer
    return None


def gerar_croqui(iface, gpkg_path, escala_fixa=1000):
    """escala_fixa=1000 -> sempre 1:1000. escala_fixa=None -> usa a
    escala atual da tela, arredondada pra escala cadastral padrão mais
    próxima. Retorna (ok: bool, mensagem: str)."""
    from qgis.core import (
        QgsProject, QgsExpressionContextUtils, QgsLayoutExporter, QgsLayoutItemMap,
    )
    from qgis.PyQt.QtGui import QDesktopServices
    from qgis.PyQt.QtCore import QUrl

    project = QgsProject.instance()

    layer_lotes = resolver_layer_lotes(project)
    if layer_lotes is None:
        return False, "Camada de lotes não encontrada no projeto aberto."

    selecionados = layer_lotes.selectedFeatures()
    if len(selecionados) != 1:
        return False, "Selecione exatamente 1 lote no mapa antes de gerar o croqui."
    feat = selecionados[0]

    layout = project.layoutManager().layoutByName(NOME_LAYOUT_CROQUI)
    if layout is None:
        return False, f'Modelo "{NOME_LAYOUT_CROQUI}" não encontrado no projeto.'

    ip_local = obter_ip_local()
    base_em = obter_base_atualizada_em(gpkg_path)
    campos = [f.name() for f in feat.fields()]
    lote_id = feat["id"] if "id" in campos else feat.id()

    # Seta em projeto E layout — escopo de layout tem precedência na
    # avaliação de expressões, então um valor antigo salvo no layout (de
    # uma edição manual anterior) nunca "gruda" e passa a ser sobrescrito
    # a cada geração.
    for escopo_set in (
        lambda k, v: QgsExpressionContextUtils.setProjectVariable(project, k, v),
        lambda k, v: QgsExpressionContextUtils.setLayoutVariable(layout, k, v),
    ):
        escopo_set("estacao_ip", ip_local)
        escopo_set("base_atualizada_em", base_em)
        escopo_set("lote_alvo", lote_id)

    atlas = layout.atlas()
    atlas.setCoverageLayer(layer_lotes)
    atlas.setEnabled(True)
    atlas.setSortFeatures(False)
    atlas.setFilterFeatures(True)
    atlas.setFilterExpression('"id" = @lote_alvo')

    mapitem = None
    if escala_fixa is None:
        itens_mapa = [it for it in layout.items() if isinstance(it, QgsLayoutItemMap)]
        if itens_mapa:
            mapitem = itens_mapa[0]

    escala_anterior = mapitem.scale() if mapitem is not None else None
    atlas.beginRender()
    try:
        if atlas.count() != 1:
            return False, "Lote não localizado pelo filtro do atlas — tente selecionar de novo."

        if escala_fixa is not None:
            escala = escala_fixa
        else:
            tela = iface.mapCanvas().scale()
            escala = next((e for e in ESCALAS_CROQUI if e >= tela), ESCALAS_CROQUI[-1])
            if mapitem is not None:
                mapitem.setScale(escala)

        for it in layout.items():
            if hasattr(it, "id") and it.id() == "Escala valor":
                it.setText("1:{:,.0f}".format(escala).replace(",", "."))
                break

        atlas.first()
        layout.refresh()

        insc = str(feat["insc_imob"]) if "insc_imob" in campos and feat["insc_imob"] else str(feat.id())
        nome_arquivo = re.sub(r"\W+", "_", insc)
        sufixo = f"_1-{escala}" if escala_fixa is None else ""

        pasta = os.path.join(os.path.expanduser("~"), "Downloads", "GeoDourados - Croquis")
        os.makedirs(pasta, exist_ok=True)
        destino = os.path.join(pasta, f"Croqui_{nome_arquivo}{sufixo}.pdf")

        cfg = QgsLayoutExporter.PdfExportSettings()
        cfg.dpi = 300
        resultado = QgsLayoutExporter(layout).exportToPdf(destino, cfg)

        if resultado == QgsLayoutExporter.Success:
            QDesktopServices.openUrl(QUrl.fromLocalFile(destino))
            return True, f"Croqui gerado (1:{escala}): {destino}"
        return False, f"Falha ao exportar o croqui (código {resultado})."
    finally:
        if mapitem is not None and escala_anterior is not None:
            mapitem.setScale(escala_anterior)
        atlas.endRender()
