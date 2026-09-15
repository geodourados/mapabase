import os

# Configuração central da rotina de atualização da base cartográfica pública.

# Caminho do GPKG de origem (gerado pelo processo interno de geoprocessamento,
# fora deste projeto). Configurável por variável de ambiente para funcionar
# tanto na máquina local quanto em outro servidor sem editar código.
SOURCE_GPKG_PATH = os.environ.get(
    "GEODOURADOS_GPKG_PATH", r"C:\GeoDourados-Fonte\Mapa_GeoDourados.gpkg"
)

# Cópia de trabalho dentro do repositório, usada para gerar os GeoJSON e para
# subir como asset da Release "latest". Não é versionada no git (.gitignore).
GPKG_LOCAL_PATH = "dados/gpkg/Mapa_GeoDourados.gpkg"

REPO = "geodourados/mapabase"

# Camadas do GPKG que devem ser publicadas também como GeoJSON individual.
# chave = nome da camada dentro do GPKG | valor = nome do arquivo .geojson gerado
#
# Desde 2026-09-15, o nome exportado pro GPKG é o nome ESTÁVEL da tabela do
# PostgreSQL (ver NOME_EXPORTACAO_POR_ID em mapabase-interno/scripts/
# exportar_gpkg.py) — não muda mais se a camada for renomeada no QGIS.
#   - "lotes_fiscais": schema de cadastro fiscal (insc_imob, matricula, zoneamento)
#   - "4_logradouros  atual_e_anterior": corresponde a mapa_cadastral.eixo_viario no
#     banco (fonte oficial confirmada pelo usuário) — nome de override manual, não
#     é o nome puro da tabela, porque duas camadas do projeto apontam pra essa
#     mesma tabela com filtros SQL diferentes.
CAMADAS_GEOJSON = {
    "lotes_fiscais": "lotes_fiscais",
    "4_logradouros  atual_e_anterior": "eixo_viario",
}

GEOJSON_DIR = "dados/geojson"

# Campos removidos da publicação pública — dados internos de operação, não
# informação da própria base cartográfica.
CAMPOS_OCULTOS = ["usuario_alteracao", "observacao"]

# Filtro aplicado a todas as camadas exportadas — só publica registros
# validados (situacao = 1).
FILTRO_WHERE = "situacao = 1"

# Estilo simplestyle-spec (https://github.com/mapbox/simplestyle-spec) aplicado
# a cada feature exportada — respeitado por GitHub, geojson.io, Leaflet, Mapbox.
ESTILOS = {
    "lotes_fiscais": {
        "stroke": "#1a365d",
        "stroke-width": 1,
        "stroke-opacity": 1,
        "fill": "#f6ad55",
        "fill-opacity": 0.35,
    },
    "eixo_viario": {
        "stroke": "#e53e3e",
        "stroke-width": 2,
        "stroke-opacity": 0.9,
    },
}
