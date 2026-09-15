import os

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
    QMessageBox, QFrame, QFileDialog,
)
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtGui import QIcon, QPixmap

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
        main.addWidget(header)

        corpo = QVBoxLayout()
        corpo.setContentsMargins(8, 8, 8, 8)
        corpo.setSpacing(5)

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

        # Projeto personalizado
        linha = QFrame()
        linha.setFrameShape(QFrame.HLine)
        corpo.addWidget(linha)

        lbl_pers = QLabel("Meu projeto personalizado")
        lbl_pers.setStyleSheet("font-weight:bold;font-size:10px;color:#1a365d;")
        corpo.addWidget(lbl_pers)

        lbl_pers_info = QLabel(
            "Adicionou camadas ou mudou estilos? Salve seu projeto aqui — ele fica "
            "separado da base oficial, então atualizar a base não sobrescreve suas mudanças."
        )
        lbl_pers_info.setWordWrap(True)
        lbl_pers_info.setStyleSheet("font-size:9px;color:#666;")
        corpo.addWidget(lbl_pers_info)

        linha_botoes = QHBoxLayout()
        self.btn_salvar_pers = QPushButton("💾  Salvar projeto atual")
        self.btn_salvar_pers.setFixedHeight(25)
        self.btn_salvar_pers.clicked.connect(self._on_salvar_personalizado)
        linha_botoes.addWidget(self.btn_salvar_pers)

        self.btn_abrir_pers = QPushButton("📂  Abrir meu projeto")
        self.btn_abrir_pers.setFixedHeight(25)
        self.btn_abrir_pers.clicked.connect(self._on_abrir_personalizado)
        linha_botoes.addWidget(self.btn_abrir_pers)
        corpo.addLayout(linha_botoes)

        self.lbl_pers_status = QLabel("")
        self.lbl_pers_status.setStyleSheet("font-size:9px;color:#888;")
        corpo.addWidget(self.lbl_pers_status)

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

        pers_existe = os.path.exists(paths["projeto_personalizado"])
        self.btn_abrir_pers.setEnabled(pers_existe)
        if pers_existe:
            import datetime
            mtime = os.path.getmtime(paths["projeto_personalizado"])
            data = datetime.datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
            self.lbl_pers_status.setText(f"Último salvo em {data}")
        else:
            self.lbl_pers_status.setText("Nenhum projeto personalizado salvo ainda.")

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

    # ── Projeto personalizado ────────────────────────────────────────────
    def _on_salvar_personalizado(self):
        from qgis.core import QgsProject
        from .sync import get_local_paths
        paths = get_local_paths()
        os.makedirs(paths["dir"], exist_ok=True)

        resp = QMessageBox.question(
            self, "Salvar projeto personalizado",
            "Isso salva o projeto ABERTO ATUALMENTE no QGIS como seu projeto "
            "personalizado (separado da base oficial). Continuar?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        ok = QgsProject.instance().write(paths["projeto_personalizado"])
        if ok:
            QMessageBox.information(self, "Salvo", "Projeto personalizado salvo com sucesso.")
            self.atualizar_status()
        else:
            QMessageBox.critical(self, "Erro", "Não foi possível salvar o projeto.")

    def _on_abrir_personalizado(self):
        from .sync import get_local_paths
        paths = get_local_paths()
        if not os.path.exists(paths["projeto_personalizado"]):
            QMessageBox.warning(self, "Não encontrado", "Você ainda não salvou um projeto personalizado.")
            return
        self.iface.addProject(paths["projeto_personalizado"])
        self.close()
