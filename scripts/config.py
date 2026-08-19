# Configuração central da rotina de atualização da base cartográfica pública.

# ID do arquivo no Google Drive (mesmo GPKG distribuído pelo plugin QGIS oficial)
GDRIVE_FILE_ID = "1UisKbqD-61L1PVno5s2RYGJi7uJD3U0l"

GPKG_LOCAL_PATH = "dados/gpkg/Mapa_GeoDourados.gpkg"

# Camadas do GPKG que devem ser publicadas também como GeoJSON individual.
# chave = nome da camada dentro do GPKG | valor = nome do arquivo .geojson gerado
# Confirmado em 2026-08-19 direto no GPKG local (C:\GeoDourados-Offline):
#   - "3_lotes": schema de cadastro fiscal (insc_imob, matricula, zoneamento) — 120.327 registros
#   - "4_logradouros  atual_e_anterior": corresponde a mapa_cadastral.eixo_viario no banco
#     (7.518 registros) — fonte oficial confirmada pelo usuário
CAMADAS_GEOJSON = {
    "3_lotes": "lotes_fiscais",
    "4_logradouros  atual_e_anterior": "eixo_viario",
}

GEOJSON_DIR = "dados/geojson"

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
