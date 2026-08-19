"""
Lista as camadas reais dentro do GPKG baixado — rode uma vez para confirmar
os nomes usados em scripts/config.py (CAMADAS_GEOJSON).
"""
import sqlite3
import sys

from config import GPKG_LOCAL_PATH


def listar(gpkg_path):
    conn = sqlite3.connect(gpkg_path)
    cur = conn.cursor()
    cur.execute("SELECT table_name, data_type FROM gpkg_contents ORDER BY table_name")
    linhas = cur.fetchall()
    conn.close()
    return linhas


if __name__ == "__main__":
    for nome, tipo in listar(GPKG_LOCAL_PATH):
        print(f"{tipo:10s} {nome}")
