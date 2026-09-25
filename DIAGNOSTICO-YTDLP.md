# Diferença entre comando manual e aplicativo

## Evidência local

Comparação com a mesma URL de VOD da Kick já registrada no projeto e o comando `.venv\Scripts\python.exe -m yt_dlp --skip-download URL`:

- Execução restrita do agente: `WinError 10013`, antes de conseguir conectar ao endpoint.
- Execução no contexto normal de rede: `HTTP Error 404` retornado pela Kick.
- Execução restrita com o PATH copiado do contexto normal: continuou com `WinError 10013`.
- Nova chamada CLI do aplicativo, no contexto normal: `HTTP Error 404`, sem 10013.
- Servidor reiniciado no contexto normal e consulta pela API real: erro classificado como `kick_vod_incompatible`, fallback `import_local`.

Isso identifica a restrição de rede do contexto de execução como causa da diferença reproduzida. Não demonstra que todo possível 10013 em outras máquinas tenha a mesma causa. Um subprocesso herda as permissões do processo pai: trocar API por CLI, isoladamente, não remove uma restrição de rede.

## Comparação exata

| Item | Antes | Agora |
|---|---|---|
| Python do servidor | `iniciar.bat` já usa `.venv\Scripts\python.exe` | Mantido |
| Chamada yt-dlp | `yt_dlp.YoutubeDL(...).extract_info(...)` dentro da thread do servidor | Processo com caminho absoluto `<projeto>\.venv\Scripts\python.exe -m yt_dlp` |
| Local do pacote observado | `.venv\Lib\site-packages\yt_dlp` | Mesmo pacote, executado como módulo |
| CWD | Herdado do servidor; launcher muda para a pasta do projeto | Pasta absoluta do projeto explícita no subprocesso |
| Env/PATH | Herdados do servidor, sem alterações pelo app | `env=None`: herdados integralmente, sem ativação de venv nem alteração de PATH |
| Proxy | Sem configuração explícita no app; nenhum proxy encontrado na comparação | Sem flags de proxy nem mudanças em variáveis; usa resolução normal da CLI |
| Configuração yt-dlp | API não carrega automaticamente os arquivos de configuração da CLI | Descoberta normal da CLI, como no comando manual; sem `--ignore-config` |
| Processo | Sem subprocesso para yt-dlp; FFmpeg independente | `shell=False`, stdin fechado, stdout capturado, stderr temporário; `CREATE_NO_WINDOW` no Windows apenas evita janela extra |
| Rede/permissões | Servidor iniciado pelo agente em execução restrita | Servidor reiniciado no contexto normal; sem mudanças de firewall, proxy, certificados ou privilégios no código |

Os PATHs comparados tinham as mesmas entradas, embora a sequência/representação não fosse idêntica. As variáveis com assinaturas diferentes eram PATH e LESS; LESS não é alterada pelo aplicativo. Valores de ambiente sensíveis não foram registrados.

## Flags do aplicativo

Comuns: `--no-playlist --socket-timeout 30 --js-runtimes node -- URL`.

Metadados: `--skip-download --dump-single-json --ignore-no-formats-error --retries 2`. O JSON permite persistir os dados; as demais opções correspondem às opções anteriores da API.

Download: `--no-simulate --format bv*+ba/b --output <pasta>/source.%(ext)s --merge-output-format mkv --continue --no-overwrites --retries 3 --newline --progress --progress-template download:TUTUCO:%(progress._percent_str)s`. Mantém formato, retomada e preservação dos arquivos; a saída de progresso alimenta a interface. Quem baixa continua sendo exclusivamente yt-dlp.

O launcher permanece inalterado. Para uso normal, iniciar por `iniciar.bat` no Windows. Se o servidor for iniciado por ferramenta que imponha restrição de rede, seu subprocesso também herdará essa restrição. O app não tenta escalonar permissões ou contornar bloqueios automaticamente.

## Validação

51 testes Python e 4 testes JavaScript passaram; Ruff e verificação de sintaxe JavaScript passaram. Novos testes verificam executável absoluto do venv mesmo com PATH diferente, cwd, ausência de shell, herança de ambiente/proxy, flags de metadados/download, preservação da distinção 404/10013, erro sem venv e inicialização real do módulo instalado. Os testes anteriores foram adaptados apenas no ponto de mock do transporte (API interna para adaptador CLI), mantendo suas verificações.

Tratamento do 404, fallback local, campanhas, arquivos existentes e regras de aprovação não foram alterados. Nenhum downloader próprio ou alteração de proteção da Kick foi adicionado.
