# Plugin "Mapa Base - GeoDourados"

Plugin QGIS distribuído junto com a base cartográfica. Baixa e mantém
atualizada a base direto do GitHub público, avisa (ícone com badge na
barra de ferramentas) quando há versão nova toda vez que o QGIS abre, e
permite salvar um projeto personalizado separado da base oficial.

## Instalação

Não é feita manualmente pelo usuário final — o
[`Abrir_MapaBase.bat`](../Abrir_MapaBase.bat) (raiz do repositório) baixa
e instala este plugin automaticamente na primeira execução, sem precisar
reiniciar o QGIS manualmente (o próprio `.bat` já abre o QGIS logo em
seguida, o que conta como a "primeira abertura" que carrega o plugin).

## Publicando uma atualização do código do plugin

O `.zip` distribuído é um **asset da Release "latest"**, separado dos
dados (`Mapa_GeoDourados.gpkg`, `lotes_fiscais.geojson`) — só precisa ser
republicado quando o **código** deste plugin muda, não a cada publicação
diária de dados.

```powershell
Compress-Archive -Path "plugin\MapaBase_GeoDourados" -DestinationPath "plugin\MapaBase_GeoDourados_plugin.zip" -Force
```

```bash
gh release upload latest --repo geodourados/mapabase --clobber plugin/MapaBase_GeoDourados_plugin.zip
```

Usuários que já têm o plugin instalado recebem a versão nova na próxima
vez que rodarem `Abrir_MapaBase.bat` (ele sempre reinstala o plugin do
zero a partir do zip mais recente antes de baixar os dados).
