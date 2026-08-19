"""
Exporta as camadas configuradas do GPKG para GeoJSON individuais, reprojetando
para WGS84 (EPSG:4326, padrão do formato) e embutindo o estilo simplestyle-spec
nas properties de cada feature.
Requer GDAL (ogr2ogr) disponível no PATH.
"""
import json
import os
import sqlite3
import subprocess
import sys

from config import (
    CAMADAS_GEOJSON, CAMPOS_OCULTOS, ESTILOS, FILTRO_WHERE, GEOJSON_DIR, GPKG_LOCAL_PATH,
)

# Colunas de controle do GPKG que não são atributos da camada — nunca vão no -select.
COLUNAS_NAO_ATRIBUTO = {"fid", "geom"}


def campos_publicaveis(gpkg_path, camada):
    conn = sqlite3.connect(gpkg_path)
    conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
    cur = conn.cursor()
    cur.execute(f'PRAGMA table_info("{camada}")')
    colunas = [row[1] for row in cur.fetchall()]
    conn.close()
    return [
        c for c in colunas
        if c not in COLUNAS_NAO_ATRIBUTO and c not in CAMPOS_OCULTOS
    ]


def exportar_camada(gpkg_path, camada, saida_path):
    # O driver GeoJSON não suporta DeleteLayer, então -overwrite falha se o
    # arquivo já existir — removemos antes em vez de depender da flag.
    if os.path.exists(saida_path):
        os.remove(saida_path)

    campos = campos_publicaveis(gpkg_path, camada)
    comando = [
        "ogr2ogr",
        "-f", "GeoJSON",
        "-t_srs", "EPSG:4326",
        "-lco", "COORDINATE_PRECISION=7",  # ~1cm — suficiente para dados urbanos, reduz tamanho do arquivo
        "-select", ",".join(campos),  # exclui CAMPOS_OCULTOS (dados internos de operação)
        "-where", FILTRO_WHERE,  # só registros validados
        saida_path,
        gpkg_path,
        camada,
    ]
    subprocess.run(comando, check=True)


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
