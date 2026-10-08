"""Atalhos (hiperlinks) exibidos na aba Mais.

Os grupos do GeoPortal reproduzem os botões da página
https://geoportal.dourados.ms.gov.br/portal/home/index.html (mesmos hiperlinks).
"""

GRUPOS = [
    ("GeoPortal", [
        ("🗺  Acesse o GeoPortal", "https://geoportal.dourados.ms.gov.br/portal/apps/sites/#/home/"),
        ("✉  Contato (GeoDourados)", "mailto:geodourados@dourados.ms.gov.br"),
    ]),
    ("Prefeitura", [
        ("Portal da Prefeitura", "https://www.dourados.ms.gov.br/"),
        ("Carta de Serviços", "https://cidadao.dourados.ms.gov.br/index.php?class=CartaServico"),
        ("Câmara Municipal", "https://www.camaradourados.ms.gov.br/"),
        ("Leis Municipais", "https://leismunicipais.com.br/prefeitura/ms/dourados"),
        ("Acesso a Informação", "https://transparencia.betha.cloud/#/yJ9y3J_D09niojsx99D7Dw==/acesso-informacao"),
        ("Transparência", "https://www.dourados.ms.gov.br/index.php/transparencia/"),
        ("Ouvidoria", "https://www.dourados.ms.gov.br/index.php/ouvidoria/"),
        ("Diário Oficial", "https://do.dourados.ms.gov.br/"),
    ]),
    ("Cidadão e Servidor", [
        ("Cidadão Web - BETHA", "https://e-gov.betha.com.br/cdweb/03114-513/contribuinte/main.faces"),
        ("Protocolo - BETHA", "https://protocolo.betha.cloud/#/cidadao/solicitacao-abertura/"),
        ("Portal do Cidadão", "https://cidadao.dourados.ms.gov.br/"),
        ("Cidadão - RI Digital", "https://ridigital.org.br/"),
        ("Servidor - BETHA", "https://betha.cloud/"),
        ("Protocolo - AprovaDigital", "https://dourados.aprova.com.br/"),
        ("Servidor - Ofício Eletrônico", "https://oficioeletronico.com.br/"),
        ("Servidor - RI Digital", "https://ridigital.org.br/Convenios/DefaultConvenio.aspx?from=menu"),
    ]),
    ("Geoinformação e outros", [
        ("Central de Atend. ao Cidadão", "https://cac.dourados.ms.gov.br/"),
        ("Diretório de Geoinformação", "https://dados.geo.dourados.ms.gov.br/"),
        ("SIG-RI - Mapa ONR", "https://mapa.onr.org.br/"),
        ("IBGE Cidades", "https://www.ibge.gov.br/cidades-e-estados/ms/dourados.html"),
    ]),
    ("Mapas do IBGE (Dourados)", [
        ("Mapa municipal 2020 (PDF)",
         "https://geoftp.ibge.gov.br/cartas_e_mapas/mapas_municipais/colecao_de_mapas_municipais/2020/MS/dourados/5003702_MM.pdf"),
        ("Mapa municipal estatístico 2007 (PDF)",
         "https://geoftp.ibge.gov.br/cartas_e_mapas/mapas_para_fins_de_levantamentos_estatisticos/"
         "contagem_da_populacao_e_censo_agropecuario_2007/mapas_municipais_estatisticos/ms/dourados.pdf"),
        ("Setores censitários – Censo 2022",
         "https://geoftp.ibge.gov.br/cartas_e_mapas/mapas_para_fins_de_levantamentos_estatisticos/"
         "censo_demografico_2022/mapas_e_descritivos_de_setores_censitarios/MS/5003702/"),
        ("Mapa urbano estatístico – Censo 2022",
         "https://geoftp.ibge.gov.br/cartas_e_mapas/mapas_para_fins_de_levantamentos_estatisticos/"
         "censo_demografico_2022/mapas_urbanos_estatisticos/MS/dourados_5003702/"),
    ]),
    ("Certidões (CAC)", [
        ("📄  CND (Certidão Negativa)", "https://cac.dourados.ms.gov.br/emissoes/documentos/certidao-negativa/imovel"),
        ("💰  Valor Venal", "https://cac.dourados.ms.gov.br/emissoes/documentos/certidao-venal"),
    ]),
]

URL_VALIDADOR_CNM = "https://cnm.onr.org.br/index.php"
URL_CORREIOS_CEP = "https://buscacepinter.correios.com.br/app/endereco/index.php"
