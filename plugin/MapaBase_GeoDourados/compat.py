"""Compatibilidade QGIS 3.x (Qt5/PyQt5) e QGIS 4.x (Qt6/PyQt6).

- Enums do Qt: o código usa SEMPRE a forma com escopo (Qt.AlignmentFlag.AlignLeft, QFrame.Shape.NoFrame...), que
  funciona no PyQt5 (>= 5.11) e é obrigatória no PyQt6.
- Enums da API do QGIS: `E()` tenta primeiro o nome com escopo (QGIS >= 3.26/3.30, único que existe no QGIS 4) e cai
  no nome antigo nas versões mais velhas do QGIS 3.
- Classes que mudaram de módulo no Qt6 (QAction, QShortcut) são importadas daqui.
"""
from qgis.core import Qgis

try:                                   # Qt6: QAction e QShortcut estão em QtGui
    from qgis.PyQt.QtGui import QAction, QShortcut
except ImportError:                    # Qt5
    from qgis.PyQt.QtWidgets import QAction, QShortcut

QT6 = Qgis.QGIS_VERSION_INT >= 40000 if hasattr(Qgis, "QGIS_VERSION_INT") else False


def E(cls, grupo, nome, legado=None):
    """Valor de enum da API do QGIS: `cls.grupo.nome` (com escopo) ou, em QGIS antigo, o nome solto.
    `legado` = (classe, nome) quando o nome antigo mora em outro lugar. Retorna None se não existir."""
    try:
        return getattr(getattr(cls, grupo), nome)
    except AttributeError:
        pass
    outra, nome2 = legado if legado else (cls, nome)
    return getattr(outra, nome2, None)


def mensagem_aviso():
    return E(Qgis, "MessageLevel", "Warning", (Qgis, "Warning"))


def mensagem_info():
    return E(Qgis, "MessageLevel", "Info", (Qgis, "Info"))


def definir_figura(item, caminho):
    """QgsLayoutItemPicture.setPicturePath com o formato raster (assinatura nova, QGIS >= 3.32) ou sem ele."""
    formato = E(Qgis, "PictureFormat", "Raster")
    if formato is not None:
        try:
            item.setPicturePath(caminho, formato)
            return
        except TypeError:
            pass
    item.setPicturePath(caminho)
