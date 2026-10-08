"""Avisos legais e de qualidade dos dados exibidos pelo plugin."""
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtWidgets import QDialog, QPushButton, QTextBrowser, QVBoxLayout

CHAVE_VISTO = "MapaBaseGeoDourados/aviso_dados_visto_v1"

AVISO_CURTO = (
    "Dados públicos (Lei nº 4.390/2019 e Lei de Acesso à Informação). Base em "
    "atualização constante: pode conter erros ou imprecisões. Não substitui "
    "documentos oficiais."
)

AVISO_HTML = """
<style>
  body{font-family:Arial,sans-serif;font-size:11px;color:#222}
  h3{color:#1a365d;margin:4px 0 6px 0}
  h4{color:#1a5276;margin:10px 0 3px 0}
  p{margin:3px 0}
  .box{border-left:4px solid #1a365d;background:#eaf4fb;padding:6px 10px;margin:6px 0}
  .warn{border-left:4px solid #e67e22;background:#fef9e7;padding:6px 10px;margin:6px 0}
</style>

<h3>Sobre os dados — leia antes de usar</h3>

<div class="box">
  <b>Dados públicos.</b> A base cartográfica do Município de Dourados foi instituída pela
  <b>Lei nº 4.390, de 17 de dezembro de 2019</b>, e seus elementos têm <b>caráter ostensivo</b>
  (Art. 9º). A disponibilização também observa a <b>Lei de Acesso à Informação</b>
  (Lei nº 12.527/2011).<br>
  Lei municipal: <a href="http://leis.org/qzfuw">http://leis.org/qzfuw</a>.
  Consulte-a para as condições de utilização dos dados por terceiros.
</div>

<div class="warn">
  <b>&#9888; Base em atualização constante — pode conter erros ou imprecisões.</b><br>
  Os dados vêm de digitalizações em geoprocessamento, restituição aerofotogramétrica e
  outros processos de produção cartográfica, e estão sempre em revisão. Pode haver
  omissões, deslocamentos, diferenças de área e informações defasadas. Confira a data de
  atualização da base (exibida no rodapé do croqui).
</div>

<h4>Uso adequado</h4>
<p>&bull; Este material <b>não substitui</b> documentos oficiais: matrícula, certidões,
levantamento topográfico/georreferenciado, projetos aprovados ou parecer técnico.</p>
<p>&bull; Não use como prova de propriedade, posse ou de limites de imóveis.</p>
<p>&bull; Antes de decisões que dependam de precisão (compra, construção, parcelamento),
confirme a informação junto à Prefeitura e nos documentos oficiais.</p>

<h4>Desenvolvimento do plugin</h4>
<div class="box">
  <b>Ênio Alencar da Silva</b> — Geógrafo<br>
  Núcleo de Inteligência Geográfica<br>
  Departamento de Geoprocessamento<br>
  Secretaria Municipal de Planejamento (SEPLAN)<br>
  Prefeitura Municipal de Dourados-MS<br>
  E-mail: <a href="mailto:enio.silva@dourados.ms.gov.br">enio.silva@dourados.ms.gov.br</a><br>
  GeoDourados: <a href="mailto:geodourados@dourados.ms.gov.br">geodourados@dourados.ms.gov.br</a><br>
  GeoPortal: <a href="https://geoportal.dourados.ms.gov.br/portal/apps/sites/#/home/">geoportal.dourados.ms.gov.br</a><br>
  Código e atualizações: <a href="https://github.com/geodourados/mapabase">github.com/geodourados/mapabase</a><br>
  Versão do plugin: <b>@VERSAO@</b>
</div>

<h4>Responsabilidade</h4>
<p>Os dados são de responsabilidade da Secretaria Municipal de Planejamento de Dourados-MS
(Departamento de Geoprocessamento). Este plugin atua apenas como meio de distribuição
técnica e não coleta nem transmite dados pessoais.</p>
"""


def mostrar_aviso_dados(parent=None):
    dlg = QDialog(parent)
    dlg.setWindowTitle("Sobre o plugin, os dados e termos de uso")
    dlg.resize(520, 520)
    lay = QVBoxLayout(dlg)
    navegador = QTextBrowser()
    navegador.setOpenExternalLinks(True)
    try:
        from .sync import versao_plugin_local
        versao = versao_plugin_local() or "?"
    except Exception:
        versao = "?"
    navegador.setHtml(AVISO_HTML.replace("@VERSAO@", versao))
    lay.addWidget(navegador)
    btn = QPushButton("Entendi")
    btn.setFixedHeight(28)
    btn.clicked.connect(dlg.accept)
    lay.addWidget(btn)
    dlg.exec_()
    QSettings().setValue(CHAVE_VISTO, True)


def mostrar_aviso_primeira_vez(parent=None):
    if not QSettings().value(CHAVE_VISTO, False, type=bool):
        mostrar_aviso_dados(parent)
