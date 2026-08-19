"""
Rotina diária local: copia o GPKG de origem, gera os GeoJSON e publica tudo
no GitHub (Release "latest" para os arquivos grandes, git para o leve).

Não depende de Google Drive nem de nenhum serviço externo — a fonte é o GPKG
já mantido atualizado localmente pelo processo de geoprocessamento.

Uso: python scripts/publicar.py
Variável de ambiente opcional: GEODOURADOS_GPKG_PATH (caminho do GPKG de origem)
"""
import os
import shutil
import subprocess
import sys

from config import GEOJSON_DIR, GPKG_LOCAL_PATH, REPO, SOURCE_GPKG_PATH
from gerar_geojson import main as gerar_geojson


def log(msg):
    print(f"[publicar] {msg}", flush=True)


def copiar_gpkg_origem():
    if not os.path.exists(SOURCE_GPKG_PATH):
        log(f"ERRO: GPKG de origem não encontrado em {SOURCE_GPKG_PATH}")
        log("Defina a variável de ambiente GEODOURADOS_GPKG_PATH se o arquivo estiver em outro local.")
        sys.exit(1)

    os.makedirs(os.path.dirname(GPKG_LOCAL_PATH), exist_ok=True)
    log(f"Copiando {SOURCE_GPKG_PATH} -> {GPKG_LOCAL_PATH}")
    shutil.copyfile(SOURCE_GPKG_PATH, GPKG_LOCAL_PATH)


def publicar_release():
    lotes = os.path.join(GEOJSON_DIR, "lotes_fiscais.geojson")

    view = subprocess.run(
        ["gh", "release", "view", "latest", "--repo", REPO],
        capture_output=True,
    )
    if view.returncode != 0:
        log("Release 'latest' não existe ainda — criando...")
        subprocess.run(
            [
                "gh", "release", "create", "latest",
                "--repo", REPO,
                "--title", "Base cartográfica — versão mais recente",
                "--notes", "Atualizado automaticamente. Sempre aponte para 'latest', não para uma versão fixa.",
            ],
            check=True,
        )

    log("Publicando GPKG e lotes_fiscais.geojson na Release 'latest'...")
    subprocess.run(
        ["gh", "release", "upload", "latest", "--repo", REPO, "--clobber", GPKG_LOCAL_PATH, lotes],
        check=True,
    )


def commit_push_eixo_viario():
    eixo = os.path.join(GEOJSON_DIR, "eixo_viario.geojson")
    subprocess.run(["git", "add", eixo], check=True)

    diff = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if diff.returncode == 0:
        log("eixo_viario.geojson sem mudanças — nada para commitar.")
        return

    log("Commitando e enviando eixo_viario.geojson...")
    subprocess.run(
        ["git", "commit", "-m", "Atualização automática do eixo viário"],
        check=True,
    )
    subprocess.run(["git", "push"], check=True)


def main():
    copiar_gpkg_origem()
    gerar_geojson()
    publicar_release()
    commit_push_eixo_viario()
    log("Concluído.")


if __name__ == "__main__":
    main()
