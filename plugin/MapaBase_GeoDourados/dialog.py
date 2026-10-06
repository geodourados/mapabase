import os

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QMessageBox, QFrame, QListWidget, QInputDialog, QLineEdit, QScrollArea,
    QWidget, QComboBox, QCheckBox, QListWidgetItem, QAbstractItemView, QApplication,
    QTabWidget, QStackedWidget, QSizePolicy,
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


class _Cabecalho(QFrame):
    """Faixa azul do topo; mantém o rótulo de versão colado no canto inferior direito."""

    def __init__(self):
        super().__init__()
        self.canto = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.canto is not None:
            self.canto.adjustSize()
            self.canto.move(self.width() - self.canto.width() - 5, self.height() - self.canto.height() - 1)


class MapaBaseDialog(QWidget):
    LARGURA_RECOLHIDO = 34  # um pouco maior que o botão X do painel

    def __init__(self, iface, on_fechar=None):
        super().__init__()
        self.iface = iface
        self._on_fechar = on_fechar
        self.setWindowTitle("Mapa Base - GeoDourados (Offline)")
        self.setWindowIcon(QIcon(os.path.join(PLUGIN_DIR, "icons", "icon.png")))
        self.setMinimumWidth(340)
        self._itens_busca = []
        self._altura_expandida = None
        self._primeira_exibicao = True
        self._largura_antes = None
        self._recolhido = False
        self._largura_recolher = None
        self._dual = None
        self._camada_tabela = None
        self._timer_tabela = None
        self._ids_attr = []
        self._idx_attr = 0
        self._form = None
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

        header = _Cabecalho()
        self._header = header
        header.setStyleSheet("background-color: #1a365d;")
        header.setFixedHeight(34)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(6, 3, 6, 3)
        hl.setSpacing(4)
        brasao_path = os.path.join(PLUGIN_DIR, "icons", "brasao.png")
        if os.path.exists(brasao_path):
            lbl = QLabel()
            lbl.setPixmap(QPixmap(brasao_path).scaled(26, 26, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            hl.addWidget(lbl)
        tl = QLabel("Mapa Base Digital da Cidade de Dourados - MS")
        tl.setStyleSheet("color:white;font-size:8px;font-weight:bold;")
        tl.setWordWrap(False)
        tl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        hl.addWidget(tl, 1)
        from .sync import versao_plugin_local
        versao = versao_plugin_local()
        if versao:
            lbl_versao = QLabel(f"v{versao}", header)
            lbl_versao.setStyleSheet("color:#a0aec0;font-size:7px;background:transparent;")
            lbl_versao.setToolTip("Versão instalada do plugin")
            header.canto = lbl_versao
        estilo_btn = ("QPushButton{color:white;background:transparent;border:none;font-size:13px;}"
                      "QPushButton:hover{background:#2c5f8a;border-radius:3px;}")
        for attr, texto, dica, slot in (
            ("btn_recolher", "▸", "Recolher o painel numa faixa estreita (clique na seta para voltar)", self._on_recolher),
            ("btn_ajustar", "↕", "Auto ajustar a largura do painel ao conteúdo", self._on_ajustar),
            ("btn_maximizar", "□", "Alargar / restaurar o painel", self._on_maximizar),
        ):
            b = QPushButton(texto)
            b.setToolTip(dica)
            b.setFixedSize(20, 20)
            b.setStyleSheet(estilo_btn)
            b.clicked.connect(slot)
            setattr(self, attr, b)
            hl.addWidget(b)
        self.topo = QWidget()
        topo_lay = QVBoxLayout(self.topo)
        topo_lay.setContentsMargins(8, 8, 8, 0)
        topo_lay.addWidget(header)
        main.addWidget(self.topo)

        corpo.setContentsMargins(6, 4, 6, 6)
        corpo.setSpacing(4)

        # ── Abas ─────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabBar::tab{padding:4px 9px;font-size:10px;}"
            "QTabBar::tab:selected{font-weight:bold;color:#1a365d;}")
        corpo.addWidget(self.tabs, 1)

        def pagina(titulo):
            w = QWidget()
            lay = QVBoxLayout(w)
            lay.setContentsMargins(4, 6, 4, 4)
            lay.setSpacing(5)
            self.tabs.addTab(w, titulo)
            return lay

        def titulo_secao(texto):
            lb = QLabel(texto)
            lb.setStyleSheet("font-weight:bold;font-size:10px;color:#1a365d;")
            return lb

        def linha_h():
            f = QFrame()
            f.setFrameShape(QFrame.HLine)
            return f

        # ── Aba BASE ─────────────────────────────────────────────────────
        pb = pagina("Base")
        self.frm_status = QFrame()
        self.frm_status.setStyleSheet("border:1px solid #ccc;border-radius:4px;padding:3px;")
        sl = QHBoxLayout(self.frm_status)
        sl.setContentsMargins(4, 2, 4, 2)
        self.lbl_status = QLabel("Verificando...")
        self.lbl_status.setStyleSheet("font-size:10px;")
        self.lbl_status.setWordWrap(True)
        sl.addWidget(self.lbl_status)
        pb.addWidget(self.frm_status)

        self.frm_plugin = QFrame()
        self.frm_plugin.setStyleSheet("border:1px solid #e67e22;background:#fef3e2;border-radius:4px;padding:3px;")
        pl = QVBoxLayout(self.frm_plugin)
        pl.setContentsMargins(4, 2, 4, 2)
        self.lbl_plugin = QLabel("")
        self.lbl_plugin.setWordWrap(True)
        self.lbl_plugin.setStyleSheet("font-size:10px;border:none;background:transparent;")
        pl.addWidget(self.lbl_plugin)
        self.btn_atualizar_plugin = QPushButton("⬆  Atualizar plugin")
        self.btn_atualizar_plugin.setFixedHeight(24)
        self.btn_atualizar_plugin.clicked.connect(self._on_atualizar_plugin)
        pl.addWidget(self.btn_atualizar_plugin)
        self.frm_plugin.setVisible(False)
        pb.addWidget(self.frm_plugin)

        self.prog_bar = QProgressBar()
        self.prog_bar.setVisible(False)
        self.prog_bar.setFixedHeight(14)
        pb.addWidget(self.prog_bar)
        self.lbl_prog = QLabel("")
        self.lbl_prog.setAlignment(Qt.AlignCenter)
        self.lbl_prog.setStyleSheet("font-size:9px;color:#555;")
        pb.addWidget(self.lbl_prog)

        self.btn_atualizar = QPushButton("⬇  Baixar / Atualizar base")
        self.btn_atualizar.setFixedHeight(27)
        self.btn_atualizar.setStyleSheet(
            "QPushButton{background:#1a365d;color:white;border-radius:4px;font-weight:bold;}"
            "QPushButton:hover{background:#2c5f8a;}QPushButton:disabled{background:#aaa;}")
        self.btn_atualizar.clicked.connect(self._on_atualizar)
        pb.addWidget(self.btn_atualizar)
        self.btn_abrir_oficial = QPushButton("📂  Abrir projeto oficial")
        self.btn_abrir_oficial.setFixedHeight(25)
        self.btn_abrir_oficial.clicked.connect(self._on_abrir_oficial)
        pb.addWidget(self.btn_abrir_oficial)

        pb.addWidget(linha_h())
        pb.addWidget(titulo_secao("Meus projetos personalizados"))
        lbl_pers_info = QLabel("Mudou estilos ou adicionou camadas? Salve com um nome: fica separado da "
                               "base oficial e atualizar a base não sobrescreve.")
        lbl_pers_info.setWordWrap(True)
        lbl_pers_info.setStyleSheet("font-size:9px;color:#666;")
        pb.addWidget(lbl_pers_info)
        self.lista_pers = QListWidget()
        self.lista_pers.setFixedHeight(70)
        self.lista_pers.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        pb.addWidget(self.lista_pers)
        linha_botoes = QHBoxLayout()
        self.btn_salvar_pers = QPushButton("💾  Salvar como novo")
        self.btn_salvar_pers.setFixedHeight(24)
        self.btn_salvar_pers.clicked.connect(self._on_salvar_personalizado)
        linha_botoes.addWidget(self.btn_salvar_pers)
        self.btn_abrir_pers = QPushButton("📂  Abrir")
        self.btn_abrir_pers.setFixedHeight(24)
        self.btn_abrir_pers.clicked.connect(self._on_abrir_personalizado)
        linha_botoes.addWidget(self.btn_abrir_pers)
        self.btn_excluir_pers = QPushButton("🗑  Excluir")
        self.btn_excluir_pers.setFixedHeight(24)
        self.btn_excluir_pers.clicked.connect(self._on_excluir_personalizado)
        linha_botoes.addWidget(self.btn_excluir_pers)
        pb.addLayout(linha_botoes)
        pb.addStretch()

        # ── Aba BUSCAR ───────────────────────────────────────────────────
        pq = pagina("Buscar")
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
            "Inscrição e Matrícula: procuram nos lotes (por prefixo; com 'Exata', o valor completo). "
            "Loteamento e Logradouro: pelo nome, em qualquer ordem e sem acento; dão zoom e piscam o contorno.")
        l1.addWidget(self.cb_tipo, 1)
        self.chk_exata = QCheckBox("Exata")
        l1.addWidget(self.chk_exata)
        pq.addLayout(l1)

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
        pq.addLayout(l2)

        self.lbl_busca = QLabel("")
        self.lbl_busca.setWordWrap(True)
        self.lbl_busca.setStyleSheet("font-size:9px;color:#555;")
        pq.addWidget(self.lbl_busca)

        l3 = QHBoxLayout()
        l3.setSpacing(2)
        self.lista_busca = QListWidget()
        self.lista_busca.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.lista_busca.itemClicked.connect(self._on_resultado_clicado)
        self.lista_busca.itemActivated.connect(self._on_resultado_clicado)
        self.lista_busca.setFixedHeight(60)
        self.lista_busca.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
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
        l3.addLayout(col)
        l3.setAlignment(Qt.AlignTop)
        pq.addLayout(l3)

        b_ver = QPushButton("📋  Ver atributos do selecionado  →")
        b_ver.setFixedHeight(25)
        b_ver.setToolTip("Abre a aba Atributos com as feições selecionadas.")
        b_ver.clicked.connect(self._ir_para_atributos)
        pq.addWidget(b_ver)

        pq.addWidget(linha_h())
        pq.addWidget(titulo_secao("Croqui de localização (PDF)"))
        lbl_croqui_info = QLabel("Selecione 1 lote (pela busca ou no mapa) e clique:")
        lbl_croqui_info.setStyleSheet("font-size:9px;color:#666;")
        pq.addWidget(lbl_croqui_info)
        linha_croqui_botoes = QHBoxLayout()
        self.btn_croqui_1000 = QPushButton("🗺  1:1000")
        self.btn_croqui_1000.setFixedHeight(25)
        self.btn_croqui_1000.clicked.connect(lambda: self._on_gerar_croqui(1000))
        linha_croqui_botoes.addWidget(self.btn_croqui_1000)
        self.btn_croqui_tela = QPushButton("🗺  Escala da tela")
        self.btn_croqui_tela.setFixedHeight(25)
        self.btn_croqui_tela.clicked.connect(lambda: self._on_gerar_croqui(None))
        linha_croqui_botoes.addWidget(self.btn_croqui_tela)
        pq.addLayout(linha_croqui_botoes)
        pq.addStretch()

        # ── Aba ATRIBUTOS ────────────────────────────────────────────────
        pa = pagina("Atributos")
        self.lbl_attr = QLabel("")
        self.lbl_attr.setStyleSheet("font-size:10px;font-weight:bold;color:#1a365d;")
        self.lbl_attr.setWordWrap(True)
        pa.addWidget(self.lbl_attr)
        nav = QHBoxLayout()
        nav.setSpacing(3)
        self.btn_prev = QPushButton("◀")
        self.btn_prev.setFixedSize(26, 22)
        self.btn_prev.clicked.connect(lambda: self._navegar_attr(-1))
        nav.addWidget(self.btn_prev)
        self.lbl_pos = QLabel("")
        self.lbl_pos.setStyleSheet("font-size:9px;")
        self.lbl_pos.setAlignment(Qt.AlignCenter)
        nav.addWidget(self.lbl_pos, 1)
        self.btn_next = QPushButton("▶")
        self.btn_next.setFixedSize(26, 22)
        self.btn_next.clicked.connect(lambda: self._navegar_attr(1))
        nav.addWidget(self.btn_next)
        self.cb_modo_attr = QComboBox()
        self.cb_modo_attr.addItems(["Formulário", "Tabela"])
        self.cb_modo_attr.setToolTip("Formulário: um registro por vez (campo e valor). Tabela: vários registros em linhas.")
        self.cb_modo_attr.currentIndexChanged.connect(lambda _=None: self._atualizar_atributos())
        nav.addWidget(self.cb_modo_attr)
        self.chk_so_selecionados = QCheckBox("Só selec.")
        self.chk_so_selecionados.setChecked(True)
        self.chk_so_selecionados.setStyleSheet("font-size:9px;")
        self.chk_so_selecionados.setToolTip("No modo Tabela: só as feições selecionadas ou a camada toda.")
        self.chk_so_selecionados.toggled.connect(lambda _=None: self._atualizar_atributos())
        nav.addWidget(self.chk_so_selecionados)
        b_janela = QPushButton("↗")
        b_janela.setToolTip("Abrir a tabela completa numa janela separada do QGIS.")
        b_janela.setFixedSize(24, 22)
        b_janela.clicked.connect(self._on_tabela_em_janela)
        nav.addWidget(b_janela)
        pa.addLayout(nav)
        self.stack_attr = QStackedWidget()
        # página 0: formulário
        self.scroll_form = QScrollArea()
        self.scroll_form.setWidgetResizable(True)
        self.scroll_form.setFrameShape(QFrame.NoFrame)
        self.cont_form = QWidget()
        self.lay_form = QVBoxLayout(self.cont_form)
        self.lay_form.setContentsMargins(0, 0, 0, 0)
        self.scroll_form.setWidget(self.cont_form)
        self.stack_attr.addWidget(self.scroll_form)
        # página 1: tabela
        self.cont_tabela = QWidget()
        self.lay_tabela = QVBoxLayout(self.cont_tabela)
        self.lay_tabela.setContentsMargins(0, 0, 0, 0)
        self.stack_attr.addWidget(self.cont_tabela)
        self.stack_attr.setMinimumHeight(300)
        pa.addWidget(self.stack_attr, 1)
        self.tabs.currentChanged.connect(self._on_aba_mudou)
        try:
            self.iface.currentLayerChanged.connect(self._on_camada_ativa_mudou)
        except Exception:
            pass

        # ── Aba MAIS ─────────────────────────────────────────────────────
        pm = pagina("Mais")
        pm.addWidget(titulo_secao("Links úteis"))
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
            btn.setFixedHeight(26)
            btn.setStyleSheet("font-size:9px;")
            btn.clicked.connect(lambda _checked, u=url: QDesktopServices.openUrl(QUrl(u)))
            (linha_links1 if i < 2 else linha_links2).addWidget(btn)
        pm.addLayout(linha_links1)
        pm.addLayout(linha_links2)
        pm.addWidget(linha_h())
        btn_sobre = QPushButton("ℹ  Sobre os dados e termos de uso")
        btn_sobre.setFixedHeight(26)
        btn_sobre.clicked.connect(self._on_sobre_dados)
        pm.addWidget(btn_sobre)
        pm.addStretch()

        # ── Rodapé fixo (aviso legal) ────────────────────────────────────
        from .avisos import AVISO_CURTO
        rod = QHBoxLayout()
        rod.setSpacing(4)
        lbl_aviso = QLabel(AVISO_CURTO)
        lbl_aviso.setWordWrap(True)
        lbl_aviso.setStyleSheet("font-size:9px;color:#2d3748;")
        rod.addWidget(lbl_aviso, 1)
        b_info = QPushButton("ℹ")
        b_info.setToolTip("Sobre os dados e termos de uso")
        b_info.setFixedSize(24, 24)
        b_info.clicked.connect(self._on_sobre_dados)
        rod.addWidget(b_info)
        corpo.addLayout(rod)

        self.scroll.setWidget(self.conteudo)
        main.addWidget(self.scroll, 1)
        main.addStretch(0)

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

    def _on_fechar_painel(self):
        if self.dock is not None:
            self.dock.hide()

    def _widgets_cabecalho(self):
        return [w for w in self._header.children()
                if isinstance(w, QWidget) and w is not self.btn_recolher]

    def _on_recolher(self):
        # Recolhe numa faixa estreita só com a seta (libera espaço no mapa).
        dock = self.dock
        if dock is None:
            return
        if not self._recolhido:
            self._largura_recolher = dock.width()
            self._recolhido = True
            self.scroll.hide()
            for w in self._widgets_cabecalho():
                w.hide()
            self.btn_recolher.setText("◂")
            self.btn_recolher.setToolTip("Expandir o painel")
            self.setMinimumWidth(0)
            dock.setMinimumWidth(0)
            dock.setMaximumWidth(self.LARGURA_RECOLHIDO)
            self.topo.layout().setContentsMargins(2, 4, 2, 0)
            self._header.setFixedSize(self.LARGURA_RECOLHIDO - 8, 24)
            self.btn_recolher.setFixedSize(20, 20)
            if not dock.isFloating():
                self.iface.mainWindow().resizeDocks([dock], [self.LARGURA_RECOLHIDO], Qt.Horizontal)
            else:
                dock.resize(self.LARGURA_RECOLHIDO, dock.height())
        else:
            self._recolhido = False
            self._header.setMinimumSize(0, 0)
            self._header.setMaximumSize(16777215, 16777215)
            self._header.setFixedHeight(34)
            self.btn_recolher.setFixedSize(20, 20)
            self.topo.layout().setContentsMargins(8, 8, 8, 0)
            self.scroll.show()
            for w in self._widgets_cabecalho():
                w.show()
            self.btn_recolher.setText("▸")
            self.btn_recolher.setToolTip("Recolher o painel numa faixa estreita (clique na seta para voltar)")
            self.setMinimumWidth(340)
            dock.setMaximumWidth(16777215)
            largura = self._largura_recolher or 400
            if not dock.isFloating():
                self.iface.mainWindow().resizeDocks([dock], [largura], Qt.Horizontal)
            else:
                dock.resize(largura, dock.height())

    def _on_ajustar(self):
        if self._recolhido:
            self._on_recolher()
        largura = max(self.conteudo.sizeHint().width() + 28, 360)
        self._definir_largura(largura)
        self._largura_antes = None
        self.btn_maximizar.setText("□")

    def _on_maximizar(self):
        dock = self.dock
        if dock is None:
            return
        if self._recolhido:
            self._on_recolher()
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

    # ── Aba Atributos (formulário / tabela) ──────────────────────────────
    LIMITE_FORM = 300

    def _camada_da_tabela(self):
        from qgis.core import QgsProject
        from .camadas import camadas_principais
        camada = self.iface.activeLayer()
        if camada is None or camada.type() != camada.VectorLayer:
            camada = camadas_principais(QgsProject.instance())["lotes"]
        return camada

    def _ir_para_atributos(self):
        self.tabs.setCurrentIndex(self.tabs.count() - 2)  # aba Atributos (penúltima)

    def _indice_aba_atributos(self):
        return self.tabs.count() - 2

    def _on_aba_mudou(self, indice):
        if indice == self._indice_aba_atributos():
            self._carregar_atributos()

    def _on_camada_ativa_mudou(self, *args):
        if self.tabs.currentIndex() == self._indice_aba_atributos():
            self._carregar_atributos()

    def _carregar_atributos(self):
        camada = self._camada_da_tabela()
        if camada is not self._camada_tabela:
            if self._camada_tabela is not None:
                try:
                    self._camada_tabela.selectionChanged.disconnect(self._agendar_atributos)
                except Exception:
                    pass
            self._camada_tabela = camada
            self._idx_attr = 0
            if camada is not None:
                camada.selectionChanged.connect(self._agendar_atributos)
        self._atualizar_atributos()

    def _agendar_atributos(self, *args):
        if self.tabs.currentIndex() != self._indice_aba_atributos():
            return
        if self._timer_tabela is None:
            self._timer_tabela = QTimer(self)
            self._timer_tabela.setSingleShot(True)
            self._timer_tabela.timeout.connect(self._atualizar_atributos)
        self._timer_tabela.start(250)

    def _limpar_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()
        self._form = None
        self._dual = None

    def _navegar_attr(self, passo):
        if not self._ids_attr:
            return
        self._idx_attr = (self._idx_attr + passo) % len(self._ids_attr)
        self._mostrar_formulario()

    def _atualizar_atributos(self):
        camada = self._camada_tabela
        self._limpar_layout(self.lay_form)
        self._limpar_layout(self.lay_tabela)
        if camada is None:
            self.lbl_attr.setText("Abra o projeto oficial (ou selecione uma camada vetorial) primeiro.")
            self.lbl_pos.setText("")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            return
        self._ids_attr = list(camada.selectedFeatureIds())
        n = len(self._ids_attr)
        modo_tabela = self.cb_modo_attr.currentIndex() == 1
        self.chk_so_selecionados.setVisible(modo_tabela)
        self.btn_prev.setVisible(not modo_tabela)
        self.btn_next.setVisible(not modo_tabela)
        self.lbl_pos.setVisible(not modo_tabela)
        if modo_tabela:
            self._mostrar_tabela()
        else:
            self.lbl_attr.setText(f"{camada.name()} — {n} selecionado(s)")
            self._mostrar_formulario()

    def _mostrar_formulario(self):
        from qgis.gui import QgsAttributeForm, QgsAttributeEditorContext
        camada = self._camada_tabela
        self.stack_attr.setCurrentIndex(0)
        self._limpar_layout(self.lay_form)
        ids = self._ids_attr[: self.LIMITE_FORM]
        n = len(ids)
        self.btn_prev.setEnabled(n > 1)
        self.btn_next.setEnabled(n > 1)
        if not ids:
            self.lbl_pos.setText("")
            msg = QLabel("Nenhuma feição selecionada.\nSelecione no mapa ou use a aba Buscar.")
            msg.setStyleSheet("color:#718096;padding:12px;")
            msg.setAlignment(Qt.AlignCenter)
            self.lay_form.addWidget(msg)
            self.lay_form.addStretch()
            return
        self._idx_attr = min(self._idx_attr, n - 1)
        feat = camada.getFeature(ids[self._idx_attr])
        try:
            from qgis.core import QgsVectorLayerUtils
            titulo = QgsVectorLayerUtils.getFeatureDisplayString(camada, feat)
        except Exception:
            titulo = ""
        self.lbl_pos.setText(f"{self._idx_attr + 1} / {n}   {titulo}")
        form = QgsAttributeForm(camada, feat, QgsAttributeEditorContext(), self.cont_form)
        form.setMode(QgsAttributeEditorContext.IdentifyMode)
        self.lay_form.addWidget(form)
        self._form = form

    def _mostrar_tabela(self):
        from qgis.core import QgsFeatureRequest
        from qgis.gui import QgsDualView, QgsAttributeEditorContext
        camada = self._camada_tabela
        self.stack_attr.setCurrentIndex(1)
        so_sel = self.chk_so_selecionados.isChecked()
        req = QgsFeatureRequest()
        if so_sel:
            ids = list(camada.selectedFeatureIds())
            req.setFilterFids(ids)
            self.lbl_attr.setText(f"{camada.name()} — {len(ids)} selecionado(s)")
            if not ids:
                self.lbl_attr.setText(f"{camada.name()} — nenhuma feição selecionada (selecione no mapa ou use a busca)")
                return
        else:
            limite = 5000
            req.setLimit(limite)
            total = camada.featureCount()
            extra = f" (mostrando os {limite} primeiros)" if total > limite else ""
            self.lbl_attr.setText(f"{camada.name()} — {total} feição(ões){extra}")
        dv = QgsDualView(self.cont_tabela)
        dv.init(camada, self.iface.mapCanvas(), req, QgsAttributeEditorContext())
        dv.setView(QgsDualView.AttributeTable)
        self.lay_tabela.addWidget(dv, 1)
        self._dual = dv

    def _on_tabela_em_janela(self):
        if self._camada_tabela is None:
            self._carregar_atributos()
        if self._camada_tabela is not None:
            self.iface.showAttributeTable(self._camada_tabela)

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
