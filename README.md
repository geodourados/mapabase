# Mapa Base — Dourados/MS (dados abertos)

Base cartográfica digital do município de Dourados-MS, instituída pela
**Lei nº 4.390/2019**, mantida atualizada automaticamente e disponibilizada
neste repositório para uso público — qualquer pessoa ou aplicação pode
consumir os arquivos diretamente, sem instalar plugin ou software específico.

Fonte oficial: Núcleo de Inteligência Geográfica — Departamento de
Geoprocessamento — Secretaria Municipal de Planejamento — Prefeitura
Municipal de Dourados-MS.

## Uso rápido no QGIS

Se você usa QGIS (Windows) e só quer abrir o mapa completo, sem se preocupar
com URLs: baixe e rode **[`Abrir_MapaBase.bat`](Abrir_MapaBase.bat)** — ele
baixa a versão mais recente e abre o projeto pronto no QGIS automaticamente.

## O que tem aqui

- **`dados/gpkg/Mapa_GeoDourados.gpkg`** — GeoPackage completo, com todas as
  camadas da base cartográfica municipal (~200 MB). Publicado como asset da
  [Release "latest"](https://github.com/geodourados/mapabase/releases/tag/latest)
  — não é versionado no git.
- **`dados/geojson/lotes_fiscais.geojson`** — cadastro fiscal completo (~100 MB).
  Também publicado como asset da Release "latest".
- **`dados/geojson/eixo_viario.geojson`** — sistema viário (~11 MB). Este fica
  versionado no próprio repositório git (arquivo pequeno, histórico de
  mudanças visível, renderiza direto na página do GitHub).

Os GeoJSON usam [simplestyle-spec](https://github.com/mapbox/simplestyle-spec)
nas properties de cada feature (`stroke`, `fill`, `fill-opacity` etc.), então
GitHub, [geojson.io](https://geojson.io), Leaflet e Mapbox já renderizam com
a cor correta automaticamente, sem configuração adicional.

## Atualização automática

Um workflow do GitHub Actions (`.github/workflows/atualizar_dados.yml`) roda
todos os dias úteis às 06:00 (horário de Campo Grande), baixa a versão mais
recente do GeoPackage oficial, regenera os GeoJSON e:

- sobrescreve os assets `.gpkg` e `lotes_fiscais.geojson` na Release "latest";
- commita `eixo_viario.geojson` no git, só se o conteúdo mudou.

## Consumindo os dados automaticamente (sync com apps)

Qualquer aplicação pode buscar a versão mais recente via HTTP, sem
autenticação. Os arquivos grandes ficam sempre na mesma URL (a Release
"latest" é sobrescrita a cada atualização, a URL nunca muda):

```
https://github.com/geodourados/mapabase/releases/download/latest/Mapa_GeoDourados.gpkg
https://github.com/geodourados/mapabase/releases/download/latest/lotes_fiscais.geojson
```

O eixo viário (arquivo leve, versionado em git) usa a URL "raw" padrão:

```
https://raw.githubusercontent.com/geodourados/mapabase/main/dados/geojson/eixo_viario.geojson
```

Exemplos de uso:

```bash
# baixar a versão mais recente do cadastro fiscal
curl -L -o lotes_fiscais.geojson \
  https://github.com/geodourados/mapabase/releases/download/latest/lotes_fiscais.geojson
```

```js
// Leaflet
fetch('https://raw.githubusercontent.com/geodourados/mapabase/main/dados/geojson/eixo_viario.geojson')
  .then(r => r.json())
  .then(geojson => L.geoJSON(geojson).addTo(map));
```

Para sincronização eficiente (evitar baixar de novo se nada mudou), use o
cabeçalho HTTP `If-None-Match`/`If-Modified-Since` — tanto assets de Release
quanto arquivos "raw" do GitHub respondem com `ETag`/`Last-Modified`.

## Termos de uso

Os dados são de responsabilidade da Secretaria de Planejamento de
Dourados-MS, disponibilizados nos termos da Lei nº 4.390/2019
(caráter ostensivo — Art. 9º). Consulte a lei para condições de uso por
terceiros: <http://leis.org/qzfuw>
