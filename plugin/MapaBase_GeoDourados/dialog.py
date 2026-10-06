import os

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QMessageBox, QFrame, QListWidget, QInputDialog, QLineEdit, QScrollArea,
    QWidget, QComboBox, QCheckBox, QListWidgetItem, QAbstractItemView, QApplication,
)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from qgis.PyQt.QtGui import QIcon, QPixmap, QDesktopServices

PLUGIN_DIR = os.path.dirname(__file__)


class DownloadWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def __init__(self, dest_path):
        super().__init__()
        self.dest_path = dest_path

    def run(self):
        from .sync import baixar_gpkg
        ok, err = baixar_gpkg(self.dest_path, progress_callback=lambda v, m: self.progress.emit(v, m))
        self.finished.emit(ok, err)


class MapaBaseDialog(QWidget):
    def __init__(self, iface, on_fechar=None):
        super().__init__()
        self.iface = iface
        self._on_fechar = on_fechar
        self.setWindowTitle("Mapa Base - GeoDourados")
        self.setWindowIcon(QIcon(os.path.join(PLUGIN_DIR, "icons", "icon.png")))
        self.setMinimumWidth(340)
        self._itens_busca = []
        self._altura_expandida = None
        self._primeira_exibicao = True
        self._largura_antes = None
        self.dock = None
        self._build_ui()

    def showEvent(self, event):
        super().showEvent(event)
        # Checagem de rede só depois de pintar a tela (não trava a abertura).
        QTimer.singleShot(50, self.atualizar_status)
        if self._primeira_exibicao:
            self._primeira_exibicao = False
            QTimer.singleShot(100, self._on_ajustar)

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.conteudo = QWidget()
        corpo = QVBoxLayout(self.conteudo)
        corpo.setContentsMargins(8, 6, 8, 8)
        corpo.setSpacing(5)

        header = QFrame()
        header.setStyleSheet("background-color: #1a365d;")
        header.setFixedHeight(44)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(10, 4, 10, 4)
        brasao_path = os.path.join(PLUGIN_DIR, "icons", "brasao.png")
        if os.path.exists(brasao_path):
            lbl = QLabel()
            lbl.setPixmap(QPixmap(brasao_path).scaled(30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            hl.addWidget(lbl)
        tl = QLabel("Mapa Base Digital da Cidade de Dourados - MS")
        tl.setStyleSheet("color:white;font-size:9px;font-weight:bold;")
        tl.setWordWrap(True)
        hl.addWidget(tl)
        hl.addStretch()
        from .sync import versao_plugin_local
        versao = versao_plugin_local()
        if versao:
            lbl_versao = QLabel(f"v{versao}")
            lbl_versao.setStyleSheet("color:#cbd5e0;font-size:9px;")
            lbl_versao.setToolTip("Versão instalada do plugin")
            hl.addWidget(lbl_versao)
        estilo_btn = ("QPushButton{color:white;background:transparent;border:none;font-size:13px;}"
                      "QPushButton:hover{background:#2c5f8a;border-radius:3px;}")
        for attr, texto, dica, slot in (
            ("btn_recolher", "▾", "Recolher o painel (reabra pelo botão Mapa Base na barra de ferramentas)", self._on_recolher),
            ("btn_ajustar", "↕", "Auto ajustar a largura do painel ao conteúdo", self._on_ajustar),
            ("btn_maximizar", "□", "Alargar / restaurar o painel", self._on_maximizar),
        ):
            b = QPushButton(texto)
            b.setToolTip(dica)
            b.setFixedSize(22, 22)
            b.setStyleSheet(estilo_btn)
            b.clicked.connect(slot)
            setattr(self, attr, b)
            hl.addWidget(b)
        self.topo = QWidget()
        topo_lay = QVBoxLayout(self.topo)
        topo_lay.setContentsMargins(8, 8, 8, 0)
        topo_lay.addWidget(header)
        main.addWidget(self.topo)

        # Status
        self.frm_status = QFrame()
        self.frm_status.setStyleSheet("border:1px solid #ccc;border-radius:4px;padding:4px;")
        sl = QHBoxLayout(self.frm_status)
        self.lbl_status = QLabel("Verificando...")
        self.lbl_status.setStyleSheet("font-size:10px;")
        sl.addWidget(self.lbl_status)
        corpo.addWidget(self.frm_status)

        # Aviso de nova versão do PLUGIN (só aparece quando existe)
        self.frm_plugin = QFrame()
        self.frm_plugin.setStyleSheet("border:1px solid #e67e22;background:#fef3e2;border-radius:4px;padding:4px;")
        pl = QVBoxLayout(self.frm_plugin)
        self.lbl_plugin = QLabel("")
        self.lbl_plugin.setWordWrap(True)
        self.lbl_plugin.setStyleSheet("font-size:10px;border:none;background:transparent;")
        pl.addWidget(self.lbl_plugin)
        self.btn_atualizar_plugin = QPushButton("⬆  Atualizar plugin")
        self.btn_atualizar_plugin.setFixedHeight(25)
        self.btn_atualizar_plugin.clicked.connect(self._on_atualizar_plugin)
        pl.addWidget(self.btn_atualizar_plugin)
        self.frm_plugin.setVisible(False)
        corpo.addWidget(self.frm_plugin)

        self.prog_bar = QProgressBar()
        self.prog_bar.setVisible(False)
        self.prog_bar.setFixedHeight(14)
        corpo.addWidget(self.prog_bar)
        self.lbl_prog = QLabel("")
        self.lbl_prog.setAlignment(Qt.AlignCenter)
        self.lbl_prog.setStyleSheet("font-size:9px;color:#555;")
        corpo.addWidget(self.lbl_prog)

        self.btn_atualizar = QPushButton("⬇  Baixar / Atualizar base")
        self.btn_atualizar.setFixedHeight(27)
        self.btn_atualizar.setStyleSheet(
            "QPushButton{background:#1a365d;color:white;border-radius:4px;font-weight:bold;}"
            "QPushButton:hover{background:#2c5f8a;}QPushButton:disabled{background:#aaa;}"
        )
        self.btn_atualizar.clicked.connect(self._on_atualizar)
        corpo.addWidget(self.btn_atualizar)

        self.btn_abrir_oficial = QPushButton("📂  Abrir projeto oficial")
        self.btn_abrir_oficial.setFixedHeight(25)
        self.btn_abrir_oficial.clicked.connect(self._on_abrir_oficial)
        corpo.addWidget(self.btn_abrir_oficial)

        # Busca
        linha_busca = QFrame()
        linha_busca.setFrameShape(QFrame.HLine)
        corpo.addWidget(linha_busca)

        lbl_busca = QLabel("Buscar no mapa")
        lbl_busca.setStyleSheet("font-weight:bold;font-size:10px;color:#1a365d;")
        corpo.addWidget(lbl_busca)

        from .busca import TIPOS
        l1 = QHBoxLayout()
        l1.setSpacing(3)
        self.txt_busca = QLineEdit()
        self.txt_busca.setPlaceholderText("Digite e tecle Enter")
        self.txt_busca.returnPressed.connect(self._on_buscar)
        l1.addWidget(self.txt_busca, 2)
        self.cb_tipo = QComboBox()
        for rotulo, chave in TIPOS:
            self.cb_tipo.addItem(rotulo, chave)
        self.cb_tipo.setToolTip(
            "Inscrição e Matrícula: procuram nos lotes (por prefixo; com 'Exata', o valor completo).\n"
            "Loteamento e Logradouro: pelo nome, em qualquer ordem e sem acento; dão zoom e piscam o contorno.")
        l1.addWidget(self.cb_tipo, 1)
        self.chk_exata = QCheckBox("Exata")
        l1.addWidget(self.chk_exata)
        corpo.addLayout(l1)

        l2 = QHBoxLayout()
        l2.setSpacing(3)
        b_buscar = QPushButton("🔎 Buscar")
        b_buscar.setFixedHeight(24)
        b_buscar.setStyleSheet("QPushButton{background:#1a365d;color:white;border-radius:4px;font-weight:bold;}"
                               "QPushButton:hover{background:#2c5f8a;}")
        b_buscar.clicked.connect(self._on_buscar)
        l2.addWidget(b_buscar)
        b_limpar = QPushButton("Limpar")
        b_limpar.setFixedHeight(24)
        b_limpar.clicked.connect(self._on_limpar_busca)
        l2.addWidget(b_limpar)
        b_sel = QPushButton("Do lote selec.")
        b_sel.setFixedHeight(24)
        b_sel.setToolTip("Mostra o lote que está selecionado no mapa.")
        b_sel.clicked.connect(self._on_lote_selecionado)
        l2.addWidget(b_sel)
        corpo.addLayout(l2)

        self.lbl_busca = QLabel("")
        self.lbl_busca.setWordWrap(True)
        self.lbl_busca.setStyleSheet("font-size:9px;color:#555;")
        corpo.addWidget(self.lbl_busca)

        l3 = QHBoxLayout()
        l3.setSpacing(2)
        self.lista_busca = QListWidget()
        self.lista_busca.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.lista_busca.itemClicked.connect(self._on_resultado_clicado)
        self.lista_busca.itemActivated.connect(self._on_resultado_clicado)
        self.lista_busca.setFixedHeight(60)
        l3.addWidget(self.lista_busca, 1)
        col = QVBoxLayout()
        col.setSpacing(2)
        b_zoom = QPushButton("🔍")
        b_zoom.setToolTip("Zoom em todos os resultados selecionados (Ctrl/Shift+clique para vários).")
        b_zoom.setFixedSize(24, 22)
        b_zoom.clicked.connect(self._on_zoom_selecionados)
        col.addWidget(b_zoom)
        b_alt = QPushButton("↕")
        b_alt.setToolTip("Ajustar a altura da lista ao número de resultados.")
        b_alt.setFixedSize(24, 22)
        b_alt.clicked.connect(self._ajustar_altura_lista)
        col.addWidget(b_alt)
        col.addStretch()
        l3.addLayout(col)
        corpo.addLayout(l3)

        self.btn_tabela = QPushButton("📋  Tabela de atributos")
        self.btn_tabela.setFixedHeight(25)
        self.btn_tabela.setToolTip("Abre a tabela de atributos da camada ativa (ou dos lotes, se nenhuma estiver ativa).")
        self.btn_tabela.clicked.connect(self._on_tabela_atributos)
        corpo.addWidget(self.btn_tabela)

        # Croqui (PDF)
        linha_croqui = QFrame()
        linha_croqui.setFrameShape(QFrame.HLine)
        corpo.addWidget(linha_croqui)

        lbl_croqui = QLabel("Croqui de localização (PDF)")
        lbl_croqui.setStyleSheet("font-weight:bold;font-size:10px;color:#1a365d;")
        corpo.addWidget(lbl_croqui)

        lbl_croqui_info = QLabel("Selecione 1 lote no mapa do projeto oficial e clique:")
        lbl_croqui_info.setStyleSheet("font-size:9px;color:#666;")
        corpo.addWidget(lbl_croqui_info)

        linha_croqui_botoes = QHBoxLayout()
        self.btn_croqui_1000 = QPushButton("🗺  Croqui 1:1000")
        self.btn_croqui_1000.setFixedHeight(25)
        self.btn_croqui_1000.clicked.connect(lambda: self._on_gerar_croqui(1000))
        linha_croqui_botoes.addWidget(self.btn_croqui_1000)

        self.btn_croqui_tela = QPushButton("🗺  Croqui (escala da tela)")
        self.btn_croqui_tela.setFixedHeight(25)
        self.btn_croqui_tela.clicked.connect(lambda: self._on_gerar_croqui(None))
        linha_croqui_botoes.addWidget(self.btn_croqui_tela)
        corpo.addLayout(linha_croqui_botoes)

        # Projeto personalizado
        linha = QFrame()
        linha.setFrameShape(QFrame.HLine)
        corpo.addWidget(linha)

        lbl_pers = QLabel("Meus projetos personalizados")
        lbl_pers.setStyleSheet("font-weight:bold;font-size:10px;color:#1a365d;")
        corpo.addWidget(lbl_pers)

        lbl_pers_info = QLabel(
            "Adicionou camadas ou mudou estilos? Salve com um nome — fica separado "
            "da base oficial, então atualizar a base não sobrescreve suas mudanças. "
            "Pode salvar quantos quiser."
        )
        lbl_pers_info.setWordWrap(True)
        lbl_pers_info.setStyleSheet("font-size:9px;color:#666;")
        corpo.addWidget(lbl_pers_info)

        self.lista_pers = QListWidget()
        self.lista_pers.setFixedHeight(80)
        corpo.addWidget(self.lista_pers)

        linha_botoes = QHBoxLayout()
        self.btn_salvar_pers = QPushButton("💾  Salvar como novo")
        self.btn_salvar_pers.setFixedHeight(25)
        self.btn_salvar_pers.clicked.connect(self._on_salvar_personalizado)
        linha_botoes.addWidget(self.btn_salvar_pers)

        self.btn_abrir_pers = QPushButton("📂  Abrir selecionado")
        self.btn_abrir_pers.setFixedHeight(25)
        self.btn_abrir_pers.clicked.connect(self._on_abrir_personalizado)
        linha_botoes.addWidget(self.btn_abrir_pers)
        corpo.addLayout(linha_botoes)

        self.btn_excluir_pers = QPushButton("🗑  Excluir selecionado")
        self.btn_excluir_pers.setFixedHeight(22)
        self.btn_excluir_pers.clicked.connect(self._on_excluir_personalizado)
        corpo.addWidget(self.btn_excluir_pers)

        # Links úteis
        linha_links = QFrame()
        linha_links.setFrameShape(QFrame.HLine)
        corpo.addWidget(linha_links)

        lbl_links = QLabel("Links úteis")
        lbl_links.setStyleSheet("font-weight:bold;font-size:10px;color:#1a365d;")
        corpo.addWidget(lbl_links)

        LINKS = [
            ("📄  CND (Certidão Negativa)", "https://cac.dourados.ms.gov.br/emissoes/documentos/certidao-negativa/imovel"),
            ("💰  Valor Venal", "https://cac.dourados.ms.gov.br/emissoes/documentos/certidao-venal"),
            ("🏗  Aprova Digital", "https://dourados.aprova.com.br/home"),
            ("📋  Protocolo BETHA", "https://protocolo.betha.cloud/#/cidadao/dashboard"),
        ]
        linha_links1 = QHBoxLayout()
        linha_links2 = QHBoxLayout()
        for i, (texto, url) in enumerate(LINKS):
            btn = QPushButton(texto)
            btn.setFixedHeight(24)
            btn.setStyleSheet("font-size:9px;")
            btn.clicked.connect(lambda _checked, u=url: QDesktopServices.openUrl(QUrl(u)))
            (linha_links1 if i < 2 else linha_links2).addWidget(btn)
        corpo.addLayout(linha_links1)
        corpo.addLayout(linha_links2)

        btn_sobre = QPushButton("ℹ  Sobre os dados e termos de uso")
        btn_sobre.setFixedHeight(24)
        btn_sobre.setStyleSheet("font-size:9px;")
        btn_sobre.clicked.connect(self._on_sobre_dados)
        corpo.addWidget(btn_sobre)

        from .avisos import AVISO_CURTO
        lbl_aviso = QLabel(AVISO_CURTO)
        lbl_aviso.setWordWrap(True)
        lbl_aviso.setStyleSheet("font-size:10px;color:#2d3748;")
        corpo.addWidget(lbl_aviso)

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setFixedHeight(24)
        btn_fechar.clicked.connect(self._on_recolher)
        corpo.addWidget(btn_fechar)

        self.scroll.setWidget(self.conteudo)
        main.addWidget(self.scroll)

    # ── Status ───────────────────────────────────────────────────────────
    def atualizar_status(self):
        from .sync import get_local_paths, verificar_atualizacao_disponivel

        paths = get_local_paths()
        instalado = os.path.exists(paths["gpkg"])

        if not instalado:
            self._set_status("⬜ Base não instalada nesta máquina.", "#fffbea", "#f0b429")
            self.btn_atualizar.setText("⬇  Baixar Mapa Base")
            self.btn_abrir_oficial.setEnabled(False)
        else:
            tem, msg = verificar_atualizacao_disponivel()
            if tem:
                self._set_status(f"🔄 {msg}", "#fef3e2", "#e67e22")
                self.btn_atualizar.setText("🔄  Atualizar Mapa Base")
            else:
                size_mb = os.path.getsize(paths["gpkg"]) / 1_048_576
                self._set_status(f"✅ Baixado ({size_mb:.0f} MB) — {msg}", "#eafaf1", "#27ae60")
                self.btn_atualizar.setText("🔄  Verificar / Atualizar")
            self.btn_abrir_oficial.setEnabled(True)

        self._atualizar_aviso_plugin()
        self._atualizar_lista_personalizados()

    def _atualizar_aviso_plugin(self):
        from .sync import verificar_atualizacao_plugin
        tem, remota, local = verificar_atualizacao_plugin()
        self.frm_plugin.setVisible(tem)
        if tem:
            self.lbl_plugin.setText(f"🔔 Nova versão do plugin disponível: {remota} (instalada: {local}).")

    def _on_atualizar_plugin(self):
        from qgis.PyQt.QtWidgets import QApplication
        from .sync import atualizar_plugin
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ok, info = atualizar_plugin()
        finally:
            QApplication.restoreOverrideCursor()
        if ok:
            self.btn_atualizar_plugin.setEnabled(False)
            QMessageBox.information(
                self, "Plugin atualizado",
                f"Plugin atualizado para a versão {info}.\n\nFeche e abra o QGIS novamente para começar a usar a nova versão.")
        else:
            QMessageBox.warning(self, "Não foi possível atualizar", info)

    def _atualizar_lista_personalizados(self):
        from .sync import listar_meus_projetos
        self.lista_pers.clear()
        nomes = listar_meus_projetos()
        self.lista_pers.addItems(nomes)
        tem_algum = len(nomes) > 0
        self.btn_abrir_pers.setEnabled(tem_algum)
        self.btn_excluir_pers.setEnabled(tem_algum)
        if tem_algum:
            self.lista_pers.setCurrentRow(0)

    def _set_status(self, texto, bg, borda):
        self.lbl_status.setText(texto)
        self.frm_status.setStyleSheet(f"border:1px solid {borda};background:{bg};border-radius:4px;padding:4px;")

    # ── Baixar/Atualizar ─────────────────────────────────────────────────
    def _on_atualizar(self):
        from .sync import get_local_paths
        paths = get_local_paths()
        os.makedirs(paths["dir"], exist_ok=True)

        self.btn_atualizar.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(0)

        self._worker = DownloadWorker(paths["gpkg"])
        self._worker.progress.connect(lambda v, m: (self.prog_bar.setValue(v), self.lbl_prog.setText(m)))
        self._worker.finished.connect(self._on_download_finished)
        self._worker.start()

    def _on_sobre_dados(self):
        from .avisos import mostrar_aviso_dados
        mostrar_aviso_dados(self)

    def _on_download_finished(self, ok, erro):
        self.btn_atualizar.setEnabled(True)
        if not ok:
            self.prog_bar.setValue(0)
            QMessageBox.critical(self, "Erro no download", erro)
            return
        self.prog_bar.setValue(100)
        self.lbl_prog.setText("✅ Concluído!")
        self.atualizar_status()
        from .avisos import mostrar_aviso_primeira_vez
        mostrar_aviso_primeira_vez(self)

    # ── Abrir projeto oficial ────────────────────────────────────────────
    def _on_abrir_oficial(self):
        from .sync import get_local_paths, PROJETO_NOME
        paths = get_local_paths()
        if not os.path.exists(paths["gpkg"]):
            QMessageBox.warning(self, "Não instalado", "Baixe o Mapa Base primeiro.")
            return
        uri = f"geopackage:{paths['gpkg']}?projectName={PROJETO_NOME}"
        self.iface.addProject(uri)

    # ── Painel: recolher / auto ajustar / alargar ─────────────────────────
    def _area_disponivel(self):
        try:
            tela = self.screen() or QApplication.primaryScreen()
        except Exception:
            tela = QApplication.primaryScreen()
        return tela.availableGeometry()

    def _definir_largura(self, largura):
        dock = self.dock
        if dock is None:
            return
        if dock.isFloating():
            area = self._area_disponivel()
            self.dock.resize(largura, min(self.dock.height(), int(area.height() * 0.92)))
        else:
            self.iface.mainWindow().resizeDocks([dock], [largura], Qt.Horizontal)

    def _on_recolher(self):
        # Esconde o painel; o botão do plugin na barra de ferramentas reabre.
        if self.dock is not None:
            self.dock.hide()

    def _on_ajustar(self):
        largura = max(self.conteudo.sizeHint().width() + 28, 360)
        self._definir_largura(largura)
        self._largura_antes = None
        self.btn_maximizar.setText("□")

    def _on_maximizar(self):
        dock = self.dock
        if dock is None:
            return
        if self._largura_antes is None:
            self._largura_antes = dock.width()
            self._definir_largura(int(self.iface.mainWindow().width() * 0.5))
            self.btn_maximizar.setText("❐")
        else:
            self._definir_largura(self._largura_antes)
            self._largura_antes = None
            self.btn_maximizar.setText("□")

    # ── Busca ────────────────────────────────────────────────────────────
    def _on_buscar(self):
        from qgis.core import QgsProject
        from . import busca
        termo = self.txt_busca.text().strip()
        if not termo:
            self.lbl_busca.setText("Digite o que procurar.")
            return
        itens, msg = busca.buscar(QgsProject.instance(), self.cb_tipo.currentData(), termo, self.chk_exata.isChecked())
        self._mostrar_resultados(itens, msg)
        if len(itens) == 1:
            busca.zoom_itens(self.iface, itens)

    def _mostrar_resultados(self, itens, msg):
        self._itens_busca = itens
        self.lista_busca.clear()
        for i, it in enumerate(itens):
            li = QListWidgetItem(it["rotulo"])
            li.setData(Qt.UserRole, i)
            self.lista_busca.addItem(li)
        self.lbl_busca.setText(msg)
        self._ajustar_altura_lista()

    def _ajustar_altura_lista(self):
        n = self.lista_busca.count()
        altura_linha = self.lista_busca.sizeHintForRow(0) if n > 0 else 18
        linhas = min(max(n, 3), 12)
        self.lista_busca.setFixedHeight(altura_linha * linhas + 2 * self.lista_busca.frameWidth() + 4)

    def _itens_do_clique(self, itens_lista):
        return [self._itens_busca[li.data(Qt.UserRole)] for li in itens_lista]

    def _on_resultado_clicado(self, item):
        from . import busca
        busca.zoom_itens(self.iface, self._itens_do_clique([item]))

    def _on_zoom_selecionados(self):
        from . import busca
        sel = self.lista_busca.selectedItems()
        if sel:
            busca.zoom_itens(self.iface, self._itens_do_clique(sel))

    def _on_limpar_busca(self):
        self.txt_busca.clear()
        self._mostrar_resultados([], "")

    def _on_lote_selecionado(self):
        from qgis.core import QgsProject
        from . import busca
        item, msg = busca.lote_selecionado(QgsProject.instance())
        if item is None:
            self.lbl_busca.setText(msg)
            return
        self._mostrar_resultados([item], "Lote selecionado no mapa.")
        busca.zoom_itens(self.iface, [item], piscar=False)

    def _on_tabela_atributos(self):
        from qgis.core import QgsProject
        from .camadas import camadas_principais
        camada = self.iface.activeLayer()
        if camada is None or camada.type() != camada.VectorLayer:
            camada = camadas_principais(QgsProject.instance())["lotes"]
        if camada is None:
            QMessageBox.warning(self, "Sem camada", "Abra o projeto oficial (ou selecione uma camada vetorial) primeiro.")
            return
        self.iface.showAttributeTable(camada)

    # ── Croqui ───────────────────────────────────────────────────────────
    def _on_gerar_croqui(self, escala_fixa):
        from .sync import get_local_paths
        from . import croqui

        paths = get_local_paths()
        ok, msg = croqui.gerar_croqui(self.iface, paths["gpkg"], escala_fixa=escala_fixa)
        if ok:
            QMessageBox.information(self, "Croqui gerado", msg)
        else:
            QMessageBox.warning(self, "Não foi possível gerar o croqui", msg)

    # ── Projeto personalizado ────────────────────────────────────────────
    def _on_salvar_personalizado(self):
        from qgis.core import QgsProject
        from .sync import get_local_paths, caminho_meu_projeto, slug_nome_projeto

        nome, ok_clicou = QInputDialog.getText(
            self, "Salvar projeto como",
            "Nome pra esse projeto (ex: \"Zona Norte\", \"Fiscalização 2026\"):",
            QLineEdit.Normal, "",
        )
        if not ok_clicou or not slug_nome_projeto(nome):
            return

        destino = caminho_meu_projeto(nome)
        if os.path.exists(destino):
            resp = QMessageBox.question(
                self, "Já existe",
                f'Já existe um projeto salvo com o nome "{nome}". Substituir?',
                QMessageBox.Yes | QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return

        paths = get_local_paths()
        os.makedirs(paths["meus_projetos_dir"], exist_ok=True)

        ok = QgsProject.instance().write(destino)
        if ok:
            QMessageBox.information(self, "Salvo", f'Projeto "{nome}" salvo com sucesso.')
            self.atualizar_status()
        else:
            QMessageBox.critical(self, "Erro", "Não foi possível salvar o projeto.")

    def _item_selecionado(self):
        item = self.lista_pers.currentItem()
        if not item:
            QMessageBox.warning(self, "Nada selecionado", "Selecione um projeto na lista primeiro.")
            return None
        return item.text()

    def _on_abrir_personalizado(self):
        from .sync import caminho_meu_projeto
        nome = self._item_selecionado()
        if not nome:
            return
        self.iface.addProject(caminho_meu_projeto(nome))

    def _on_excluir_personalizado(self):
        from .sync import caminho_meu_projeto
        nome = self._item_selecionado()
        if not nome:
            return
        resp = QMessageBox.question(
            self, "Excluir projeto",
            f'Excluir o projeto salvo "{nome}"? Essa ação não pode ser desfeita.',
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        try:
            os.remove(caminho_meu_projeto(nome))
            self.atualizar_status()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível excluir: {e}")
