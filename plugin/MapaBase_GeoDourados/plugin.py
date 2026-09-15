import os

from qgis.PyQt.QtCore import QSize, Qt, QThread, pyqtSignal
from qgis.PyQt.QtGui import QColor, QIcon, QPainter, QPixmap
from qgis.PyQt.QtWidgets import QAction, QToolBar

PLUGIN_DIR = os.path.dirname(__file__)


class CheckUpdateWorker(QThread):
    resultado = pyqtSignal(bool, str)

    def run(self):
        from .sync import verificar_atualizacao_disponivel
        tem, msg = verificar_atualizacao_disponivel()
        self.resultado.emit(tem, msg)


class MapaBaseGeoDouradosPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None
        self._check_worker = None
        self._icon_normal = None
        self._icon_com_aviso = None

    def initGui(self):
        self._icon_normal = QIcon(os.path.join(PLUGIN_DIR, "icons", "icon.png"))
        self._icon_com_aviso = self._gerar_icone_com_aviso()

        self.action = QAction(self._icon_normal, "Mapa Base - GeoDourados", self.iface.mainWindow())
        self.action.setToolTip("Mapa Base Digital da Cidade de Dourados - MS")
        self.action.triggered.connect(self.run)

        self.iface.addPluginToMenu("Mapa Base - GeoDourados", self.action)

        db_toolbar = self.iface.mainWindow().findChild(QToolBar, "mDatabaseToolBar")
        if db_toolbar:
            db_toolbar.addAction(self.action)
        else:
            self._toolbar = self.iface.addToolBar("Mapa Base - GeoDourados")
            self._toolbar.setObjectName("MapaBaseGeoDouradosToolbar")
            self._toolbar.setIconSize(QSize(24, 24))
            self._toolbar.addAction(self.action)

        # Checa atualização em segundo plano, sem travar a abertura do QGIS.
        self._checar_atualizacao_em_segundo_plano()

    def unload(self):
        self.iface.removePluginMenu("Mapa Base - GeoDourados", self.action)
        db_toolbar = self.iface.mainWindow().findChild(QToolBar, "mDatabaseToolBar")
        if db_toolbar:
            db_toolbar.removeAction(self.action)
        if hasattr(self, "_toolbar") and self._toolbar:
            self._toolbar.deleteLater()
            self._toolbar = None

    def run(self):
        from .dialog import MapaBaseDialog
        if not self.dialog:
            self.dialog = MapaBaseDialog(self.iface, on_fechar=self._checar_atualizacao_em_segundo_plano)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
        self.dialog.atualizar_status()

    # ── Indicador de atualização disponível (badge no ícone) ───────────────
    def _gerar_icone_com_aviso(self):
        base = QPixmap(os.path.join(PLUGIN_DIR, "icons", "icon.png"))
        if base.isNull():
            return self._icon_normal
        pix = QPixmap(base)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        raio = int(pix.width() * 0.32)
        x = pix.width() - raio
        y = 0
        painter.setBrush(QColor("#e53e3e"))
        painter.setPen(QColor("white"))
        painter.drawEllipse(x, y, raio, raio)
        painter.end()
        return QIcon(pix)

    def _checar_atualizacao_em_segundo_plano(self):
        if self._check_worker and self._check_worker.isRunning():
            return
        self._check_worker = CheckUpdateWorker()
        self._check_worker.resultado.connect(self._on_resultado_checagem)
        self._check_worker.start()

    def _on_resultado_checagem(self, tem_atualizacao, _msg):
        if not self.action:
            return
        self.action.setIcon(self._icon_com_aviso if tem_atualizacao else self._icon_normal)
        self.action.setToolTip(
            "Mapa Base - GeoDourados — atualização disponível!"
            if tem_atualizacao
            else "Mapa Base Digital da Cidade de Dourados - MS"
        )
