# Mapa Base — Dourados/MS (dados abertos)

Base cartográfica digital do município de Dourados-MS, instituída pela
**Lei nº 4.390/2019**, mantida atualizada automaticamente e disponibilizada
neste repositório para uso público — qualquer pessoa ou aplicação pode
consumir os arquivos diretamente, sem instalar plugin ou software específico.

Fonte oficial: Núcleo de Inteligência Geográfica — Departamento de
Geoprocessamento — Secretaria Municipal de Planejamento — Prefeitura
Municipal de Dourados-MS.

## Não tem o QGIS instalado?

Baixe o **QGIS Portable** (~650 MB, já vem com o plugin Mapa Base instalado e não precisa de instalação):

<https://github.com/geodourados/mapabase/releases/download/latest/QGIS_Portable_MapaBase.zip>

Descompacte em qualquer pasta e abra **`Abrir_QGIS_MapaBase.bat`**. No plugin, clique em *Baixar Mapa Base* e depois em *Abrir projeto oficial*.

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

Dados públicos, também observada a Lei de Acesso à Informação (Lei nº 12.527/2011).

> **Atenção — base em atualização constante.** Pode conter erros, omissões ou
> imprecisões: os dados vêm de digitalizações em geoprocessamento, restituição
> aerofotogramétrica e outros processos de produção cartográfica. **Não substitui**
> matrícula, certidões, levantamento topográfico/georreferenciado nem projetos
> aprovados, e não deve ser usada como prova de propriedade, posse ou limites.
> Confirme junto à Prefeitura antes de decisões que dependam de precisão.

## 📜 Licença e Uso

Os dados deste repositório são **dados públicos de caráter ostensivo**, instituídos pela **Lei Ordinária nº 4.390, de 17 de dezembro de 2019** (Art. 9º), e estão licenciados sob **Creative Commons Atribuição 4.0 Internacional (CC BY 4.0)**.

É permitido o download, uso, adaptação e redistribuição dos dados, inclusive para fins comerciais, **mediante atribuição da fonte**:

> "Base Cartográfica do Município de Dourados/MS — Prefeitura Municipal de Dourados (Lei 4.390/2019, CC BY 4.0). Fonte: https://github.com/geodourados/mapabase/"

Consulte o arquivo [LICENSE.md](LICENSE.md) para detalhes completos.

> **Dados de terceiros.** A licença acima vale para os dados da base cartográfica da Prefeitura. O pacote opcional
> "Complemento IBGE e Rural" (Release `complemento`) reúne dados de outras fontes — IBGE, SICAR/Serviço Florestal
> Brasileiro, INCRA, FUNAI, IBAMA, Receita Federal e OpenStreetMap (ODbL) —, que mantêm as licenças e as atribuições
> de origem, listadas na aba Complemento do plugin e na tabela `pacote_camadas` do GeoPackage.

