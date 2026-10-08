# -*- coding: utf-8 -*-
"""Layouts temáticos GeoDourados (A0–A4) – NBR 10068 / NBR 10582 / convenções cartográficas IBGE.

Uso (plugin ou console):  from .layouts_tematicos import criar_layouts
                          criar_layouts(extensao=iface.mapCanvas().extent())
Cria/recria 7 layouts "GeoDourados - Mapa <formato> <orientação> (ABNT)" no projeto, presos ao tema
"Impressão – Mapa Base" (= visibilidade atual da árvore de camadas no momento da criação).
Autor: Ênio Alencar da Silva – SEPLAN/GeoDourados. Ver LEIA-ME_INTEGRACAO.md.
"""
import math
import os

from qgis.core import *
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont, QColor

# Estado da geração em curso (preenchido por criar_layouts; as funções de desenho leem daqui)
P = LM = EXT = VISIVEIS = None
LOGO_BRASAO = LOGO_GEO = LOGO_SEPLAN = LOGO_NORTE = None
AQUI = os.path.dirname(os.path.abspath(__file__))
MAP_ID = 'Mapa principal'
FONT = 'Arial'
TEMA = 'Impressão – Mapa Base'

# Responsável técnico e contato (variáveis do projeto – editáveis em Projeto › Propriedades › Variáveis)
VARS = {
    'rt_nome': 'Ênio Alencar da Silva',
    'rt_titulo': 'Geógrafo',
    'rt_registro': 'CREA-PR 140382 · Visto CREA-MS 45670',
    'rt_art': 'ART de Cargo e Função nº 1320240023149',
    'contato': 'geodourados@dourados.ms.gov.br · (67) 2222-2248',
}

# Declinação magnética – WMM-2025 (NOAA) em Dourados (-22,22; -54,81) em 07/10/2026 (época 2026,7644):
# D = -18,36933°, variação anual -0,14567°/ano. Válido até 2029 (vida do WMM-2025).
DECL = ("with_variable('t', year(now()) + (epoch(now()) - epoch(make_date(year(now()), 1, 1))) / 31557600000, "
        "with_variable('d', -18.36933 - 0.14567 * (@t - 2026.7644), "
        "with_variable('m', round(abs(@d) * 60), "
        "floor(@m / 60) || '°' || lpad(@m % 60, 2, '0') || ''' ' || if(@d < 0, 'W', 'E'))))")


def criar_tema():
    """Tema de impressão = visibilidade atual da árvore (o layout não muda quando a tela muda)."""
    mt = P.mapThemeCollection()
    modelo = QgsLayerTreeModel(P.layerTreeRoot())   # referência mantida até o fim da função
    rec = QgsMapThemeCollection.createThemeFromCurrentState(P.layerTreeRoot(), modelo)
    if mt.hasMapTheme(TEMA):
        mt.update(TEMA, rec)
    else:
        mt.insert(TEMA, rec)
    # visível de fato = marcada E com todos os grupos-pai ligados
    return {n.layerId() for n in P.layerTreeRoot().findLayers() if n.isVisible()}


def fora_da_legenda(l):
    # imagens de fundo (XYZ/WMS/raster) e camadas "ao vivo" do Waze não entram na legenda
    return l is None or l.type() != QgsMapLayerType.VectorLayer or 'waze' in l.name().lower()


def podar_legenda(raiz, visiveis):
    """Poda a árvore PRÓPRIA da legenda (criada pelo QGIS ao desligar o auto-update).

    Não usar setRootGroup() com um clone criado no Python: o objeto é coletado e o QGIS fecha.
    """
    def podar(g):
        for n in list(g.children()):
            if QgsLayerTree.isGroup(n):
                podar(n)
                if not n.children():
                    g.removeChildNode(n)
            elif n.layerId() not in visiveis or fora_da_legenda(n.layer()):
                g.removeChildNode(n)
    podar(raiz)

# (nome, largura, altura, margem NBR 10068)  margem esquerda (encadernação) = 25 mm
FORMATOS = [
    ('A0', 1189, 841, 10, 'Paisagem'),
    ('A1', 841, 594, 10, 'Paisagem'),
    ('A2', 594, 420, 7, 'Paisagem'),
    ('A3', 420, 297, 7, 'Paisagem'),
    ('A4', 297, 210, 7, 'Paisagem'),
    ('A3', 297, 420, 7, 'Retrato'),
    ('A4', 210, 297, 7, 'Retrato'),
]


def lyr(name):
    r = P.mapLayersByName(name)
    return r[0] if r else None


def tfmt(size, bold=False, color='0,0,0'):
    f = QgsTextFormat()
    qf = QFont(FONT)
    qf.setBold(bold)
    f.setFont(qf)
    f.setSize(size)
    f.setSizeUnit(QgsUnitTypes.RenderPoints)
    f.setColor(QColor(*[int(c) for c in color.split(',')]))
    return f


def place(item, x, y, w, h):
    item.attemptMove(QgsLayoutPoint(x, y, QgsUnitTypes.LayoutMillimeters))
    item.attemptResize(QgsLayoutSize(w, h, QgsUnitTypes.LayoutMillimeters))


def rect(L, x, y, w, h, sw=0.25, fill=None, iid=''):
    s = QgsLayoutItemShape(L)
    s.setShapeType(QgsLayoutItemShape.Rectangle)
    props = {'outline_color': '0,0,0,255', 'outline_width': str(sw), 'outline_width_unit': 'MM',
             'joinstyle': 'miter'}
    if fill:
        props['color'] = fill
    else:
        props['style'] = 'no'
    s.setSymbol(QgsFillSymbol.createSimple(props))
    L.addLayoutItem(s)
    place(s, x, y, w, h)
    s.setId(iid)
    s.setLocked(True)
    return s


def label(L, text, x, y, w, h, size, bold=False, ha=Qt.AlignLeft, va=Qt.AlignTop, iid='', html=False, rich=False):
    lb = QgsLayoutItemLabel(L)
    lb.setText(text)
    tf = tfmt(size, bold)
    tf.setAllowHtmlFormatting(rich)
    lb.setTextFormat(tf)
    lb.setHAlign(ha)
    lb.setVAlign(va)
    lb.setMarginX(0)
    lb.setMarginY(0)
    if html:
        lb.setMode(QgsLayoutItemLabel.ModeHtml)
    L.addLayoutItem(lb)
    place(lb, x, y, w, h)
    lb.setId(iid)
    return lb




def pic(L, path, x, y, w, h, iid):
    pc = QgsLayoutItemPicture(L)
    pc.setPicturePath(path, Qgis.PictureFormat.Raster)
    pc.setResizeMode(QgsLayoutItemPicture.Zoom)
    pc.setPictureAnchor(QgsLayoutItem.Middle)
    L.addLayoutItem(pc)
    place(pc, x, y, w, h)
    pc.setId(iid)
    return pc


def nice_down(v, seq=(1, 2, 2.5, 5)):
    e = 10 ** math.floor(math.log10(v))
    best = e
    for m in seq + (10,):
        if m * e <= v + 1e-9:
            best = m * e
    return best


def nice_up(v, seq=(1, 2, 2.5, 5)):
    e = 10 ** math.floor(math.log10(v))
    for m in seq + (10,):
        if m * e >= v - 1e-9:
            return m * e


def build(fmt, W, H, m, orient):
    nome = f'GeoDourados - Mapa {fmt} {orient} (ABNT)'
    old = LM.layoutByName(nome)
    if old:
        LM.removeLayout(old)
    L = QgsPrintLayout(P)
    L.initializeDefaults()
    L.setName(nome)
    L.pageCollection().page(0).setPageSize(QgsLayoutSize(W, H, QgsUnitTypes.LayoutMillimeters))
    LM.addLayout(L)

    k = (min(W, H) / 210.0) ** 0.7          # fator de escala tipográfica
    pad = 1.5 * k
    x0, y0, x1, y1 = 25.0, m, W - m, H - m    # margens NBR 10068 (esq. 25 mm)
    iw, ih = x1 - x0, y1 - y0
    g = 7.5 * k                              # faixa para coordenadas da grade

    # Moldura externa (quadro)
    rect(L, x0, y0, iw, ih, sw=0.7 if fmt in ('A0', 'A1') else 0.5, iid='Moldura externa')

    if orient == 'Paisagem':
        P_w = round(iw * (0.25 if fmt in ('A0', 'A1') else 0.27), 1)
        px = x1 - P_w
        mx, my, mw, mh = x0 + g, y0 + g, px - x0 - 2 * g, ih - 2 * g
        Hp = ih
        fr = [('header', .09), ('title', .09), ('inset', .17), ('legend', None),
              ('scale', .11), ('carto', .12), ('credits', .15)]
        used = sum(f for _, f in fr if f)
        cells = {}
        cy = y0
        for key, f in fr:
            h = (f if f else 1 - used) * Hp
            cells[key] = (px, cy, P_w, h)
            cy += h
    else:
        P_h = round(ih * (0.30 if fmt == 'A4' else 0.27), 1)
        py = y1 - P_h
        mx, my, mw, mh = x0 + g, y0 + g, iw - 2 * g, ih - P_h - 2 * g
        c1, c2 = iw * 0.38, iw * 0.30
        c3 = iw - c1 - c2
        cells = {
            'header': (x0, py, c1, P_h * .18),
            'title': (x0, py + P_h * .18, c1, P_h * .19),
            'carto': (x0, py + P_h * .37, c1, P_h * .27),
            'credits': (x0, py + P_h * .64, c1, P_h * .36),
            'legend': (x0 + c1, py, c2, P_h),
            'inset': (x0 + c1 + c2, py, c3, P_h * .58),
            'scale': (x0 + c1 + c2, py + P_h * .58, c3, P_h * .42),
        }
    for key, (cx, cy, cw, ch) in cells.items():
        rect(L, cx, cy, cw, ch, sw=0.35, iid=f'Célula {key}')

    # ---------------- Mapa principal ----------------
    mp = QgsLayoutItemMap(L)
    mp.setId(MAP_ID)
    L.addLayoutItem(mp)
    place(mp, mx, my, mw, mh)
    mp.setCrs(P.crs())
    mp.setFrameEnabled(True)
    mp.setFrameStrokeWidth(QgsLayoutMeasurement(0.3, QgsUnitTypes.LayoutMillimeters))
    mp.zoomToExtent(EXT)
    mp.setScale(nice_up(mp.scale()))
    mp.setFollowVisibilityPreset(True)
    mp.setFollowVisibilityPresetName(TEMA)
    L.setReferenceMap(mp)

    # Grade UTM (quadrícula) – anotações à esquerda/inferior
    gu = QgsLayoutItemMapGrid('Grade UTM (SIRGAS 2000 / 21S)', mp)
    mp.grids().addGrid(gu)
    gu.setCrs(P.crs())
    gu.setUnits(QgsLayoutItemMapGrid.DynamicPageSizeBased)
    gu.setMinimumIntervalWidth(35 * k)
    gu.setMaximumIntervalWidth(70 * k)
    gu.setStyle(QgsLayoutItemMapGrid.Solid)
    gu.setLineSymbol(QgsLineSymbol.createSimple({'color': '60,60,60,140', 'width': str(0.1 * k), 'width_unit': 'MM'}))
    gu.setFrameStyle(QgsLayoutItemMapGrid.ExteriorTicks)
    gu.setFrameWidth(1.5 * k)
    gu.setFramePenSize(0.2)
    for side, on in ((QgsLayoutItemMapGrid.FrameLeft, True), (QgsLayoutItemMapGrid.FrameBottom, True),
                     (QgsLayoutItemMapGrid.FrameRight, False), (QgsLayoutItemMapGrid.FrameTop, False)):
        gu.setFrameSideFlag(side, on)
    gu.setAnnotationEnabled(True)
    gu.setAnnotationFormat(QgsLayoutItemMapGrid.CustomFormat)
    gu.setAnnotationExpression("format_number(@grid_number, 0) || if(@grid_axis = 'x', ' E', ' N')")
    gu.setAnnotationTextFormat(tfmt(5 * k))
    gu.setAnnotationFrameDistance(0.8 * k)
    for side in (QgsLayoutItemMapGrid.Left, QgsLayoutItemMapGrid.Bottom):
        gu.setAnnotationPosition(QgsLayoutItemMapGrid.OutsideMapFrame, side)
        gu.setAnnotationDisplay(QgsLayoutItemMapGrid.ShowAll, side)
    for side in (QgsLayoutItemMapGrid.Right, QgsLayoutItemMapGrid.Top):
        gu.setAnnotationDisplay(QgsLayoutItemMapGrid.HideAll, side)
    gu.setAnnotationDirection(QgsLayoutItemMapGrid.Vertical, QgsLayoutItemMapGrid.Left)
    gu.setAnnotationDirection(QgsLayoutItemMapGrid.Horizontal, QgsLayoutItemMapGrid.Bottom)

    # Grade geográfica (rede de paralelos e meridianos) – anotações superior/direita
    geo = QgsCoordinateReferenceSystem('EPSG:4674')
    tr = QgsCoordinateTransform(P.crs(), geo, P)
    ge = tr.transformBoundingBox(mp.extent())
    span = max(ge.width(), ge.height())
    step = 3600
    for sec in (5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600):
        if span * 3600 / sec <= 5:
            step = sec
            break
    gg = QgsLayoutItemMapGrid('Grade geográfica (SIRGAS 2000)', mp)
    mp.grids().addGrid(gg)
    gg.setCrs(geo)
    gg.setIntervalX(step / 3600.0)
    gg.setIntervalY(step / 3600.0)
    gg.setStyle(QgsLayoutItemMapGrid.FrameAnnotationsOnly)
    gg.setFrameStyle(QgsLayoutItemMapGrid.ExteriorTicks)
    gg.setFrameWidth(1.5 * k)
    gg.setFramePenSize(0.2)
    for side, on in ((QgsLayoutItemMapGrid.FrameLeft, False), (QgsLayoutItemMapGrid.FrameBottom, False),
                     (QgsLayoutItemMapGrid.FrameRight, True), (QgsLayoutItemMapGrid.FrameTop, True)):
        gg.setFrameSideFlag(side, on)
    gg.setAnnotationEnabled(True)
    gg.setAnnotationFormat(QgsLayoutItemMapGrid.DegreeMinuteSecond)
    gg.setAnnotationPrecision(0)
    gg.setAnnotationTextFormat(tfmt(5 * k))
    gg.setAnnotationFrameDistance(0.8 * k)
    for side in (QgsLayoutItemMapGrid.Right, QgsLayoutItemMapGrid.Top):
        gg.setAnnotationPosition(QgsLayoutItemMapGrid.OutsideMapFrame, side)
        gg.setAnnotationDisplay(QgsLayoutItemMapGrid.ShowAll, side)
    for side in (QgsLayoutItemMapGrid.Left, QgsLayoutItemMapGrid.Bottom):
        gg.setAnnotationDisplay(QgsLayoutItemMapGrid.HideAll, side)
    gg.setAnnotationDirection(QgsLayoutItemMapGrid.Vertical, QgsLayoutItemMapGrid.Right)
    gg.setAnnotationDirection(QgsLayoutItemMapGrid.Horizontal, QgsLayoutItemMapGrid.Top)
    mp.updateBoundingRect()

    MV = f"item_variables('{MAP_ID}')"

    # ---------------- Cabeçalho ----------------
    cx, cy, cw, ch = cells['header']
    lh = ch - 2 * pad
    bw = lh * 515 / 667                       # proporção do brasão
    gw = lh * 1100 / 1200       # proporção do logo GeoDourados
    pic(L, LOGO_BRASAO, cx + pad, cy + pad, bw, lh, 'Brasão de Dourados')
    pic(L, LOGO_GEO, cx + cw - pad - gw, cy + pad, gw, lh, 'Logo GeoDourados')
    label(L, 'PREFEITURA MUNICIPAL\nDE DOURADOS – MS\n'
             'Secretaria de Planejamento – SEPLAN\n'
             'Depto. de Geoprocessamento',
          cx + 2 * pad + bw, cy + pad, cw - 4 * pad - bw - gw, lh, 5.2 * k, True, Qt.AlignHCenter,
          Qt.AlignVCenter, 'Cabeçalho')

    # ---------------- Título ----------------
    cx, cy, cw, ch = cells['title']
    label(L, '[% upper(@project_title) %]', cx + pad, cy + pad, cw - 2 * pad, ch * 0.55 - pad,
          10 * k, True, Qt.AlignHCenter, Qt.AlignVCenter, 'Título')
    label(L, '[% @project_basename %]', cx + pad, cy + ch * 0.55, cw - 2 * pad, ch * 0.45 - pad,
          7.5 * k, False, Qt.AlignHCenter, Qt.AlignVCenter, 'Subtítulo (tema)')

    # ---------------- Mapa de localização ----------------
    cx, cy, cw, ch = cells['inset']
    tl = 3.2 * k
    label(L, 'LOCALIZAÇÃO NO MUNICÍPIO', cx + pad, cy + pad, cw - 2 * pad, tl, 6 * k, True,
          Qt.AlignHCenter, Qt.AlignVCenter, 'Título localização')
    inset = QgsLayoutItemMap(L)
    inset.setId('Mapa de localização')
    L.addLayoutItem(inset)
    place(inset, cx + pad, cy + pad + tl + pad * 0.5, cw - 2 * pad, ch - 2.5 * pad - tl)
    inset.setCrs(P.crs())
    inset.setFrameEnabled(True)
    inset.setFrameStrokeWidth(QgsLayoutMeasurement(0.2, QgsUnitTypes.LayoutMillimeters))
    inset_layers = [l for l in (lyr('Perímetro urbano (Lei 3929/2015)'), lyr('Limite Município')) if l]
    if inset_layers:
        inset.setLayers(inset_layers)
        inset.setKeepLayerSet(True)
        lim = lyr('Limite Município') or inset_layers[0]
        e = QgsCoordinateTransform(lim.crs(), P.crs(), P).transformBoundingBox(lim.extent())
        e.scale(1.08)
        inset.zoomToExtent(e)
    ov = QgsLayoutItemMapOverview('Extensão do mapa', inset)
    inset.overviews().addOverview(ov)
    ov.setLinkedMap(mp)
    ov.setFrameSymbol(QgsFillSymbol.createSimple({'color': '255,0,0,60', 'outline_color': '255,0,0,255',
                                                  'outline_width': '0.4', 'outline_width_unit': 'MM'}))

    # ---------------- Legenda ----------------
    cx, cy, cw, ch = cells['legend']
    leg = QgsLayoutItemLegend(L)
    leg.setId('Legenda')
    L.addLayoutItem(leg)
    leg.setLinkedMap(mp)
    leg.setTitle('LEGENDA')
    leg.setAutoUpdateModel(False)
    podar_legenda(leg.model().rootGroup(), VISIVEIS)
    leg.setLegendFilterByMapEnabled(True)
    leg.setResizeToContents(False)
    leg.setColumnCount(2 if (orient == 'Paisagem' and fmt in ('A0', 'A1')) else 1)
    leg.setSplitLayer(True)
    leg.setSymbolWidth(5 * k)
    leg.setSymbolHeight(3 * k)
    leg.setBoxSpace(pad)
    leg.setWrapString('|')
    leg.rstyle(QgsLegendStyle.Title).setTextFormat(tfmt(7.5 * k, True))
    leg.rstyle(QgsLegendStyle.Group).setTextFormat(tfmt(6.5 * k, True))
    leg.rstyle(QgsLegendStyle.Subgroup).setTextFormat(tfmt(6 * k, True))
    leg.rstyle(QgsLegendStyle.SymbolLabel).setTextFormat(tfmt(5.5 * k))
    leg.setTitleAlignment(Qt.AlignHCenter)
    place(leg, cx + pad * 0.5, cy + pad * 0.5, cw - pad, ch - pad)
    leg.refresh()

    # ---------------- Norte + escalas ----------------
    cx, cy, cw, ch = cells['scale']
    nw = min(cw * 0.22, ch - 2 * pad)
    na = QgsLayoutItemPicture(L)
    na.setId('Indicação do Norte')
    L.addLayoutItem(na)
    na.setPicturePath(LOGO_NORTE, Qgis.PictureFormat.Raster)
    na.setResizeMode(QgsLayoutItemPicture.Zoom)
    na.setLinkedMap(mp)
    place(na, cx + pad, cy + (ch - nw) / 2, nw * 0.69, nw)
    sx = cx + pad * 2 + nw * 0.8
    sw = cx + cw - sx - pad
    label(L, f"ESCALA 1:[% format_number(map_get({MV}, 'map_scale'), 0) %]",
          sx, cy + pad, sw, ch * 0.30, 7.5 * k, True, Qt.AlignHCenter, Qt.AlignVCenter, 'Escala numérica')
    sb = QgsLayoutItemScaleBar(L)
    sb.setId('Escala gráfica')
    L.addLayoutItem(sb)
    sb.setLinkedMap(mp)
    sb.setStyle('Single Box')
    # segmento "redondo": 1 segmento à esquerda (subdividido) + 2 à direita, ~80% da célula
    seg_m = nice_down((sw * 0.80 / 3) / 1000.0 * mp.scale())   # metros reais por segmento
    seg_m = max(seg_m, 1)
    km = seg_m >= 1000
    sb.setUnits(QgsUnitTypes.DistanceKilometers if km else QgsUnitTypes.DistanceMeters)
    sb.setUnitLabel('km' if km else 'm')
    sb.setNumberOfSegments(2)
    sb.setNumberOfSegmentsLeft(1)
    sb.setNumberOfSubdivisions(2)
    sb.setSegmentSizeMode(QgsScaleBarSettings.SegmentSizeFixed)
    sb.setUnitsPerSegment(seg_m / 1000.0 if km else seg_m)
    sb.setNumericFormat(QgsBasicNumericFormat())
    sb.setHeight(1.8 * k)
    sb.setLabelBarSpace(1 * k)
    sb.setTextFormat(tfmt(5.5 * k))
    sb.setLineWidth(0.2)
    sb.setFrameEnabled(False)
    sb.setBackgroundEnabled(False)
    place(sb, sx + sw * 0.05, cy + ch * 0.30 + pad, sw * 0.9, ch * 0.70 - 2 * pad)
    sb.update()
    sb.resizeToMinimumWidth()
    sb.attemptMove(QgsLayoutPoint(sx + (sw - sb.rect().width()) / 2, cy + ch * 0.30 + pad * 1.5))

    # ---------------- Informações cartográficas ----------------
    cx, cy, cw, ch = cells['carto']
    conv = ("with_variable('c', transform(map_get(" + MV + ", 'map_extent_center'), "
            "map_get(" + MV + ", 'map_crs'), 'EPSG:4674'), "
            "with_variable('g', degrees(atan(tan(radians(x(@c) + 57)) * sin(radians(y(@c))))), "
            "with_variable('m', abs(@g) * 60, "
            "if(@g < 0, '-', '') || floor(@m / 60) || '° ' || lpad(floor(@m - floor(@m / 60) * 60), 2, '0') "
            "|| ''' ' || lpad(round((@m - floor(@m)) * 60), 2, '0') || '\"')))")
    th = 3.2 * k
    label(L, 'SISTEMA DE REFERÊNCIA', cx + pad, cy + pad, cw - 2 * pad, th, 5.5 * k, True,
          Qt.AlignLeft, Qt.AlignVCenter, 'Título sistema de referência')
    label(L, 'Projeção Universal Transversa de Mercator – UTM\n'
             'Datum horizontal: SIRGAS 2000 – Fuso 21 Sul\n'
             'Meridiano Central: 57° W Gr.  |  ' + f"[% map_get({MV}, 'map_crs') %]\n"
             'Datum vertical: Imbituba – SC\n'
             'Convergência meridiana (centro): [% ' + conv + ' %]\n'
             "Declinação magnética ([% format_date(now(), 'MM/yyyy') %]): [% " + DECL + " %]"
             " – cresce 0°09' W/ano (WMM-2025)",
          cx + pad, cy + pad + th, cw - 2 * pad, ch - 2 * pad - th, 5.5 * k, False, Qt.AlignLeft, Qt.AlignTop,
          'Informações cartográficas')

    # ---------------- Fonte / créditos / folha (carimbo) ----------------
    cx, cy, cw, ch = cells['credits']
    rb = ch * 0.38                                   # faixa inferior: campos do carimbo
    ra = ch - rb                                     # faixa superior: fonte + marca
    # marca SEPLAN/Prefeitura à direita, centralizada na faixa superior
    lw = min(cw * 0.34, (ra - 2 * pad) * 1390 / 245)
    lhh = lw * 245 / 1390
    pic(L, LOGO_SEPLAN, cx + cw - pad - lw, cy + (ra - lhh) / 2, lw, lhh, 'Marca SEPLAN / Prefeitura')
    label(L, '<b>FONTE:</b> Prefeitura de Dourados – SEPLAN (cadastro e aerolevantamento 2018); '
             'IBGE (limites). <b>CONTATO:</b> [% @contato %]',
          cx + pad, cy + pad, cw - lw - 3 * pad, ra - 2 * pad, 5.2 * k, False, Qt.AlignLeft, Qt.AlignVCenter,
          'Fonte dos dados', rich=True)
    # campos do carimbo
    campos = [('RESPONSÁVEL TÉCNICO', '[% @rt_nome %] – [% @rt_titulo %]\n[% @rt_registro %]\n[% @rt_art %]', .56),
              ('DATA', "[% format_date(now(), 'dd/MM/yyyy') %]", .18),
              ('FORMATO', fmt, .13),
              ('FOLHA', '01/01', .13)]
    fx = cx
    for cap, val, frac in campos:
        fw = cw * frac
        rect(L, fx, cy + ra, fw, rb, sw=0.25, iid=f'Campo {cap.lower()}')
        label(L, cap, fx + pad * 0.7, cy + ra + pad * 0.5, fw - 1.4 * pad, rb * 0.36, 3.8 * k, False,
              Qt.AlignLeft, Qt.AlignTop, f'Rótulo {cap.lower()}')
        multi = '\n' in val
        label(L, val, fx + pad * 0.7, cy + ra + rb * 0.30, fw - 1.4 * pad, rb * 0.70 - pad * 0.4,
              (4.3 if multi else 5.5) * k, not multi, Qt.AlignHCenter, Qt.AlignVCenter, f'Valor {cap.lower()}')
        fx += fw

    L.refresh()
    return nome, mp.scale(), step


def criar_layouts(extensao, projeto=None, pasta_logos=None, formatos=None, variaveis=None):
    """Cria/recria os layouts. Retorna [(nome, escala, passo_grade_geo_s), ...].

    extensao     QgsRectangle no SRC do projeto (ex.: iface.mapCanvas().extent()) – área do mapa principal.
    projeto      QgsProject (padrão: QgsProject.instance()).
    pasta_logos  pasta com brasao_dourados.png, logo_geodourados.png, logo_seplan_prefeitura.jpg, norte.png
                 (padrão: ./logos ao lado deste arquivo).
    formatos     subconjunto de FORMATOS (padrão: os 7).
    variaveis    sobrescreve VARS (responsável técnico/contato) – gravadas como variáveis do projeto.
    """
    global P, LM, EXT, VISIVEIS, LOGO_BRASAO, LOGO_GEO, LOGO_SEPLAN, LOGO_NORTE
    P = projeto or QgsProject.instance()
    LM = P.layoutManager()
    EXT = QgsRectangle(extensao)
    pasta = pasta_logos or os.path.join(AQUI, 'logos')
    LOGO_BRASAO = os.path.join(pasta, 'brasao_dourados.png')
    LOGO_GEO = os.path.join(pasta, 'logo_geodourados.png')
    LOGO_SEPLAN = os.path.join(pasta, 'logo_seplan_prefeitura.jpg')
    LOGO_NORTE = os.path.join(pasta, 'norte.png')
    faltando = [c for c in (LOGO_BRASAO, LOGO_GEO, LOGO_SEPLAN, LOGO_NORTE) if not os.path.exists(c)]
    if faltando:
        raise FileNotFoundError('Logos não encontrados: ' + ', '.join(faltando))
    for k, v in dict(VARS, **(variaveis or {})).items():
        if not QgsExpressionContextUtils.projectScope(P).hasVariable(k) or variaveis:
            QgsExpressionContextUtils.setProjectVariable(P, k, v)
    VISIVEIS = criar_tema()
    return [build(*f) for f in (formatos or FORMATOS)]
