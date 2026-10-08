import os

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QMessageBox, QFrame, QListWidget, QInputDialog, QLineEdit, QScrollArea,
    QWidget, QComboBox, QCheckBox, QListWidgetItem, QAbstractItemView, QApplication,
    QTabWidget, QStackedWidget, QSizePolicy, QGridLayout,
)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QUrl, QTimer
from qgis.PyQt.QtGui import QIcon, QPixmap, QDesktopServices, QFont, QFontMetrics, QColor, QPalette

PLUGIN_DIR = os.path.dirname(__file__)


class CepWorker(QThread):
    pronto = pyqtSignal(object, str)  # (dados|None, erro)

    def __init__(self, cep8):
        super().__init__()
        self.cep8 = cep8

    def run(self):
        from .cep import consultar_correios
        try:
            self.pronto.emit(consultar_correios(self.cep8), "")
        except Exception as e:
            self.pronto.emit(None, str(e) or "erro")


class ComplementoWorker(QThread):
    """Baixa o Complemento (.qlr + .gpkg)."""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str)

    def run(self):
        from . import complemento
        ok, err = complemento.baixar(progress_callback=lambda v, m: self.progress.emit(v, m))
        self.finished.emit(ok, err)


class ComplementoStatusWorker(QThread):
    pronto = pyqtSignal(str, str)

    def run(self):
        from . import complemento
        try:
            self.pronto.emit(*complemento.verificar())
        except Exception as e:
            self.pronto.emit("sem_rede", str(e))


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


ESTILO_BOTAO_AZUL = (
    "QPushButton, QPushButton:enabled, QPushButton:focus, QPushButton:pressed, QPushButton:default"
    "{background-color:#1a365d;color:#ffffff;border:none;border-radius:4px;font-weight:bold;}"
    "QPushButton:hover{background-color:#2c5f8a;color:#ffffff;}"
    "QPushButton:disabled{background-color:#a0aec0;color:#ffffff;}"
)


def estilizar_botao_azul(btn):
    """Fundo azul com texto BRANCO em todos os estados, independente do tema do QGIS
    (além do stylesheet, fixa a paleta do botão)."""
    btn.setStyleSheet(ESTILO_BOTAO_AZUL)
    pal = btn.palette()
    branco = QColor("#ffffff")
    for papel in (QPalette.ButtonText, QPalette.WindowText, QPalette.Text, QPalette.BrightText):
        pal.setColor(QPalette.Active, papel, branco)
        pal.setColor(QPalette.Inactive, papel, branco)
        pal.setColor(QPalette.Disabled, papel, branco)
    btn.setPalette(pal)


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
        header.setObjectName("cabecalho")
        # Fundo azul SÓ na faixa (um "background-color" solto vazava para os tooltips,
        # deixando o texto de ajuda preto sobre azul).
        header.setStyleSheet(
            "QFrame#cabecalho{background-color:#1a365d;}"
            "QToolTip{color:#1a202c;background-color:#fffbe6;border:1px solid #a0aec0;}")
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
        # Mesmo tamanho de fonte do título do painel (fonte padrão do QGIS).
        self._pt = QApplication.font().pointSizeF()
        if self._pt <= 0:
            self._pt = 9.0
        tl.setStyleSheet(f"color:white;font-size:{self._pt}pt;font-weight:bold;")
        _f = QFont(QApplication.font())
        _f.setBold(True)
        self._larg_titulo = QFontMetrics(_f).horizontalAdvance(tl.text()) + 6
        tl.setWordWrap(False)
        tl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        hl.addWidget(tl, 1)
        from .sync import versao_plugin_local
        versao = versao_plugin_local()
        estilo_btn = ("QPushButton{color:#ffffff;background:transparent;border:none;font-size:17px;font-weight:bold;}"
                      "QPushButton:hover{background:#2c5f8a;border-radius:3px;}")
        for attr, texto, dica, slot in (
            ("btn_recolher", "»", "Recolher o painel numa faixa estreita (clique em « para voltar)", self._on_recolher),
            ("btn_ajustar", "↔", "Auto ajustar: deixa o painel na largura ideal para o conteúdo", self._on_ajustar),
            ("btn_maximizar", "□", "Alargar o painel até metade da tela do QGIS (clique de novo para restaurar)", self._on_maximizar),
        ):
            b = QPushButton(texto)
            b.setToolTip(dica)
            b.setFixedSize(24, 24)
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
            f"QTabBar::tab{{padding:4px 10px;font-size:{self._pt}pt;}}"
            "QTabBar::tab:selected{color:#1a365d;background:#ffffff;}")
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
            lb.setProperty("fonte_uniforme", True)
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
        self.lbl_status.setProperty("fonte_uniforme", True)
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
        self.lbl_plugin.setProperty("fonte_uniforme", True)
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
        estilizar_botao_azul(self.btn_atualizar)
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
        estilizar_botao_azul(b_buscar)
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

        linha_ord = QHBoxLayout()
        linha_ord.setSpacing(3)
        self.lbl_busca = QLabel("")
        self.lbl_busca.setWordWrap(True)
        self.lbl_busca.setStyleSheet("font-size:9px;color:#555;")
        linha_ord.addWidget(self.lbl_busca, 1)
        self.lbl_ordenar = QLabel("Ordenar:")
        self.lbl_ordenar.setStyleSheet("font-size:9px;color:#555;")
        linha_ord.addWidget(self.lbl_ordenar)
        self.cb_ordem = QComboBox()
        self.cb_ordem.setStyleSheet("font-size:9px;")
        self.cb_ordem.currentIndexChanged.connect(lambda _=None: self._reordenar_resultados())
        linha_ord.addWidget(self.cb_ordem)
        self.btn_sentido = QPushButton("↑")
        self.btn_sentido.setFixedSize(22, 20)
        self.btn_sentido.setToolTip("Sentido da ordenação: crescente (↑) ou decrescente (↓).")
        self.btn_sentido.clicked.connect(self._alternar_sentido)
        linha_ord.addWidget(self.btn_sentido)
        pq.addLayout(linha_ord)
        for w_ord in (self.lbl_ordenar, self.cb_ordem, self.btn_sentido):
            w_ord.setVisible(False)  # só aparecem quando há mais de um resultado
        self._ordem_desc = False

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

        b_f4 = QPushButton("🖱  Selecionar lotes no mapa  (F4)")
        b_f4.setFixedHeight(25)
        b_f4.setToolTip("Deixa a camada de lotes ativa e a ferramenta de seleção pronta — "
                        "é só clicar no lote. Atalho: tecla F4.")
        b_f4.clicked.connect(self._on_selecionar_lotes)
        pq.addWidget(b_f4)

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

        pq.addWidget(linha_h())
        pq.addWidget(titulo_secao("Layouts de impressão (ABNT, A0 a A4)"))
        info_lay = QLabel("Clique no formato para gerar o PDF direto, com a área visível da tela, quadrícula, "
                          "legenda (só o que aparece no mapa), norte e escala. O lote selecionado sai com contorno pontilhado.")
        info_lay.setWordWrap(True)
        info_lay.setStyleSheet("font-size:9px;color:#666;")
        pq.addWidget(info_lay)
        from .layouts_tematicos import FORMATOS as _FMT
        grade_lay = QGridLayout()
        grade_lay.setSpacing(4)
        linha_ret = QHBoxLayout()
        linha_ret.setSpacing(4)
        self.btns_layout_pdf = []
        for i, (fmt, _w, _h, _m, orient) in enumerate(_FMT):
            b = QPushButton(fmt if orient == "Paisagem" else f"{fmt} retrato")
            b.setFixedHeight(25)
            b.setMinimumWidth(10)
            b.setToolTip(f"Gera o PDF do mapa em {fmt} {orient.lower()} (NBR 10068) e abre o arquivo.")
            b.clicked.connect(lambda _=False, n=i: self._on_layout_pdf(n))
            grade_lay.addWidget(b, 0, i) if orient == "Paisagem" else linha_ret.addWidget(b)
            self.btns_layout_pdf.append(b)
        pq.addLayout(grade_lay)
        pq.addLayout(linha_ret)
        b_lay = QPushButton("🖨  Criar os 7 layouts no projeto (editáveis)")
        b_lay.setToolTip("Não gera PDF: cria os layouts no projeto para você ajustar em Projeto › Gerenciador de layouts.")
        b_lay.setFixedHeight(25)
        b_lay.clicked.connect(self._on_gerar_layouts)
        pq.addWidget(b_lay)
        pq.addStretch()

        # ── Aba ATRIBUTOS ────────────────────────────────────────────────
        pa = pagina("Atributos")
        self._aba_atributos = self.tabs.count() - 1
        self.lbl_attr = QLabel("")
        self.lbl_attr.setStyleSheet("font-size:10px;font-weight:bold;color:#1a365d;")
        self.lbl_attr.setProperty("fonte_uniforme", True)
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

        # ── Aba WMS (camadas online mais usadas) ─────────────────────────
        from .wms import SERVICOS
        pw = pagina("WMS")
        self._aba_wms = self.tabs.count() - 1
        pw.addWidget(titulo_secao("Camadas online (precisam de internet)"))
        info_wms = QLabel("Abriu o plugin num projeto em branco? Adicione aqui o fundo de mapa que precisar. "
                          "Imagens de fundo ficam embaixo das camadas; sobreposições (ruas, trânsito) ficam em cima.")
        info_wms.setWordWrap(True)
        info_wms.setStyleSheet("font-size:9px;color:#666;")
        pw.addWidget(info_wms)
        self._btns_wms = {}
        for serv in SERVICOS:
            linha_w = QHBoxLayout()
            tx = QLabel("<b>%s</b><br><span style='color:#666'>%s</span>" % (serv["nome"], serv["descricao"]))
            tx.setStyleSheet("font-size:9px;")
            tx.setProperty("fonte_uniforme", True)
            tx.setWordWrap(True)
            linha_w.addWidget(tx, 1)
            bw = QPushButton("Adicionar")
            bw.setFixedSize(92, 26)
            bw.clicked.connect(lambda _=False, s=serv: self._on_wms_adicionar(s))
            linha_w.addWidget(bw)
            pw.addLayout(linha_w)
            self._btns_wms[serv["nome"]] = bw
        self.lbl_wms = QLabel("")
        self.lbl_wms.setWordWrap(True)
        self.lbl_wms.setStyleSheet("font-size:9px;color:#555;")
        pw.addWidget(self.lbl_wms)
        pw.addStretch()

        # ── Aba COMPLEMENTO (IBGE e rural; GeoPackage separado da base oficial) ──
        pc = pagina("Complemento")
        self._aba_complemento = self.tabs.count() - 1
        pc.addWidget(titulo_secao("Complemento – IBGE e Rural"))
        info_comp = QLabel(
            "Dados externos recortados para Dourados e municípios vizinhos, num arquivo separado da base oficial "
            "(~260 MB): IBGE (Censo 2022, CNEFE, setores, trajetos, Censo Agro 2017), CAR, INCRA, FUNAI, embargos, "
            "VTN, módulo fiscal e OpenStreetMap (vias, rios, redes), mais serviços online (CAR, FUNAI, IBGE BDiA, INPE, ANA, ANM, EPE e satélite).")
        info_comp.setWordWrap(True)
        info_comp.setStyleSheet("font-size:9px;color:#666;")
        pc.addWidget(info_comp)
        self.lbl_comp_status = QLabel("Verificando...")
        self.lbl_comp_status.setWordWrap(True)
        self.lbl_comp_status.setProperty("fonte_uniforme", True)
        pc.addWidget(self.lbl_comp_status)
        self.btn_comp_baixar = QPushButton("⬇  Baixar / atualizar o Complemento")
        self.btn_comp_baixar.setFixedHeight(28)
        estilizar_botao_azul(self.btn_comp_baixar)
        self.btn_comp_baixar.clicked.connect(self._on_complemento_baixar)
        pc.addWidget(self.btn_comp_baixar)
        self.prog_comp = QProgressBar()
        self.prog_comp.setVisible(False)
        pc.addWidget(self.prog_comp)
        self.lbl_comp_prog = QLabel("")
        self.lbl_comp_prog.setStyleSheet("font-size:9px;color:#555;")
        pc.addWidget(self.lbl_comp_prog)
        self.btn_comp_add = QPushButton("🗂  Adicionar as camadas ao projeto aberto")
        self.btn_comp_add.setFixedHeight(28)
        self.btn_comp_add.setToolTip("Cria o grupo \"Complemento – IBGE e Rural\" com as camadas já estilizadas. "
                                     "As camadas pesadas entram desligadas.")
        self.btn_comp_add.clicked.connect(self._on_complemento_adicionar)
        pc.addWidget(self.btn_comp_add)
        self.lbl_comp_msg = QLabel("")
        self.lbl_comp_msg.setWordWrap(True)
        self.lbl_comp_msg.setStyleSheet("font-size:9px;color:#555;")
        pc.addWidget(self.lbl_comp_msg)
        pc.addWidget(linha_h())
        lic = QLabel(
            "Fontes: IBGE; SICAR/Serviço Florestal Brasileiro; INCRA; FUNAI; IBAMA; Receita Federal. Dados pessoais "
            "(proprietários, CPF/CNPJ, responsáveis técnicos) não fazem parte do pacote. Imagem de satélite EOX "
            "Sentinel-2 cloudless: CC BY-NC-SA 4.0 (uso não comercial) – © EOX IT Services GmbH, contém dados "
            "Copernicus Sentinel modificados 2023. Esri World Imagery: © Esri, Maxar, Earthstar Geographics. Vias, rios, redes elétricas e telecom: © colaboradores do OpenStreetMap (ODbL).")
        lic.setWordWrap(True)
        lic.setStyleSheet("font-size:9px;color:#666;")
        pc.addWidget(lic)
        pc.addStretch()

        # ── Aba MAIS (rolável) ───────────────────────────────────────────
        from .atalhos import GRUPOS, URL_VALIDADOR_CNM, URL_CORREIOS_CEP
        area_mais = QScrollArea()
        area_mais.setWidgetResizable(True)
        area_mais.setFrameShape(QFrame.NoFrame)
        cont_mais = QWidget()
        pm = QVBoxLayout(cont_mais)
        pm.setContentsMargins(4, 6, 4, 4)
        pm.setSpacing(5)
        area_mais.setWidget(cont_mais)
        self.tabs.addTab(area_mais, "Mais")

        pm.addWidget(titulo_secao("Validadores"))
        lc = QHBoxLayout()
        lc.setSpacing(3)
        self.txt_cep = QLineEdit()
        self.txt_cep.setPlaceholderText("CEP (ex.: 79822-720)")
        self.txt_cep.setMaxLength(12)
        self.txt_cep.returnPressed.connect(self._on_validar_cep)
        lc.addWidget(self.txt_cep, 1)
        b_cep = QPushButton("Validar CEP")
        b_cep.setFixedHeight(24)
        b_cep.clicked.connect(self._on_validar_cep)
        lc.addWidget(b_cep)
        pm.addLayout(lc)
        lc2 = QHBoxLayout()
        lc2.setSpacing(3)
        b_eixo = QPushButton("🖱  CEP do eixo viário (clicar)")
        b_eixo.setFixedHeight(24)
        b_eixo.setStyleSheet("font-size:9px;")
        b_eixo.setToolTip("Não sabe o CEP? Clique aqui e depois numa rua no mapa: o CEP do eixo viário "
                          "é preenchido e validado. Botão direito cancela.")
        b_eixo.clicked.connect(self._on_cep_do_eixo)
        lc2.addWidget(b_eixo)
        b_lote = QPushButton("🏠  CEP da frente do lote")
        b_lote.setFixedHeight(24)
        b_lote.setStyleSheet("font-size:9px;")
        b_lote.setToolTip("Com um lote selecionado: acha a(s) rua(s) em frente a ele, pega o CEP e valida.")
        b_lote.clicked.connect(self._on_cep_do_lote)
        lc2.addWidget(b_lote)
        pm.addLayout(lc2)
        self.lbl_cep = QLabel("")
        self.lbl_cep.setWordWrap(True)
        self.lbl_cep.setStyleSheet("font-size:9px;")
        self.lbl_cep.setProperty("fonte_uniforme", True)
        pm.addWidget(self.lbl_cep)
        lv = QHBoxLayout()
        b_cnm = QPushButton("🔎  Validador de CNM (ONR)")
        b_cnm.setFixedHeight(24)
        b_cnm.setStyleSheet("font-size:9px;")
        b_cnm.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(URL_VALIDADOR_CNM)))
        lv.addWidget(b_cnm)
        b_corr = QPushButton("📮  CEP nos Correios")
        b_corr.setFixedHeight(24)
        b_corr.setStyleSheet("font-size:9px;")
        b_corr.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(URL_CORREIOS_CEP)))
        lv.addWidget(b_corr)
        pm.addLayout(lv)

        for nome_grupo, itens_grupo in GRUPOS:
            pm.addWidget(linha_h())
            pm.addWidget(titulo_secao(nome_grupo))
            grade = QGridLayout()
            grade.setSpacing(3)
            for i, (texto, url) in enumerate(itens_grupo):
                btn = QPushButton(texto)
                btn.setFixedHeight(24)
                btn.setStyleSheet("font-size:9px;")
                btn.setToolTip(url)
                btn.clicked.connect(lambda _checked, u=url: QDesktopServices.openUrl(QUrl(u)))
                grade.addWidget(btn, i // 2, i % 2)
            pm.addLayout(grade)

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
        b_info = QPushButton(f"ℹ  v{versao}" if versao else "ℹ")
        b_info.setToolTip(f"Versão {versao} do plugin. Clique para ver: sobre os dados e termos de uso."
                          if versao else "Sobre os dados e termos de uso")
        b_info.setFixedHeight(24)
        b_info.clicked.connect(self._on_sobre_dados)
        rod.addWidget(b_info)
        corpo.addLayout(rod)

        self._uniformizar_fontes(self.conteudo)
        self.scroll.setWidget(self.conteudo)
        main.addWidget(self.scroll, 1)
        main.addStretch(0)

    def _uniformizar_fontes(self, raiz):
        """Mesmo tamanho de texto em botões, abas, campos, caixas e títulos; só os textos de
        informação (cinza, tamanho 9px) e o rodapé ficam menores."""
        import re
        from qgis.PyQt.QtWidgets import QLabel as _L
        uni = f"{self._pt + 1:g}pt"

        def aplicar(w):
            css = re.sub(r"font-size:\s*[\d.]+(px|pt);?", "", w.styleSheet())
            w.setStyleSheet((css + ("" if css.endswith(";") or not css else ";") + f"font-size:{uni};")
                            if not isinstance(w, QPushButton) or "background" not in css else css)
            if isinstance(w, QPushButton) and "background" in css:
                f = w.font()
                f.setPointSizeF(self._pt + 1)
                w.setFont(f)
        for w in raiz.findChildren(QPushButton):
            if "17px" in w.styleSheet():
                continue
            aplicar(w)
        for tipo in (QCheckBox, QComboBox, QLineEdit):
            for w in raiz.findChildren(tipo):
                aplicar(w)
        for w in raiz.findChildren(_L):
            if w.property("fonte_uniforme"):
                aplicar(w)
        self.tabs.setStyleSheet(
            "QTabBar::tab{padding:4px 6px;}"
            "QTabBar::tab:selected{color:#1a365d;background:#ffffff;}")
        _ft = self.tabs.tabBar().font()
        _ft.setPointSizeF(self._pt + 1)
        self.tabs.tabBar().setFont(_ft)
        self.tabs.tabBar().setElideMode(Qt.ElideNone)
        self.tabs.tabBar().setUsesScrollButtons(False)

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
            self.btn_recolher.setText("«")
            self.btn_recolher.setToolTip("Expandir o painel")
            self.setMinimumWidth(0)
            dock.setMinimumWidth(0)
            dock.setMaximumWidth(self.LARGURA_RECOLHIDO)
            self.topo.layout().setContentsMargins(2, 4, 2, 0)
            self._header.setFixedSize(self.LARGURA_RECOLHIDO - 8, 24)
            self.btn_recolher.setFixedSize(24, 24)
            if not dock.isFloating():
                self.iface.mainWindow().resizeDocks([dock], [self.LARGURA_RECOLHIDO], Qt.Horizontal)
            else:
                dock.resize(self.LARGURA_RECOLHIDO, dock.height())
        else:
            self._recolhido = False
            self._header.setMinimumSize(0, 0)
            self._header.setMaximumSize(16777215, 16777215)
            self._header.setFixedHeight(34)
            self.btn_recolher.setFixedSize(24, 24)
            self.topo.layout().setContentsMargins(8, 8, 8, 0)
            self.scroll.show()
            for w in self._widgets_cabecalho():
                w.show()
            self.btn_recolher.setText("»")
            self.btn_recolher.setToolTip("Recolher o painel numa faixa estreita (clique em « para voltar)")
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
        # Cabeçalho em uma linha: título + brasão + 3 botões + margens.
        minimo_cab = self._larg_titulo + 26 + 3 * 24 + 4 * 4 + 12 + 16 + 2
        largura = max(self.conteudo.sizeHint().width() + 28, minimo_cab, 360)
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
        from . import busca
        self._itens_busca = itens
        lotes = bool(itens) and bool(itens[0].get("chaves"))
        criterios = busca.CRITERIOS_LOTE if lotes else busca.CRITERIOS_NOME
        atual = self.cb_ordem.currentData()
        self.cb_ordem.blockSignals(True)
        self.cb_ordem.clear()
        for rotulo, chave in criterios:
            self.cb_ordem.addItem(rotulo, chave)
        i = self.cb_ordem.findData(atual)
        self.cb_ordem.setCurrentIndex(i if i >= 0 else 0)
        self.cb_ordem.blockSignals(False)
        mostrar = len(itens) > 1
        for w in (self.lbl_ordenar, self.cb_ordem, self.btn_sentido):
            w.setVisible(mostrar)
        self.lbl_busca.setText(msg)
        self._preencher_lista()

    def _preencher_lista(self):
        from . import busca
        busca.ordenar(self._itens_busca, self.cb_ordem.currentData() or "inscricao", self._ordem_desc)
        self.lista_busca.clear()
        for i, it in enumerate(self._itens_busca):
            li = QListWidgetItem(it["rotulo"])
            li.setData(Qt.UserRole, i)
            self.lista_busca.addItem(li)
        self._ajustar_altura_lista()

    def _reordenar_resultados(self):
        if self._itens_busca:
            self._preencher_lista()

    def _alternar_sentido(self):
        self._ordem_desc = not self._ordem_desc
        self.btn_sentido.setText("↓" if self._ordem_desc else "↑")
        self._reordenar_resultados()

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
        self.tabs.setCurrentIndex(self._aba_atributos)

    def _indice_aba_atributos(self):
        return self._aba_atributos

    def _on_aba_mudou(self, indice):
        if indice == self._indice_aba_atributos():
            self._carregar_atributos()
        elif indice == getattr(self, "_aba_wms", -1):
            self._atualizar_wms()
        elif indice == getattr(self, "_aba_complemento", -1):
            self._atualizar_complemento()

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
        form = self._montar_formulario(camada, feat)
        self.lay_form.addWidget(form)
        self.lay_form.addStretch()
        self._form = form

    # Campos que nunca aparecem no formulário: os ocultos na tabela de atributos do
    # projeto (a MESMA configuração que a exportação usa pra tirá-los do GPKG público,
    # então o Fonte e o offline ficam iguais) + campos operacionais internos.
    CAMPOS_INTERNOS = {"fid", "situacao"}

    def _campos_ocultos(self, camada):
        ocultos = set(self.CAMPOS_INTERNOS)
        try:
            for c in camada.attributeTableConfig().columns():
                if c.hidden and c.name:
                    ocultos.add(c.name)
        except Exception:
            pass
        return ocultos

    def _texto_valor(self, camada, indice, valor):
        from qgis.core import QgsApplication, NULL
        if valor is None or valor == NULL:
            return ""
        try:
            cfg = camada.editorWidgetSetup(indice)
            fmt = QgsApplication.fieldFormatterRegistry().fieldFormatter(cfg.type())
            return str(fmt.representValue(camada, indice, cfg.config(), None, valor))
        except Exception:
            return str(valor)

    def _montar_formulario(self, camada, feat):
        w = QWidget()
        grade = QGridLayout(w)
        grade.setContentsMargins(6, 4, 6, 4)
        grade.setHorizontalSpacing(10)
        grade.setVerticalSpacing(4)
        grade.setColumnStretch(1, 1)
        ocultos = self._campos_ocultos(camada)
        linha = 0
        for i, campo in enumerate(camada.fields()):
            if campo.name() in ocultos:
                continue
            texto = self._texto_valor(camada, i, feat.attribute(i))
            rot = QLabel(camada.attributeDisplayName(i))
            rot.setStyleSheet("color:#4a5568;font-weight:bold;")
            rot.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            val = QLabel(texto if texto != "" else "—")
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            val.setStyleSheet("" if texto != "" else "color:#a0aec0;")
            grade.addWidget(rot, linha, 0)
            grade.addWidget(val, linha, 1)
            linha += 1
        return w

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
        # Mesmas regras do formulário: esconde os campos internos também na tabela
        # (sem alterar a configuração da camada).
        try:
            cfg = camada.attributeTableConfig()
            colunas = cfg.columns()
            for col in colunas:
                if col.name in self.CAMPOS_INTERNOS:
                    col.hidden = True
            cfg.setColumns(colunas)
            dv.setAttributeTableConfig(cfg)
        except Exception:
            pass
        self.lay_tabela.addWidget(dv, 1)
        self._dual = dv

    def _on_tabela_em_janela(self):
        if self._camada_tabela is None:
            self._carregar_atributos()
        if self._camada_tabela is not None:
            self.iface.showAttributeTable(self._camada_tabela)

    # ── F4 / WMS / Layouts / CEP ─────────────────────────────────────────
    def _on_selecionar_lotes(self):
        from .selecao import ativar_selecao_lotes
        ok, msg = ativar_selecao_lotes(self.iface)
        self.lbl_busca.setText(msg)

    def _atualizar_wms(self):
        from qgis.core import QgsProject
        from .wms import SERVICOS, camada_no_projeto
        projeto = QgsProject.instance()
        for serv in SERVICOS:
            b = self._btns_wms[serv["nome"]]
            ja = camada_no_projeto(projeto, serv) is not None
            b.setText("✓ No projeto" if ja else "Adicionar")
            b.setEnabled(not ja)

    def _atualizar_complemento(self):
        from . import complemento
        if complemento.instalado():
            self.lbl_comp_status.setText("✅ Instalado em: " + complemento.pasta() + "\nVerificando atualização...")
        else:
            self.lbl_comp_status.setText("Não instalado. Baixe para usar as camadas offline.")
        self.btn_comp_add.setEnabled(complemento.instalado())
        self._st_comp = ComplementoStatusWorker()
        self._st_comp.pronto.connect(self._on_complemento_status)
        self._st_comp.start()

    def _on_complemento_status(self, estado, msg):
        from . import complemento
        icone = {"ok": "✅", "atualizar": "🔄", "nao_instalado": "⬇", "sem_rede": "ℹ"}.get(estado, "")
        extra = ("\n" + complemento.pasta()) if complemento.instalado() else ""
        self.lbl_comp_status.setText(f"{icone} {msg}{extra}")
        self.btn_comp_baixar.setText("⬇  Atualizar o Complemento" if estado == "atualizar" else
                                     "⬇  Baixar o Complemento" if estado == "nao_instalado" else
                                     "⬇  Baixar de novo o Complemento")

    def _on_complemento_baixar(self):
        self.btn_comp_baixar.setEnabled(False)
        self.prog_comp.setVisible(True)
        self.prog_comp.setValue(0)
        self._w_comp = ComplementoWorker()
        self._w_comp.progress.connect(lambda v, m: (self.prog_comp.setValue(v), self.lbl_comp_prog.setText(m)))
        self._w_comp.finished.connect(self._on_complemento_baixado)
        self._w_comp.start()

    def _on_complemento_baixado(self, ok, erro):
        self.btn_comp_baixar.setEnabled(True)
        if not ok:
            self.prog_comp.setValue(0)
            QMessageBox.critical(self, "Erro no download do Complemento", erro)
            return
        self.prog_comp.setValue(100)
        self.lbl_comp_prog.setText("✅ Concluído!")
        self._atualizar_complemento()

    def _on_complemento_adicionar(self):
        from qgis.core import QgsProject
        from . import complemento
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ok, msg = complemento.adicionar_ao_projeto(QgsProject.instance())
        finally:
            QApplication.restoreOverrideCursor()
        self.lbl_comp_msg.setText(("✅ " if ok else "⚠ ") + msg)

    def _on_wms_adicionar(self, serv):
        from qgis.core import QgsProject
        from . import wms
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ok, msg = wms.adicionar(QgsProject.instance(), serv)
        finally:
            QApplication.restoreOverrideCursor()
        self.lbl_wms.setText(("✅ " if ok else "⚠ ") + msg)
        self._atualizar_wms()

    def _variaveis_layouts(self, projeto):
        """O módulo grava o responsável técnico (nome/CREA/ART) como variáveis do projeto e imprime
        no carimbo. Só o projeto Fonte (banco) usa os dados padrão do autor; nos demais fica em
        branco, pro usuário preencher em Projeto › Propriedades › Variáveis."""
        from qgis.core import QgsExpressionContextUtils
        from .camadas import camadas_principais
        lotes = camadas_principais(projeto)["lotes"]
        eh_fonte = lotes is not None and lotes.providerType() == "postgres"
        if not eh_fonte and not QgsExpressionContextUtils.projectScope(projeto).hasVariable("rt_nome"):
            return {"rt_nome": "", "rt_titulo": "", "rt_registro": "", "rt_art": "",
                    "contato": "geodourados@dourados.ms.gov.br"}
        return None

    def _on_layout_pdf(self, indice):
        """Gera o layout do formato escolhido, exporta o PDF e remove o layout provisório do projeto."""
        import re
        import time
        from qgis.core import QgsProject, QgsLayoutExporter
        from . import layouts_tematicos as lt
        projeto = QgsProject.instance()
        formato = lt.FORMATOS[indice]
        QApplication.setOverrideCursor(Qt.WaitCursor)
        layout = None
        try:
            res = lt.criar_layouts(self.iface.mapCanvas().extent(), projeto=projeto,
                                   variaveis=self._variaveis_layouts(projeto), formatos=[formato])
            layout = projeto.layoutManager().layoutByName(res[0][0])
            pasta = os.path.join(os.path.expanduser("~"), "Downloads", "GeoDourados - Mapas")
            os.makedirs(pasta, exist_ok=True)
            nome = re.sub(r"\W+", "_", f"Mapa_{formato[0]}_{formato[4]}_{time.strftime('%Y%m%d_%H%M%S')}")
            destino = os.path.join(pasta, nome + ".pdf")
            cfg = QgsLayoutExporter.PdfExportSettings()
            cfg.dpi = 200
            ok = QgsLayoutExporter(layout).exportToPdf(destino, cfg) == QgsLayoutExporter.Success
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Não foi possível gerar o mapa", str(e))
            ok, destino = False, ""
        else:
            QApplication.restoreOverrideCursor()
        finally:
            lt.limpar_temporarios(projeto, layout)
        if ok:
            QDesktopServices.openUrl(QUrl.fromLocalFile(destino))
            self.iface.messageBar().pushSuccess("Mapa Base", f"Mapa {formato[0]} {formato[4].lower()} gerado: {destino}")

    def _on_gerar_layouts(self):
        from qgis.core import QgsProject, QgsExpressionContextUtils
        from .camadas import camadas_principais
        projeto = QgsProject.instance()
        resp = QMessageBox.question(
            self, "Gerar layouts ABNT",
            "Serão criados (ou atualizados) 7 layouts de impressão, A0 a A4, com a área visível da tela "
            "e as camadas visíveis agora. Layouts com o mesmo nome serão substituídos.\n\nContinuar?",
            QMessageBox.Yes | QMessageBox.No)
        if resp != QMessageBox.Yes:
            return
        # O módulo grava o responsável técnico (nome/CREA/ART) como variáveis do projeto e imprime
        # no carimbo. Só o projeto Fonte (banco) usa os dados padrão do autor; nos demais fica em
        # branco, pro usuário preencher em Projeto › Propriedades › Variáveis.
        lotes = camadas_principais(projeto)["lotes"]
        eh_fonte = lotes is not None and lotes.providerType() == "postgres"
        variaveis = None
        if not eh_fonte and not QgsExpressionContextUtils.projectScope(projeto).hasVariable("rt_nome"):
            variaveis = {"rt_nome": "", "rt_titulo": "", "rt_registro": "", "rt_art": "",
                         "contato": "geodourados@dourados.ms.gov.br"}
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            from . import layouts_tematicos
            res = layouts_tematicos.criar_layouts(self.iface.mapCanvas().extent(), projeto=projeto, variaveis=variaveis)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Não foi possível gerar os layouts", str(e))
            return
        QApplication.restoreOverrideCursor()
        self.iface.messageBar().pushSuccess(
            "Mapa Base", f"{len(res)} layouts ABNT criados/atualizados — veja em Projeto › Gerenciador de layouts.")

    _cep_prefixo = ""

    def _on_validar_cep(self):
        self._validar_cep(self.txt_cep.text(), "")

    def _validar_cep(self, texto, prefixo):
        from qgis.core import QgsProject
        from . import cep
        cep8 = cep.normalizar(texto)
        if not cep8:
            self.lbl_cep.setText(prefixo + "❌ CEP inválido: informe os 8 dígitos (ex.: 79822-720).")
            return
        self._cep_atual = cep8
        self._cep_prefixo = prefixo
        self._cep_local = cep.buscar_local(QgsProject.instance(), cep8)
        self.lbl_cep.setText(prefixo + "Consultando os Correios...")
        self._cep_worker = CepWorker(cep8)
        self._cep_worker.pronto.connect(self._on_cep_pronto)
        self._cep_worker.start()

    def _on_cep_do_eixo(self):
        from .ferramentas import FerramentaClique
        canvas = self.iface.mapCanvas()
        self._ferr_anterior = canvas.mapTool()
        self._ferr_cep = FerramentaClique(canvas, self._ao_clicar_eixo)
        canvas.setMapTool(self._ferr_cep)
        self.lbl_cep.setText("🖱 Clique sobre uma rua (eixo viário) no mapa. Botão direito cancela.")

    def _ao_clicar_eixo(self, ponto):
        from qgis.core import QgsGeometry, QgsProject
        from . import cep
        canvas = self.iface.mapCanvas()
        # devolve a ferramenta que estava em uso
        if getattr(self, "_ferr_anterior", None) is not None:
            canvas.setMapTool(self._ferr_anterior)
        else:
            canvas.unsetMapTool(self._ferr_cep)
        if ponto is None:
            self.lbl_cep.setText("Cancelado.")
            return
        # 12 pixels, mas nunca menos de ~10 m: o usuário clica na pista, não exatamente no eixo.
        geografico = canvas.mapSettings().destinationCrs().isGeographic()
        tolerancia = max(canvas.mapUnitsPerPixel() * 12, 0.0001 if geografico else 10.0)
        achado = cep.eixo_no_ponto(QgsProject.instance(), QgsGeometry.fromPointXY(ponto),
                                   canvas.mapSettings().destinationCrs(), tolerancia)
        if achado is None:
            self.lbl_cep.setText("⚠ Nenhum eixo viário perto do clique. Aproxime o zoom e clique sobre a rua.")
            return
        canvas.flashGeometries([achado["geom"]], achado["crs"])
        if not achado["cep8"]:
            self.lbl_cep.setText(f"⚠ {achado['nome']}: este trecho não tem CEP cadastrado na base.")
            return
        self.txt_cep.setText(cep.formatar(achado["cep8"]))
        self._validar_cep(achado["cep8"], f"🛣 {achado['nome']} (eixo clicado)\n")

    def _on_cep_do_lote(self):
        from qgis.core import QgsProject
        from . import cep
        from .camadas import camadas_principais
        lotes = camadas_principais(QgsProject.instance())["lotes"]
        if lotes is None:
            self.lbl_cep.setText("⚠ Camada de lotes não encontrada no projeto aberto.")
            return
        sel = lotes.selectedFeatures()
        if len(sel) != 1:
            self.lbl_cep.setText("⚠ Selecione exatamente 1 lote (aba Buscar ou F4) e clique de novo.")
            return
        frentes = cep.eixos_da_frente(QgsProject.instance(), sel[0].geometry(), lotes.crs())
        if not frentes:
            self.lbl_cep.setText("⚠ Não encontrei eixo viário perto desse lote.")
            return
        self.iface.mapCanvas().flashGeometries([f["geom"] for f in frentes], frentes[0]["crs"])
        linhas = ["🏠 Frente do lote:"]
        for f in frentes:
            linhas.append(f"   • {f['nome']} — CEP {cep.formatar(f['cep8']) if f['cep8'] else 'não cadastrado'}"
                          f" ({f['distancia']:.0f} m)")
        com_cep = [f for f in frentes if f["cep8"]]
        prefixo = "\n".join(linhas) + "\n"
        if not com_cep:
            self.lbl_cep.setText(prefixo + "⚠ Nenhum dos trechos tem CEP cadastrado.")
            return
        if len(com_cep) > 1:
            prefixo += "(lote de esquina: validando o CEP do trecho mais próximo)\n"
        self.txt_cep.setText(cep.formatar(com_cep[0]["cep8"]))
        self._validar_cep(com_cep[0]["cep8"], prefixo)

    def _on_cep_pronto(self, dados, erro):
        from . import cep
        fmt = cep.formatar(self._cep_atual)
        linhas = []
        if self._cep_local:
            ruas = "; ".join(self._cep_local[:4]) + (" …" if len(self._cep_local) > 4 else "")
            linhas.append(f"✅ {fmt} consta na base de logradouros de Dourados: {ruas}")
        if erro:
            linhas.append("⚠ Sem conexão para consultar os Correios." if not self._cep_local
                          else "(Correios: sem conexão para confirmar.)")
        elif dados is None:
            linhas.append(f"❌ {fmt} não foi encontrado nos Correios." if not self._cep_local
                          else "(Os Correios não retornaram esse CEP.)")
        else:
            end = ", ".join(x for x in (dados.get("logradouro"), dados.get("bairro")) if x)
            cidade = f'{dados.get("localidade", "")}/{dados.get("uf", "")}'
            linhas.append(f"✅ Correios: {fmt}" + (f" — {end}" if end else "") + f" — {cidade}")
            if (dados.get("localidade") or "").strip().lower() != "dourados":
                linhas.append("⚠ Atenção: este CEP não é de Dourados.")
        self.lbl_cep.setText(self._cep_prefixo + "\n".join(linhas))

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
