"""Ferramentas de mapa do painel."""
from qgis.gui import QgsMapToolEmitPoint
from qgis.PyQt.QtCore import Qt


class FerramentaClique(QgsMapToolEmitPoint):
    """Um clique no mapa: chama ao_clicar(QgsPointXY em coordenadas do mapa); botão direito
    cancela (ao_clicar(None))."""

    def __init__(self, canvas, ao_clicar):
        super().__init__(canvas)
        self._ao_clicar = ao_clicar
        self.setCursor(Qt.CursorShape.CrossCursor)

    def canvasReleaseEvent(self, evento):
        if evento.button() == Qt.MouseButton.RightButton:
            self._ao_clicar(None)
        elif evento.button() == Qt.MouseButton.LeftButton:
            self._ao_clicar(self.toMapCoordinates(evento.pos()))
