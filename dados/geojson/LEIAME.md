# GeoJSON da base cartográfica de Dourados (aplicativo de fiscalização)

Arquivos para consumo direto (celular, web) pelo `raw.githubusercontent.com`, atualizados todo dia pela rotina
automática. Formato: GeoJSON RFC 7946, EPSG:4326 (WGS84), UTF-8, geometrias 2D com 6 casas decimais, sem
propriedades de estilo. Nomes de arquivos e campos são estáveis; mudanças serão avisadas antes.

Comece por **`indice.json`**: ele diz a data da atualização, o retângulo (`bbox`, em graus: oeste, sul, leste,
norte) e o total de feições de cada arquivo, para o app baixar só o que cobre a área da tela e só quando o arquivo
mudou (ETag).

| Arquivo | Conteúdo |
|---|---|
| `indice.json` | Data e cobertura de cada arquivo (`lotes`, `bic`, `camadas`) |
| `lotes/<distrito.setor>.geojson` | Lotes (`id`, `insc_imob`, `quadra_cartorio`, `lote_cartorio`, `matricula`, `circunscricao`, `zoneamento`, `condominio`, `area_geom`, `cnm`). Setor grande é dividido em `<setor>-1`, `-2`… por faixa de quadras; lotes sem inscrição válida ficam em `lotes/sem-inscricao.geojson` |
| `bic/<setor>.json` | Tabela do BIC **sem dados pessoais**, indexada pela inscrição do lote (`insc_lote`). Um registro por inscrição ou, havendo mais de uma unidade, uma lista de registros. Cada entrada do índice traz `faixa` (primeira e última quadra, `dd.ss.qq`) |
| `eixo_viario.geojson` | Eixo viário, **todas as situações** (campo `situacao`) |
| `quadras.geojson` | Quadras (`id`, `dszq`, `cartorio`, `localidade`, `setor`) |
| `loteamentos.geojson` | Loteamentos (`id`, `nome`, `registro`, `data_aprovacao`) |
| `zoneamento.geojson`, `perimetro_urbano.geojson` | Zoneamento (sigla e nome) e perímetro urbano |

Não fazem parte destes arquivos: nome ou documento de proprietário, responsável, endereço de correspondência e
valores tributários (LGPD).

Os dados são públicos (Lei municipal nº 4.390/2019 e Lei de Acesso à Informação), em atualização constante, e
**não substituem** documentos oficiais. Fonte: Prefeitura Municipal de Dourados-MS, SEPLAN, Departamento de
Geoprocessamento.
