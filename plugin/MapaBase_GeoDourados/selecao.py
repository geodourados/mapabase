"""Atalho F4: deixa a camada de lotes ativa e a ferramenta de seleção pronta."""
from qgis.core import QgsProject

from .camadas import camadas_principais


def ativar_selecao_lotes(iface):
    """Ativa a camada de lotes (tornando-a visível) e a ferramenta "Selecionar feição".
    Retorna (ok, mensagem)."""
    projeto = QgsProject.instance()
    lotes = camadas_principais(projeto)["lotes"]
    if lotes is None:
        return False, "Camada de lotes não encontrada no projeto aberto."
    no = projeto.layerTreeRoot().findLayer(lotes.id())
    if no is not None:
        no.setItemVisibilityCheckedParentRecursive(True)
    iface.setActiveLayer(lotes)
    iface.actionSelect().trigger()
    return True, f'Camada "{lotes.name()}" ativa — clique no lote para selecioná-lo.'
