"""Cortina (swipe) para comparar duas imagens no mapa: satélite de anos diferentes, MapBiomas, Sentinel-2 sem nuvens...

Tudo online (nada é baixado). A camada da DIREITA/abaixo é desenhada normalmente pelo mapa; a da ESQUERDA/acima é
desenhada por um item sobre o mapa, recortado até a linha, que pode ser arrastada com o mouse.
"""
import datetime
import json
import os
import re
import urllib.parse
import urllib.request

from qgis.core import (QgsApplication, QgsMapRendererParallelJob, QgsProject, QgsRasterLayer, QgsRectangle,
                       QgsMapLayer)
from qgis.gui import QgsMapCanvasItem
from qgis.PyQt.QtCore import QEvent, QObject, QPointF, QRectF, Qt
from qgis.PyQt.QtGui import QBrush, QColor, QPen
from qgis.PyQt.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton,
                                 QSlider, QVBoxLayout)

from . import mapbiomas
from .sync import HEADERS

WAYBACK_CONFIG = "https://s3-us-west-2.amazonaws.com/config.maptiles.arcgis.com/waybackconfig.json"
GRUPO = "Comparar imagens (swipe)"
PROP = "mapabase/comparar"

FONTES = [
    ("wayback", "Esri World Imagery Wayback (histórico de imagens)"),
    ("mapbiomas", "MapBiomas Coleção 11 (1985–2025)"),
    ("eox", "Sentinel-2 sem nuvens – EOX (anual)"),
    ("gibs", "NASA GIBS – HLS 30 m (diário)"),
    ("projeto", "Camada raster do projeto"),
]


# ---------------------------------------------------------------- versões de cada fonte
_wayback = None


def _json_cache(url, nome, dias=7):
    pasta = os.path.join(QgsApplication.qgisSettingsDirPath(), "mapabase_cache")
    os.makedirs(pasta, exist_ok=True)
    arq = os.path.join(pasta, nome)
    velho = not os.path.exists(arq) or (datetime.datetime.now().timestamp() - os.path.getmtime(arq)) > dias * 86400
    if velho:
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                with open(arq, "wb") as f:
                    f.write(r.read())
        except Exception:
            if not os.path.exists(arq):
                raise
    with open(arq, encoding="utf-8") as f:
        return json.load(f)


def wayback():
    """[(id, 'AAAA-MM-DD', dict)] do mais novo para o mais antigo."""
    global _wayback
    if _wayback is None:
        itens = []
        for k, v in _json_cache(WAYBACK_CONFIG, "waybackconfig.json").items():
            m = re.search(r"(\d{4}-\d{2}-\d{2})", v.get("itemTitle", ""))
            if m:
                itens.append((k, m.group(1), v))
        _wayback = sorted(itens, key=lambda t: t[1], reverse=True)
    return _wayback


def versoes(fonte, project):
    """[(rótulo, valor)] da fonte, da mais nova para a mais antiga."""
    if fonte == "wayback":
        return [(d, k) for k, d, _v in wayback()]
    if fonte == "mapbiomas":
        return [(str(a), a) for a in range(mapbiomas.ANOS[1], mapbiomas.ANOS[0] - 1, -1)]
    if fonte == "eox":
        fim = datetime.date.today().year - 1
        return [(str(a), a) for a in range(fim, 2015, -1) if a != 2017]
    if fonte == "gibs":
        hoje = datetime.date.today()
        return [((hoje - datetime.timedelta(days=n)).isoformat(),) * 2 for n in range(3, 401)]
    if fonte == "projeto":
        return [(l.name(), l.id()) for l in project.mapLayers().values()
                if isinstance(l, QgsRasterLayer) and l.customProperty(PROP) is None
                and l.customProperty(mapbiomas.PROP) is None]
    return []


def _xyz(url, nome, zmax):
    fonte = f"type=xyz&url={urllib.parse.quote(url, safe=':/')}&zmax={zmax}&zmin=0"
    return QgsRasterLayer(fonte, nome, "wms")


def criar_camada(fonte, valor, project):
    """(camada, é_do_projeto, informação) ou (None, False, mensagem de erro)."""
    if fonte == "projeto":
        camada = project.mapLayer(valor)
        return (camada, True, camada.name()) if camada else (None, False, "Camada não encontrada.")
    if fonte == "wayback":
        item = next((v for k, d, v in wayback() if k == valor), None)
        if item is None:
            return None, False, "Versão do Wayback não encontrada."
        url = item["itemURL"].replace("{level}", "{z}").replace("{row}", "{y}").replace("{col}", "{x}")
        data = re.search(r"(\d{4}-\d{2}-\d{2})", item["itemTitle"]).group(1)
        camada = _xyz(url, f"Wayback {data}", 23)
        info = f"Esri World Imagery Wayback, versão de {data} (a data é da publicação; a imagem pode ser mais antiga)."
    elif fonte == "mapbiomas":
        camada = QgsRasterLayer(mapbiomas._fonte(valor), f"MapBiomas Col. 11 – {valor}", "gdal")
        if camada.isValid():
            mapbiomas._estilo(camada)
        info = f"MapBiomas Coleção 11, {valor} (CC BY 4.0)."
    elif fonte == "eox":
        nome = "s2cloudless" if valor == 2016 else f"s2cloudless-{valor}"
        url = f"https://tiles.maps.eox.at/wmts/1.0.0/{nome}_3857/default/g/{{z}}/{{y}}/{{x}}.jpg"
        camada = _xyz(url, f"Sentinel-2 EOX {valor}", 15)
        info = (f"Sentinel-2 sem nuvens {valor} – © EOX IT Services GmbH, contém dados Copernicus Sentinel; "
                + ("CC BY 4.0." if valor == 2016 else "CC BY-NC-SA 4.0 (uso não comercial)."))
    elif fonte == "gibs":
        url = ("https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/HLS_S30_Nadir_BRDF_Adjusted_Reflectance/default/"
               f"{valor}/GoogleMapsCompatible_Level12/{{z}}/{{y}}/{{x}}.jpg")
        camada = _xyz(url, f"NASA HLS {valor}", 12)
        info = f"NASA GIBS – HLS Sentinel-2 de {valor}. Dias sem passagem ou com nuvem aparecem vazios."
    else:
        return None, False, "Fonte desconhecida."
    if not camada.isValid():
        return None, False, "Não foi possível abrir a imagem (sem internet ou serviço fora do ar)."
    camada.setCustomProperty(PROP, fonte)
    return camada, False, info


# ---------------------------------------------------------------- swipe
class SwipeItem(QgsMapCanvasItem):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.camada_esq = None
        self.camada_dir = None
        self.imagem = None
        self.posicao = 0.5
        self.vertical = True
        self.job = None
        self.setZValue(1)
        canvas.mapCanvasRefreshed.connect(self.renderizar)
        canvas.extentsChanged.connect(self._invalidar)

    def desligar(self):
        try:
            self.canvas.mapCanvasRefreshed.disconnect(self.renderizar)
            self.canvas.extentsChanged.disconnect(self._invalidar)
        except Exception:
            pass
        if self.job:
            self.job.cancelWithoutBlocking()
        self.canvas.scene().removeItem(self)

    def _invalidar(self):
        self.imagem = None
        self.update()

    def renderizar(self):
        if not self.camada_esq:
            return
        if self.job:
            self.job.cancelWithoutBlocking()
        ms = self.canvas.mapSettings()
        camadas = list(ms.layers())
        if self.camada_dir in camadas:
            camadas[camadas.index(self.camada_dir)] = self.camada_esq
        else:
            camadas.append(self.camada_esq)
        ms.setLayers(camadas)
        job = QgsMapRendererParallelJob(ms)
        extent = ms.visibleExtent()
        job.finished.connect(lambda j=job, e=extent: self._pronto(j, e))
        self.job = job
        job.start()

    def _pronto(self, job, extent):
        if job is not self.job:
            return
        self.imagem = job.renderedImage()
        self.imagem.setDevicePixelRatio(self.canvas.mapSettings().devicePixelRatio())
        self.job = None
        self.setRect(QgsRectangle(extent))
        self.update()

    def paint(self, painter, *_args):
        r = self.boundingRect()
        w, h = r.width(), r.height()
        if self.vertical:
            corte = w * self.posicao
            alvo = QRectF(0, 0, corte, h)
        else:
            corte = h * self.posicao
            alvo = QRectF(0, 0, w, corte)
        if self.imagem is not None:
            dpr = self.imagem.devicePixelRatio()
            painter.drawImage(alvo, self.imagem, QRectF(alvo.x() * dpr, alvo.y() * dpr,
                                                        alvo.width() * dpr, alvo.height() * dpr))
        a, b = (QPointF(corte, 0), QPointF(corte, h)) if self.vertical else (QPointF(0, corte), QPointF(w, corte))
        painter.setPen(QPen(QColor(0, 0, 0, 180), 4))
        painter.drawLine(a, b)
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawLine(a, b)
        meio = QPointF(corte, h / 2) if self.vertical else QPointF(w / 2, corte)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.drawEllipse(meio, 9, 9)
        painter.drawText(QRectF(meio.x() - 9, meio.y() - 9, 18, 18), Qt.AlignmentFlag.AlignCenter, "⇔" if self.vertical else "⇕")


class ArrastoLinha(QObject):
    """Arrastar a linha da cortina com o mouse, com qualquer ferramenta ativa (clique fora da linha segue normal)."""
    TOLERANCIA = 8

    def __init__(self, canvas, item, ao_mover):
        super().__init__(canvas)
        self.canvas = canvas
        self.item = item
        self.ao_mover = ao_mover
        self.arrastando = False
        self.cursor_trocado = False
        canvas.viewport().installEventFilter(self)

    def remover(self):
        self.canvas.viewport().removeEventFilter(self)
        self._cursor(False)

    def _perto(self, p):
        if self.item.vertical:
            return abs(p.x() - self.item.posicao * self.canvas.width()) <= self.TOLERANCIA
        return abs(p.y() - self.item.posicao * self.canvas.height()) <= self.TOLERANCIA

    def _cursor(self, sim):
        if sim and not self.cursor_trocado:
            QApplication.setOverrideCursor(Qt.CursorShape.SplitHCursor if self.item.vertical else Qt.CursorShape.SplitVCursor)
            self.cursor_trocado = True
        elif not sim and self.cursor_trocado:
            QApplication.restoreOverrideCursor()
            self.cursor_trocado = False

    def _mover(self, p):
        self.item.posicao = min(max((p.x() / self.canvas.width()) if self.item.vertical
                                    else (p.y() / self.canvas.height()), 0.0), 1.0)
        self.item.update()
        self.ao_mover(self.item.posicao)

    def eventFilter(self, _obj, e):
        tipo = e.type()
        if tipo == QEvent.Type.MouseButtonPress and e.button() == Qt.MouseButton.LeftButton and self._perto(e.pos()):
            self.arrastando = True
            return True
        if tipo == QEvent.Type.MouseMove:
            if self.arrastando:
                self._mover(e.pos())
                return True
            self._cursor(self._perto(e.pos()))
        if tipo == QEvent.Type.MouseButtonRelease and self.arrastando:
            self.arrastando = False
            return True
        if tipo == QEvent.Type.Leave and not self.arrastando:
            self._cursor(False)
        return False


# ---------------------------------------------------------------- painel
class _Lado(QVBoxLayout):
    def __init__(self, titulo, fonte_padrao, ao_mudar, projeto):
        super().__init__()
        self.projeto = projeto
        self.ao_mudar = ao_mudar
        lb = QLabel(f"<b>{titulo}</b>")
        self.addWidget(lb)
        self.cb_fonte = QComboBox()
        for chave, nome in FONTES:
            self.cb_fonte.addItem(nome, chave)
        self.cb_fonte.setCurrentIndex(max(0, [c for c, _ in FONTES].index(fonte_padrao)))
        self.cb_versao = QComboBox()
        self.addWidget(self.cb_fonte)
        self.addWidget(self.cb_versao)
        self.lb_info = QLabel("")
        self.lb_info.setWordWrap(True)
        self.lb_info.setStyleSheet("font-size:9px;color:#555;")
        self.addWidget(self.lb_info)
        self.cb_fonte.currentIndexChanged.connect(self._fonte_mudou)
        self.cb_versao.currentIndexChanged.connect(lambda _=None: self.ao_mudar(self))
        self._fonte_mudou()

    def fonte(self):
        return self.cb_fonte.currentData()

    def valor(self):
        return self.cb_versao.currentData()

    def _fonte_mudou(self, *_):
        self.cb_versao.blockSignals(True)
        self.cb_versao.clear()
        try:
            itens = versoes(self.fonte(), self.projeto)
        except Exception as e:
            itens = []
            self.lb_info.setText(f"Não foi possível listar as versões ({e}).")
        for rotulo, valor in itens:
            self.cb_versao.addItem(rotulo, valor)
        self.cb_versao.blockSignals(False)
        self.ao_mudar(self)

    def definir(self, fonte, valor):
        """Escolhe fonte e versão sem disparar a atualização do mapa."""
        self.cb_fonte.blockSignals(True)
        self.cb_versao.blockSignals(True)
        self.cb_fonte.setCurrentIndex(max(0, self.cb_fonte.findData(fonte)))
        self.cb_versao.clear()
        for rotulo, v in versoes(self.fonte(), self.projeto):
            self.cb_versao.addItem(rotulo, v)
        self.cb_versao.setCurrentIndex(max(0, self.cb_versao.findData(valor)))
        self.cb_fonte.blockSignals(False)
        self.cb_versao.blockSignals(False)


class ComparadorDialog(QDialog):
    def __init__(self, iface):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.projeto = QgsProject.instance()
        self.setWindowTitle("Comparar imagens (cortina)")
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.cam_esq = self.cam_dir = None
        self.dir_do_projeto = self.esq_do_projeto = False
        self.item = SwipeItem(self.canvas)
        self.arrasto = ArrastoLinha(self.canvas, self.item, self._posicao_mudou_no_mapa)
        v = QVBoxLayout(self)
        self.lado_esq = _Lado("Esquerda / acima", "wayback", self._lado_mudou, self.projeto)
        self.lado_dir = _Lado("Direita / abaixo", "wayback", self._lado_mudou, self.projeto)
        # padrão: Wayback mais novo × um ano mais antigo da lista
        if self.lado_esq.cb_versao.count() > 8:
            self.lado_esq.cb_versao.setCurrentIndex(min(40, self.lado_esq.cb_versao.count() - 1))
        v.addLayout(self.lado_esq)
        v.addLayout(self.lado_dir)
        self.sl = QSlider(Qt.Orientation.Horizontal)
        self.sl.setRange(0, 100)
        self.sl.setValue(50)
        self.sl.valueChanged.connect(self._slider)
        v.addWidget(self.sl)
        lin = QHBoxLayout()
        self.chk_vertical = QCheckBox("Linha vertical")
        self.chk_vertical.setChecked(True)
        self.chk_vertical.toggled.connect(self._orientacao)
        b_troca = QPushButton("⇄ Trocar lados")
        b_troca.clicked.connect(self._trocar)
        lin.addWidget(self.chk_vertical)
        lin.addWidget(b_troca)
        v.addLayout(lin)
        self.lb_msg = QLabel("Arraste a linha no mapa ou use o controle acima.")
        self.lb_msg.setWordWrap(True)
        self.lb_msg.setStyleSheet("font-size:9px;color:#555;")
        v.addWidget(self.lb_msg)
        self.resize(360, 420)
        self._aplicar()

    # --- camadas
    def _lado_mudou(self, _lado):
        if getattr(self, "item", None) is not None and getattr(self, "lado_dir", None) is not None:
            self._aplicar()

    def _grupo(self):
        raiz = self.projeto.layerTreeRoot()
        g = raiz.findGroup(GRUPO)
        if g is None:
            # acima dos mapas de fundo (primeira camada raster), abaixo dos vetores
            pos = len(raiz.children())
            for i, no in enumerate(raiz.children()):
                if not no.nodeType() == 0 and no.layer() is not None and isinstance(no.layer(), QgsRasterLayer):
                    pos = i
                    break
            g = raiz.insertGroup(pos, GRUPO)
        return g

    def _remover_temporarias(self):
        for cam, do_projeto in ((self.cam_dir, self.dir_do_projeto), (self.cam_esq, self.esq_do_projeto)):
            if cam is not None and not do_projeto:
                try:
                    self.projeto.removeMapLayer(cam.id())
                except Exception:
                    pass
        g = self.projeto.layerTreeRoot().findGroup(GRUPO)
        if g is not None and not g.children():
            self.projeto.layerTreeRoot().removeChildNode(g)
        self.cam_dir = self.cam_esq = None

    def _aplicar(self):
        self._remover_temporarias()
        cam_e, e_proj, info_e = criar_camada(self.lado_esq.fonte(), self.lado_esq.valor(), self.projeto)
        cam_d, d_proj, info_d = criar_camada(self.lado_dir.fonte(), self.lado_dir.valor(), self.projeto)
        self.lado_esq.lb_info.setText(info_e)
        self.lado_dir.lb_info.setText(info_d)
        if cam_e is None or cam_d is None:
            self.item.camada_esq = self.item.camada_dir = None
            self.item._invalidar()
            self.canvas.refresh()
            return
        if not e_proj:
            self.projeto.addMapLayer(cam_e, False)          # fica fora da árvore: só o item a desenha
        if not d_proj:
            self.projeto.addMapLayer(cam_d, False)
            self._grupo().insertLayer(0, cam_d)
        else:
            no = self.projeto.layerTreeRoot().findLayer(cam_d.id())
            if no is not None:
                no.setItemVisibilityCheckedParentRecursive(True)
        self.cam_esq, self.cam_dir = cam_e, cam_d
        self.esq_do_projeto, self.dir_do_projeto = e_proj, d_proj
        self.item.camada_esq, self.item.camada_dir = cam_e, cam_d
        self.item._invalidar()
        self.canvas.refresh()

    # --- controles
    def _slider(self, valor):
        self.item.posicao = valor / 100.0
        self.item.update()

    def _posicao_mudou_no_mapa(self, pos):
        self.sl.blockSignals(True)
        self.sl.setValue(int(round(pos * 100)))
        self.sl.blockSignals(False)

    def _orientacao(self, vertical):
        self.item.vertical = vertical
        self.item.update()

    def _trocar(self):
        e = (self.lado_esq.fonte(), self.lado_esq.valor())
        d = (self.lado_dir.fonte(), self.lado_dir.valor())
        self.lado_esq.definir(*d)
        self.lado_dir.definir(*e)
        self._aplicar()

    def closeEvent(self, e):
        try:
            self.arrasto.remover()
            self.item.desligar()
            self._remover_temporarias()
            self.canvas.refresh()
        except Exception:
            pass
        super().closeEvent(e)


_aberto = None


def abrir(iface):
    """Abre (ou traz para a frente) o painel da cortina."""
    global _aberto
    try:
        if _aberto is not None and _aberto.isVisible():
            _aberto.raise_()
            return _aberto
    except RuntimeError:
        pass
    _aberto = ComparadorDialog(iface)
    _aberto.show()
    return _aberto
