import os

from qgis.core import Qgis
from qgis.PyQt.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal
from qgis.PyQt.QtGui import QColor, QIcon, QPainter, QPixmap
from qgis.PyQt.QtWidgets import QAction, QDockWidget, QToolBar

PLUGIN_DIR = os.path.dirname(__file__)


class CheckUpdateWorker(QThread):
    resultado = pyqtSignal(bool, bool, str)

    def run(self):
        from .sync import verificar_atualizacao_disponivel, verificar_atualizacao_plugin
        base, _msg = verificar_atualizacao_disponivel()
        plugin, versao_nova, _local = verificar_atualizacao_plugin()
        self.resultado.emit(base, plugin, versao_nova or "")


class MapaBaseGeoDouradosPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None
        self._check_worker = None
        self._icon_normal = None
        self._icon_com_aviso = None
        self._avisou_plugin = False
        self._atalho_f4 = None
        self._avisou_base = False

    def initGui(self):
        self._icon_normal = QIcon(os.path.join(PLUGIN_DIR, "icons", "icon.png"))
        self._icon_com_aviso = self._gerar_icone_com_aviso()

        self.action = QAction(self._icon_normal, "Mapa Base - GeoDourados", self.iface.mainWindow())
        self.action.setToolTip("Mapa Base Digital da Cidade de Dourados - MS")
        self.action.triggered.connect(self.run)

        self.iface.addPluginToMenu("Mapa Base - GeoDourados", self.action)

        # Barra de ferramentas própria e separada (não mesclada em nenhuma
        # barra existente), para poder ser arrastada/reposicionada livremente
        # — mesmo padrão usado no plugin GeoDourados - Cadastro Fiscal.
        self._toolbar = self.iface.addToolBar("Mapa Base - GeoDourados")
        self._toolbar.setObjectName("MapaBaseGeoDouradosToolbar")
        self._toolbar.setIconSize(QSize(24, 24))
        self._toolbar.addAction(self.action)

        # Painel acoplado à direita (começa escondido; o botão da barra abre).
        from .dialog import MapaBaseDialog
        self.dialog = MapaBaseDialog(self.iface, on_fechar=self._checar_atualizacao_em_segundo_plano)
        self.dock = QDockWidget("Mapa Base - GeoDourados (Offline)", self.iface.mainWindow())
        self.dock.setObjectName("MapaBaseGeoDouradosDock")
        self.dock.setWidget(self.dialog)
        self.dialog.dock = self.dock
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.dock.hide()
        self.dock.visibilityChanged.connect(self._on_visibilidade_dock)

        # Atalho F4 (camada de lotes + ferramenta de seleção): registrado depois que os
        # demais plugins carregaram, pra não colidir com um F4 que já exista.
        QTimer.singleShot(4000, self._registrar_f4)

        # Checa atualização em segundo plano, sem travar a abertura do QGIS.
        self._checar_atualizacao_em_segundo_plano()

    def _registrar_f4(self):
        """F4 = ativa a camada de lotes e a ferramenta "Selecionar feição". Se outra ação
        (ex.: o plugin interno Cadastro Fiscal) já usa F4, não registra: atalho ambíguo faz
        o Qt não disparar NENHUM dos dois."""
        try:
            from qgis.PyQt.QtGui import QKeySequence
            from qgis.PyQt.QtWidgets import QShortcut
            tecla = QKeySequence("F4")
            principal = self.iface.mainWindow()
            for acao in principal.findChildren(QAction):
                if acao is not self.action and acao.shortcut() == tecla:
                    return
            for atalho in principal.findChildren(QShortcut):
                if atalho.key() == tecla:
                    return
            self._atalho_f4 = QShortcut(tecla, principal)
            self._atalho_f4.setContext(Qt.ApplicationShortcut)
            self._atalho_f4.activated.connect(self.selecionar_lotes)
        except Exception:
            self._atalho_f4 = None

    def selecionar_lotes(self):
        from .selecao import ativar_selecao_lotes
        ok, msg = ativar_selecao_lotes(self.iface)
        barra = self.iface.messageBar()
        (barra.pushInfo if ok else barra.pushWarning)("Mapa Base", msg)

    def unload(self):
        self.iface.removePluginMenu("Mapa Base - GeoDourados", self.action)
        if self._atalho_f4 is not None:
            self._atalho_f4.setEnabled(False)
            self._atalho_f4.deleteLater()
            self._atalho_f4 = None
        if getattr(self, "dock", None):
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
        if hasattr(self, "_toolbar") and self._toolbar:
            self._toolbar.deleteLater()
            self._toolbar = None

    def run(self):
        # Botão da barra de ferramentas: abre o painel (acoplado à direita) ou recolhe.
        if self.dock.isVisible():
            self.dock.hide()
        else:
            self.dock.show()
            self.dock.raise_()

    def _on_visibilidade_dock(self, visivel):
        if not visivel:
            self._checar_atualizacao_em_segundo_plano()

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

    def _on_resultado_checagem(self, base_nova, plugin_novo, versao_plugin):
        if not self.action:
            return
        tem = base_nova or plugin_novo
        self.action.setIcon(self._icon_com_aviso if tem else self._icon_normal)

        partes = []
        if plugin_novo:
            partes.append(f"nova versão do plugin ({versao_plugin})")
        if base_nova:
            partes.append("nova base de dados")
        self.action.setToolTip(
            "Mapa Base - GeoDourados — " + " e ".join(partes) + " disponível!"
            if tem
            else "Mapa Base Digital da Cidade de Dourados - MS"
        )

        # Aviso visível na barra de mensagens do QGIS, uma vez por sessão por
        # tipo de novidade (o ponto vermelho sozinho passa despercebido).
        if plugin_novo and not self._avisou_plugin:
            self._avisou_plugin = True
            self.iface.messageBar().pushMessage(
                "Mapa Base - GeoDourados",
                f"Nova versão do plugin disponível ({versao_plugin}). Abra o plugin e clique em \"Atualizar plugin\".",
                level=Qgis.Warning, duration=15)
        elif base_nova and not self._avisou_base:
            self._avisou_base = True
            self.iface.messageBar().pushMessage(
                "Mapa Base - GeoDourados",
                "Há uma nova base de dados publicada. Abra o plugin para atualizar.",
                level=Qgis.Info, duration=10)
