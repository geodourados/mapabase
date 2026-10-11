"""
Arquivos para o aplicativo mobile FiscalApp Obras (Fiscalização de Obras da SEPLAN).
Requisitos: docs/requisitos-base-cartografica.md.

Gera em dados/geojson/ (dentro do repositório, não em release):
  indice.json                  data e cobertura (bbox) de cada arquivo
  eixo_viario.geojson          TODAS as situações (campo `situacao` mantido)
  quadras.geojson              contorno + número cartorial + setor
  loteamentos.geojson          nome, registro, data_aprovacao (sem proprietário)
  zoneamento.geojson, perimetro_urbano.geojson
  lotes/<distrito.setor>.geojson   um arquivo por setor (prefixo da insc_imob)
  bic/<distrito.setor>.json        gerado por exportar_bic.py (QGIS headless, só com campos liberados)

Formato: GeoJSON RFC 7946 (EPSG:4326, UTF-8), 2D, 6 casas decimais, sem propriedades de estilo.
Saída determinística (mesma ordem, mesmo texto) para o git só versionar o que mudou.
Requer ogr2ogr no PATH (o _config.bat da rotina já inclui o do PostgreSQL 16).
"""
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from config import GEOJSON_DIR, GPKG_LOCAL_PATH

LOTES_CAMPOS = ["id", "insc_imob", "quadra_cartorio", "lote_cartorio", "matricula", "circunscricao",
                "zoneamento", "condominio", "area_geom", "cnm"]
CAMPOS_NAO_ATRIBUTO = {"fid", "geom"}
CAMPOS_OCULTOS_EIXO = {"usuario_alteracao", "observacao"}

# arquivo -> (camada do GPKG, campos, filtro); camadas inteiras, sem divisão
CAMADAS = {
    "quadras.geojson": ("quadras_fiscais", ["id", "dszq", "cartorio", "localidade"], "situacao = 1"),
    # sem `proprietario` e demais campos internos do cadastro de loteamentos (LGPD)
    "loteamentos.geojson": ("loteamentos", ["id", "nome", "registro", "data_aprovacao"], None),
    "zoneamento.geojson": ("zoneamento", ["id", "nome", "sigla"], None),
    "perimetro_urbano.geojson": ("perimetro_urbano", ["id", "codigo", "nome", "lei", "ano"], None),
}
LIMITE_DIVISAO_MB = 9      # setor maior que isso é dividido em faixas de quadras
LIMITE_MB = 10          # aviso se um arquivo passar disso (comprimido pelo GitHub fica bem menor)


def log(msg):
    print(f"[geojson-app] {msg}", flush=True)


def ogr(saida, camada, sql=None, select=None, where=None):
    if os.path.exists(saida):
        os.remove(saida)
    os.makedirs(os.path.dirname(saida), exist_ok=True)
    cmd = ["ogr2ogr", "-f", "GeoJSON", "-t_srs", "EPSG:4326", "-dim", "XY", "-skipfailures",
           "-lco", "RFC7946=YES", "-lco", "COORDINATE_PRECISION=6", "-lco", "WRITE_BBOX=NO"]
    if sql:
        cmd += ["-sql", sql]
    else:
        if select:
            cmd += ["-select", ",".join(select)]
        if where:
            cmd += ["-where", where]
    cmd += [saida, GPKG_LOCAL_PATH]
    if not sql:
        cmd.append(camada)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(saida):
        raise RuntimeError(f"ogr2ogr falhou em {camada}: {r.stderr[-400:]}")


def _caixa(coords, caixa):
    if coords and isinstance(coords[0], (int, float)):
        x, y = coords[0], coords[1]
        caixa[0], caixa[1] = min(caixa[0], x), min(caixa[1], y)
        caixa[2], caixa[3] = max(caixa[2], x), max(caixa[3], y)
    else:
        for c in coords:
            _caixa(c, caixa)


def resumo(caminho):
    """(total de feições, bbox [minx,miny,maxx,maxy] em graus) do GeoJSON gerado."""
    with open(caminho, encoding="utf-8") as f:
        d = json.load(f)
    caixa = [180.0, 90.0, -180.0, -90.0]
    for ft in d.get("features", []):
        g = ft.get("geometry")
        if g:
            _caixa(g.get("coordinates", []), caixa)
    bbox = [round(v, 6) for v in caixa] if caixa[0] <= caixa[2] else None
    return len(d.get("features", [])), bbox


def _tabela(camada):
    con = sqlite3.connect(f"file:{GPKG_LOCAL_PATH}?mode=ro", uri=True)
    con.text_factory = lambda b: b.decode("utf-8", errors="replace")
    return con


def contagem_por_quadra():
    """{setor 'dd.ss': [(prefixo 'dd.ss.qq', lotes), ...]} dos lotes com inscrição no padrão."""
    con = _tabela("lotes_fiscais")
    try:
        out = {}
        for pref, n in con.execute(
                "SELECT SUBSTR(insc_imob, 1, 8), COUNT(*) FROM lotes_fiscais "
                "WHERE situacao = 1 AND insc_imob LIKE '__.__.%' GROUP BY 1 ORDER BY 1"):
            out.setdefault(pref[:5], []).append((pref, n))
        return out
    finally:
        con.close()


def faixas(quadras, partes):
    """Agrupa as quadras (em ordem) em `partes` faixas com número parecido de lotes."""
    total = sum(n for _p, n in quadras)
    alvo, acum, faixa, saida = total / partes, 0, [], []
    for pref, n in quadras:
        faixa.append(pref)
        acum += n
        if acum >= alvo * (len(saida) + 1) and len(saida) < partes - 1:
            saida.append(faixa)
            faixa = []
    if faixa:
        saida.append(faixa)
    return saida


def _where_faixa(setor, prefixos):
    # prefixos têm largura fixa: a ordem alfabética é a ordem numérica
    return (f"situacao = 1 AND insc_imob >= '{prefixos[0]}.' AND insc_imob < '{prefixos[-1]}/' "
            f"AND insc_imob LIKE '{setor}.%'")


def gerar_lotes(destino, indice):
    pasta = os.path.join(destino, "lotes")
    os.makedirs(pasta, exist_ok=True)
    por_quadra = contagem_por_quadra()
    gerados = set()
    for setor, quadras in por_quadra.items():
        arq = os.path.join(pasta, f"{setor}.geojson")
        ogr(arq, "lotes_fiscais", select=LOTES_CAMPOS, where=f"situacao = 1 AND insc_imob LIKE '{setor}.%'")
        mb = os.path.getsize(arq) / 1048576
        if mb <= LIMITE_DIVISAO_MB or len(quadras) < 2:
            total, bbox = resumo(arq)
            indice["lotes"][setor] = {"arquivo": f"lotes/{setor}.geojson", "bbox": bbox, "total": total,
                                      "faixa": [quadras[0][0], quadras[-1][0]]}
            gerados.add(f"{setor}.geojson")
            continue
        os.remove(arq)                                    # grande demais: divide por faixa de quadras
        partes = faixas(quadras, int(mb // LIMITE_DIVISAO_MB) + 1)
        for k, pref in enumerate(partes, 1):
            chave = f"{setor}-{k}"
            arq = os.path.join(pasta, f"{chave}.geojson")
            ogr(arq, "lotes_fiscais", select=LOTES_CAMPOS, where=_where_faixa(setor, pref))
            total, bbox = resumo(arq)
            indice["lotes"][chave] = {"arquivo": f"lotes/{chave}.geojson", "bbox": bbox, "total": total,
                                      "faixa": [pref[0], pref[-1]]}
            gerados.add(f"{chave}.geojson")
    # lotes sem inscrição válida (vazia, "-" ou fora do padrão): ficam fora do índice por setor
    arq = os.path.join(pasta, "sem-inscricao.geojson")
    ogr(arq, "lotes_fiscais", select=LOTES_CAMPOS,
        where="situacao = 1 AND (insc_imob IS NULL OR insc_imob NOT LIKE '__.__.%')")
    total, bbox = resumo(arq)
    indice["lotes"]["sem-inscricao"] = {"arquivo": "lotes/sem-inscricao.geojson", "bbox": bbox, "total": total,
                                        "faixa": None}
    gerados.add("sem-inscricao.geojson")
    for velho in os.listdir(pasta):                       # arquivo de setor/faixa que deixou de existir
        if velho.endswith(".geojson") and velho not in gerados:
            os.remove(os.path.join(pasta, velho))
    log(f"lotes: {len(gerados)} arquivos, {sum(v['total'] for v in indice['lotes'].values())} lotes")


def gerar_eixo(destino):
    con = _tabela("eixo")
    colunas = [r[1] for r in con.execute('PRAGMA table_info("4_logradouros  atual_e_anterior")')]
    con.close()
    campos = [c for c in colunas if c not in CAMPOS_NAO_ATRIBUTO and c not in CAMPOS_OCULTOS_EIXO]
    arq = os.path.join(destino, "eixo_viario.geojson")
    ogr(arq, "4_logradouros  atual_e_anterior", select=campos)        # todas as situações
    return arq


def acrescentar_setor(caminho):
    """Quadras: `setor` (distrito.setor) = prefixo do campo dszq, para o app escolher o arquivo certo."""
    with open(caminho, encoding="utf-8") as f:
        d = json.load(f)
    for ft in d["features"]:
        dszq = ft["properties"].get("dszq") or ""
        ft["properties"]["setor"] = dszq[:5] if len(dszq) >= 5 else None
    linhas = ",\n".join(json.dumps(ft, ensure_ascii=False, separators=(",", ":")) for ft in d["features"])
    with open(caminho, "w", encoding="utf-8", newline="\n") as f:
        f.write('{"type":"FeatureCollection","features":[\n' + linhas + "\n]}\n")


BIC_ENTRADA = "dados/bic_publico.json"       # gerado por exportar_bic.py (fora do git); só campos liberados


def gerar_bic(destino, indice):
    """Divide a tabela do BIC (sem dados pessoais) em bic/<chave>.json, cada um com no máximo ~9 MB.
    No indice.json cada entrada traz `faixa` = [primeira, última] quadra (dd.ss.qq) que ela cobre."""
    pasta = os.path.join(destino, "bic")
    if not os.path.exists(BIC_ENTRADA):
        if os.path.isdir(pasta):
            for nome in sorted(os.listdir(pasta)):          # sem entrada nova: só reindexa o que já existe
                if nome.endswith(".json"):
                    with open(os.path.join(pasta, nome), encoding="utf-8") as f:
                        d = json.load(f)
                    ks = sorted(k[:8] for k in d)
                    indice["bic"][nome[:-5]] = {"arquivo": f"bic/{nome}", "total": len(d),
                                                "faixa": [ks[0], ks[-1]] if ks else None}
        return
    with open(BIC_ENTRADA, encoding="utf-8") as f:
        todos = json.load(f)
    por_setor = {}
    for insc in sorted(todos):
        por_setor.setdefault(insc[:5], []).append(insc)
    grupos = {}                                           # chave -> lista de inscrições
    for setor, inscs in por_setor.items():
        mb = len(json.dumps({k: todos[k] for k in inscs}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) / 1048576
        quadras = {}
        for k in inscs:
            quadras[k[:8]] = quadras.get(k[:8], 0) + 1
        if mb <= LIMITE_DIVISAO_MB or len(quadras) < 2:
            grupos[setor] = inscs
            continue
        for n, pref in enumerate(faixas(sorted(quadras.items()), int(mb // LIMITE_DIVISAO_MB) + 1), 1):
            ini, fim = pref[0], pref[-1]
            grupos[f"{setor}-{n}"] = [k for k in inscs if ini <= k[:8] <= fim]
    os.makedirs(pasta, exist_ok=True)
    for velho in os.listdir(pasta):
        if velho.endswith(".json") and velho[:-5] not in grupos:
            os.remove(os.path.join(pasta, velho))
    for chave, inscs in grupos.items():
        arq = os.path.join(pasta, f"{chave}.json")
        with open(arq, "w", encoding="utf-8", newline="\n") as f:
            json.dump({k: todos[k] for k in inscs}, f, ensure_ascii=False, separators=(",", ":"))
        indice["bic"][chave] = {"arquivo": f"bic/{chave}.json", "total": len(inscs),
                                "faixa": [inscs[0][:8], inscs[-1][:8]]}
    log(f"bic: {len(grupos)} arquivos, {sum(len(v) for v in grupos.values())} inscrições")


def main():
    if not os.path.exists(GPKG_LOCAL_PATH):
        log(f"ERRO: GPKG não encontrado em {GPKG_LOCAL_PATH}")
        sys.exit(1)
    destino = GEOJSON_DIR
    fuso = timezone(timedelta(hours=-4))
    indice = {"atualizado": datetime.now(fuso).isoformat(timespec="seconds"),
              "lotes": {}, "bic": {}, "camadas": {}}

    gerar_lotes(destino, indice)
    arquivos = {"eixo_viario.geojson": gerar_eixo(destino)}
    for nome, (camada, campos, filtro) in CAMADAS.items():
        arq = os.path.join(destino, nome)
        ogr(arq, camada, select=campos, where=filtro)
        arquivos[nome] = arq
    acrescentar_setor(os.path.join(destino, "quadras.geojson"))
    for nome, arq in arquivos.items():
        total, bbox = resumo(arq)
        indice["camadas"][nome] = {"arquivo": nome, "bbox": bbox, "total": total}
        log(f"{nome}: {total} feições, {os.path.getsize(arq) / 1048576:.1f} MB")
    gerar_bic(destino, indice)

    grandes = [(os.path.relpath(os.path.join(r, n), destino), os.path.getsize(os.path.join(r, n)) / 1048576)
               for r, _d, fs in os.walk(destino) for n in fs if n != "lotes_fiscais.geojson"
               and os.path.getsize(os.path.join(r, n)) > LIMITE_MB * 1048576]
    for nome, mb in grandes:
        log(f"AVISO: {nome} tem {mb:.1f} MB (acima de ~{LIMITE_MB} MB; no GitHub trafega comprimido)")

    with open(os.path.join(destino, "indice.json"), "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, indent=1)
        f.write("\n")
    log("indice.json gravado.")


if __name__ == "__main__":
    main()
