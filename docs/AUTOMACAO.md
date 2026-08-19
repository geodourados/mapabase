# Automação — Publicação da Base Cartográfica

Documentação de referência da rotina que mantém a base cartográfica pública
de Dourados-MS atualizada automaticamente no GitHub, a partir da fonte
mantida localmente pelo Departamento de Geoprocessamento.

## Visão geral

```
GPKG de origem                 Máquina local                    GitHub
(GeoDourados-Offline)    →    scripts/publicar.py     →    geodourados/mapabase
C:\GeoDourados-Offline\        - copia o GPKG                - Release "latest"
Mapa_GeoDourados.gpkg          - gera GeoJSON                   (.gpkg + lotes_fiscais.geojson)
                                - publica no GitHub            - git (eixo_viario.geojson)
```

Não existe mais dependência de Google Drive. A fonte é o GPKG já mantido
atualizado localmente; a rotina só copia, converte e publica.

## Componentes

| Arquivo | Função |
|---|---|
| `scripts/config.py` | Configuração central: caminho do GPKG de origem, camadas exportadas, cores (simplestyle-spec) |
| `scripts/gerar_geojson.py` | Exporta `lotes_fiscais` e `eixo_viario` do GPKG para GeoJSON (via `ogr2ogr`), com estilo embutido |
| `scripts/publicar.py` | Orquestra tudo: copia o GPKG, gera os GeoJSON, publica na Release e commita o arquivo leve |
| `scripts/publicar.bat` | Ponto de entrada chamado pelo Task Scheduler |
| `scripts/listar_camadas.py` | Utilitário para conferir os nomes reais das camadas dentro de um GPKG |

## O que é publicado e onde

| Arquivo | Tamanho aprox. | Onde fica | Por quê |
|---|---|---|---|
| `Mapa_GeoDourados.gpkg` | ~200 MB | Release "latest" (asset) | Grande demais para git normal (limite de 100MB do GitHub) |
| `lotes_fiscais.geojson` | ~95 MB | Release "latest" (asset) | Mesma razão |
| `eixo_viario.geojson` | ~11 MB | git (`dados/geojson/`) | Pequeno — fica com histórico de versões e renderiza direto na página do GitHub |

**Por que Release em vez de Git LFS:** o conteúdo muda quase todo dia útil.
Git LFS grátis cobra por armazenamento acumulado (cada versão nova é uma
cópia inteira, sem limpeza automática) — estouraria a cota gratuita em
poucas semanas. Assets de Release não têm esse custo e mantêm URL estável.

## URLs estáveis para consumo (sync com outros sistemas)

```
https://github.com/geodourados/mapabase/releases/download/latest/Mapa_GeoDourados.gpkg
https://github.com/geodourados/mapabase/releases/download/latest/lotes_fiscais.geojson
https://raw.githubusercontent.com/geodourados/mapabase/main/dados/geojson/eixo_viario.geojson
```

Essas URLs nunca mudam — a cada publicação, o conteúdo por trás delas é
sobrescrito. Qualquer aplicação pode consumir via HTTP GET simples, sem
autenticação.

## Agendamento (Windows Task Scheduler)

Tarefa: **"GeoDourados - Publicar Base Cartografica"**

- **Gatilho 1:** diariamente às 06:00
- **Gatilho 2:** ao logar no Windows (cobre o caso do PC estar desligado/hibernado no horário programado)
- **StartWhenAvailable:** ativado — se o horário passou com a máquina desligada, roda assim que possível
- **Log de cada execução:** `C:\IA_Claude\mapabase\logs\publicar.log`

Comandos úteis (PowerShell):

```powershell
# Ver status da última execução
Get-ScheduledTaskInfo -TaskName "GeoDourados - Publicar Base Cartografica"

# Rodar manualmente, sem esperar o agendamento
Start-ScheduledTask -TaskName "GeoDourados - Publicar Base Cartografica"

# Ver/editar a tarefa na interface gráfica
taskschd.msc
```

## Autenticação com o GitHub

A publicação usa o `gh` CLI (GitHub CLI). Como a tarefa agendada roda sem
sessão interativa, ela **não usa** o login feito via `gh auth login`
(armazenado no keyring da sessão do usuário) — em vez disso, lê um token
pessoal (Personal Access Token) da variável de ambiente `GH_TOKEN`.

### Gerar/trocar o token

1. `https://github.com/settings/tokens` (logado como `geodourados`) → **Generate new token (classic)**
2. Escopo: apenas **`repo`**
3. Copiar o valor gerado (aparece uma única vez)
4. No PowerShell, como o próprio usuário:
   ```powershell
   [Environment]::SetEnvironmentVariable('GH_TOKEN', 'SEU_TOKEN_AQUI', 'User')
   ```

Isso é tudo — não é preciso reiniciar a tarefa, editar código ou reiniciar a
máquina. Como a tarefa agendada sempre inicia um processo novo, ela lê o
valor mais atual da variável automaticamente na próxima execução.

**Importante:** trate esse token como uma senha. Nunca cole o valor em
prints de tela, chats ou qualquer lugar fora do comando acima. Se ele for
exposto acidentalmente (print, mensagem, etc.), revogue-o em
`github.com/settings/tokens` e gere um novo — mesmo que ninguém mal-
intencionado tenha visto, é a prática padrão de segurança.

## Variáveis de ambiente usadas

| Variável | Obrigatória | Função |
|---|---|---|
| `GH_TOKEN` | Sim | Autenticação do `gh` CLI para publicar Release e (indiretamente) `git push` |
| `GEODOURADOS_GPKG_PATH` | Não | Sobrescreve o caminho do GPKG de origem (padrão: `C:\GeoDourados-Offline\Mapa_GeoDourados.gpkg`) — útil se a automação for movida para outro servidor |

## Requisitos da máquina

- Python 3 no PATH
- GDAL / `ogr2ogr` no PATH (neste ambiente, resolvido apontando para
  `C:\Program Files\PostgreSQL\16\bin`, que já traz o GDAL — ajustar em
  `scripts/publicar.bat` se a máquina mudar)
- `gh` CLI instalado (`winget install GitHub.cli`)
- Git configurado com acesso de push ao repositório

## Solução de problemas

**A tarefa rodou mas nada foi publicado / erro no log**
Abrir `logs\publicar.log` e ler o final do arquivo — a rotina para na
primeira falha e grava o traceback completo.

**Erro de autenticação do `gh` (`gh auth login` / 401 / 403)**
O `GH_TOKEN` não está definido, expirou ou foi revogado. Gerar um novo
seguindo a seção acima.

**GPKG de origem não encontrado**
Verificar se `C:\GeoDourados-Offline\Mapa_GeoDourados.gpkg` existe e está
acessível. Se o caminho mudou, definir `GEODOURADOS_GPKG_PATH` com o novo
local (mesmo comando `[Environment]::SetEnvironmentVariable`, trocando o
nome da variável).

**Camadas não encontradas no GPKG (`ogr2ogr` reclama de layer inexistente)**
O nome interno das camadas pode ter mudado. Rodar
`python scripts/listar_camadas.py` para conferir os nomes atuais e ajustar
`CAMADAS_GEOJSON` em `scripts/config.py`.

**Quero testar sem esperar o horário agendado**
```powershell
Start-ScheduledTask -TaskName "GeoDourados - Publicar Base Cartografica"
```
ou, para ver a saída em tempo real (sem passar pelo Task Scheduler):
```
cd C:\IA_Claude\mapabase
python scripts\publicar.py
```

## Histórico de decisões

- **Google Drive removido do fluxo** — a fonte já é local; manter o Drive
  como etapa intermediária exigiria uma segunda rotina só para atualizá-lo,
  redundante.
- **GitHub Actions descartado como executor principal** — dependia de
  baixar do Drive publicamente; a automação local é mais direta e evita
  manter duas rotinas de atualização em paralelo.
- **Coordenadas com 7 casas decimais** (`COORDINATE_PRECISION=7`, ~1cm de
  precisão) — reduz o tamanho dos GeoJSON sem perda relevante para uso
  urbano.
- **Estilo via simplestyle-spec** nas properties de cada feature — permite
  que GitHub, geojson.io, Leaflet e Mapbox renderizem as cores certas sem
  configuração adicional, sem exigir um formato proprietário.
