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

    # git push via o Credential Manager do Windows trava indefinidamente em
    # sessão não-interativa (S4U) — ele tenta abrir um navegador pra OAuth e
    # não tem pra onde mostrar o prompt. Usa o GH_TOKEN direto via credential
    # helper inline (nunca escrito em disco) em vez de depender do GCM, e um
    # timeout como rede de segurança caso trave por outro motivo.
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        subprocess.run(
            [
                "git",
                "-c", "credential.helper=",
                "-c", "credential.helper=!f() { echo username=x-access-token; echo password=$GH_TOKEN; }; f",
                "push",
            ],
            check=True,
            env=env,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        log("ERRO: git push travou por mais de 120s — abortado. "
            "Verifique se GH_TOKEN está definido e válido.")
        sys.exit(1)


def main():
    copiar_gpkg_origem()
    gerar_geojson()
    publicar_release()
    commit_push_eixo_viario()
    log("Concluído.")


if __name__ == "__main__":
    main()
