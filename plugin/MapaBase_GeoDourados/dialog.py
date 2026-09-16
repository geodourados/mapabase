import os

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QMessageBox, QFrame, QListWidget, QInputDialog, QLineEdit,
)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QUrl
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


class MapaBaseDialog(QDialog):
    def __init__(self, iface, on_fechar=None):
        super().__init__(iface.mainWindow())
        self.iface = iface
        self._on_fechar = on_fechar
        self.setWindowTitle("Mapa Base - GeoDourados")
        self.setWindowIcon(QIcon(os.path.join(PLUGIN_DIR, "icons", "icon.png")))
        self.setMinimumWidth(340)
        self.setModal(False)
        self._build_ui()
        self.atualizar_status()

    def closeEvent(self, event):
        if self._on_fechar:
            self._on_fechar()
        super().closeEvent(event)

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        corpo = QVBoxLayout()
        corpo.setContentsMargins(8, 8, 8, 8)
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
        tl.setWordWrap(False)
        hl.addWidget(tl)
        hl.addStretch()
        corpo.addWidget(header)

        # Status
        self.frm_status = QFrame()
        self.frm_status.setStyleSheet("border:1px solid #ccc;border-radius:4px;padding:4px;")
        sl = QHBoxLayout(self.frm_status)
        self.lbl_status = QLabel("Verificando...")
        self.lbl_status.setStyleSheet("font-size:10px;")
        sl.addWidget(self.lbl_status)
        corpo.addWidget(self.frm_status)

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

        btn_fechar = QPushButton("Fechar")
        btn_fechar.setFixedHeight(24)
        btn_fechar.clicked.connect(self.close)
        corpo.addWidget(btn_fechar)

        main.addLayout(corpo)

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
                self._set_status(f"✅ Instalado ({size_mb:.0f} MB) — {msg}", "#eafaf1", "#27ae60")
                self.btn_atualizar.setText("🔄  Verificar / Atualizar")
            self.btn_abrir_oficial.setEnabled(True)

        self._atualizar_lista_personalizados()

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

    def _on_download_finished(self, ok, erro):
        self.btn_atualizar.setEnabled(True)
        if not ok:
            self.prog_bar.setValue(0)
            QMessageBox.critical(self, "Erro no download", erro)
            return
        self.prog_bar.setValue(100)
        self.lbl_prog.setText("✅ Concluído!")
        self.atualizar_status()

    # ── Abrir projeto oficial ────────────────────────────────────────────
    def _on_abrir_oficial(self):
        from .sync import get_local_paths, PROJETO_NOME
        paths = get_local_paths()
        if not os.path.exists(paths["gpkg"]):
            QMessageBox.warning(self, "Não instalado", "Baixe o Mapa Base primeiro.")
            return
        uri = f"geopackage:{paths['gpkg']}?projectName={PROJETO_NOME}"
        self.iface.addProject(uri)
        self.close()

    # ── Croqui ───────────────────────────────────────────────────────────
    def _on_gerar_croqui(self, escala_fixa):
        from .sync import get_local_paths
        from . import croqui

        paths = get_local_paths()
        if not os.path.exists(paths["gpkg"]):
            QMessageBox.warning(self, "Não instalado", "Baixe o Mapa Base primeiro.")
            return

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
        self.close()

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
