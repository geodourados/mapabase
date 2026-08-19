"""
Exporta as camadas configuradas do GPKG para GeoJSON individuais, reprojetando
para WGS84 (EPSG:4326, padrão do formato) e embutindo o estilo simplestyle-spec
nas properties de cada feature.
Requer GDAL (ogr2ogr) disponível no PATH.
"""
import json
import os
import subprocess
import sys

from config import CAMADAS_GEOJSON, ESTILOS, GEOJSON_DIR, GPKG_LOCAL_PATH


def exportar_camada(gpkg_path, camada, saida_path):
    # O driver GeoJSON não suporta DeleteLayer, então -overwrite falha se o
    # arquivo já existir — removemos antes em vez de depender da flag.
    if os.path.exists(saida_path):
        os.remove(saida_path)
    subprocess.run(
        [
            "ogr2ogr",
            "-f", "GeoJSON",
            "-t_srs", "EPSG:4326",
            "-lco", "COORDINATE_PRECISION=7",  # ~1cm — suficiente para dados urbanos, reduz tamanho do arquivo
            saida_path,
            gpkg_path,
            camada,
        ],
        check=True,
    )


def aplicar_estilo(geojson_path, estilo):
    with open(geojson_path, "r", encoding="utf-8") as f:
        dados = json.load(f)

    for feature in dados.get("features", []):
        feature.setdefault("properties", {})
        feature["properties"].update(estilo)

    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, separators=(",", ":"))


def main():
    if not os.path.exists(GPKG_LOCAL_PATH):
        print(f"ERRO: GPKG não encontrado em {GPKG_LOCAL_PATH}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(GEOJSON_DIR, exist_ok=True)

    for camada, nome_saida in CAMADAS_GEOJSON.items():
        destino = os.path.join(GEOJSON_DIR, f"{nome_saida}.geojson")
        print(f"Exportando '{camada}' -> {destino}")
        exportar_camada(GPKG_LOCAL_PATH, camada, destino)

        estilo = ESTILOS.get(nome_saida)
        if estilo:
            aplicar_estilo(destino, estilo)
            print(f"  estilo aplicado: {estilo}")


if __name__ == "__main__":
    main()
