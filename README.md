# rodikil-obs-studio

Cenas, overlays e configuração do OBS do canal **Rodikil**, versionados no Git.
O repositório é a fonte da verdade: com ele, qualquer PC Windows com OBS fica igual ao estúdio principal em poucos minutos.

- **Cenas** → `scenes/*.json`, aplicadas no OBS por `scripts/apply_scene.py` (via WebSocket, idempotente)
- **Overlays** → `overlays/` (HTML/CSS/JS locais: telas, moldura da câmera, chat, alertas, intros, fundo da webcam)
- **Perfil de saída** → `obs-config/profile/` (1080p60, NVENC CBR 9000, AAC 160), aplicado por `scripts/setup_obs_profile.py`
- **Identidade visual** → `brand/` (tokens + logos) e `identidade-visual/` (originais)

Detalhes de arquitetura, regras e tokens: [CLAUDE.md](CLAUDE.md).

## Máquina nova

Pré-requisitos: **OBS Studio 30+**, **Python 3.10+** (marque *Add to PATH*) e **Git**.

```powershell
git clone <URL-do-repositorio> rodikil-obs-studio
cd rodikil-obs-studio
```

1. **Abra e feche o OBS uma vez** (ele cria o perfil "Sem nome").
2. **Com o OBS fechado**, rode o setup:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\setup_machine.ps1
   ```
   Cria o `.venv`, instala as dependências, cria o `.env`, instala o plugin de recorte de fundo
   (versão fixa, conferida por SHA-256) e aplica o perfil de saída.
3. **Abra o OBS** → *Ferramentas › Configurações do servidor WebSocket* → ative, copie a senha e cole em
   `OBS_PASSWORD` no `.env`.
4. **Microfone:** rode `.venv\Scripts\python scripts\test_connection.py --devices`, copie o ID do Fifine para
   `MIC_DEVICE_ID` no `.env`.
5. **Cenas:**
   ```powershell
   .venv\Scripts\python scripts\apply_scene.py --all --dry-run
   .venv\Scripts\python scripts\apply_scene.py --all
   ```
   Rode de novo para conferir: a 2ª execução não pode mostrar nenhum `+`.
6. **No OBS, uma vez por máquina** (não dá para versionar):
   - `Webcam_Main` → *Propriedades* → escolha a webcam.
   - *Configurações › Transmissão* → conecte a conta do YouTube.
   - Áudio: o setup já desativa o Áudio Global (desktop e mic são fontes de cena). Confira em *Configurações › Áudio*.

## Roteiro da live

| Momento | Cena | Como |
|---|---|---|
| 10–15 min antes | **Iniciando** (música, sem mic) | Painel › INICIANDO, depois ● INICIAR LIVE (confirma em 2 cliques) |
| Hora de começar | **Intro** (7 s) → **Resenha** | Painel › **▶ ABRIR LIVE** (ou o atalho global do script) |
| Achou partida | **Dota 2** / **CS2** (mic aberto) | Painel › tecla 3 / 4 |
| Pausa | **Intervalo** (sem mic) | Painel › 5 |
| Fim | **Encerrando** → ■ ENCERRAR LIVE | Painel › 6, depois encerrar (2 cliques) |

### Painel Rodikil (controle visual)
`painel/index.html` — botões grandes para as cenas, ABRIR LIVE, mic e iniciar/encerrar, com tempo, kbps, frames
perdidos e CPU. Dentro do OBS: *Docas › Docas de navegador personalizadas* → nome `Painel Rodikil`, URL
`file:///C:/caminho/do/repo/painel/index.html` → na 1ª vez digite a senha do WebSocket (fica só nesta máquina).
Atalhos com o painel em foco: `1–6` cenas · `I` abrir live · `M` mic.

### Painel no celular (Stream Deck)
```powershell
.venv\Scripts\python scripts\painel_servidor.py
```
Abra no celular (mesmo Wi-Fi) o endereço que aparecer (`http://IP-DO-PC:8787/painel/index.html`), digite a senha do
WebSocket uma vez e use *Adicionar à tela inicial*. O servidor só entrega o painel — nunca o `.env` nem o resto do repo.

### Atalhos globais (funcionam com o jogo em foco)
Todos vêm do script `obs-config/scripts/rodikil-intro.lua` e levam a cena **direto para o ar**, mesmo no Modo
Estúdio (os atalhos nativos de cena do OBS só mudam a Prévia). Com o OBS **fechado**:
`.venv\Scripts\python scripts\setup_obs_hotkeys.py` — grava o mapa de `obs-config/hotkeys.json` (o `setup_machine.ps1` já faz isso).

| Tecla | Ação |
|---|---|
| `Ctrl+Alt+1` … `6` | Iniciando, Resenha, Dota 2, CS2, Intervalo, Encerrando |
| `Ctrl+Alt+0` ou `Ctrl+Alt+I` | Abrir live (intro → Resenha) |
| `Ctrl+Alt+M` | Microfone liga/desliga |
| `Ctrl+Alt+F1` … `F6` | Reações: GG, CLUTCH, F, PATETA, HYPE, TILTOU |
| `Ctrl+Alt+C` | Salvar clipe dos últimos 40 s |

### Reações com som
`overlays/reacoes/index.html` (fonte `Overlay_Reacoes`, no topo das cenas de live). Dispare pelos atalhos acima
ou pela seção **REAÇÕES** do Painel. Para ver/ouvir no navegador, abra o arquivo e clique nos botões do rodapé.

### LivePix
No painel do LivePix copie os links dos widgets de **alerta** e de **QR Code** e cole no `.env`:
`LIVEPIX_ALERTA_URL=` e `LIVEPIX_QRCODE_URL=`. Depois aplique as cenas. Sem os links, os itens ficam desativados.
O alerta aparece nas cenas de live e na Resenha. O QR Code entra num cartão Rodikil "MANDA UM PIX //"
(`overlays/livepix/qr-card.html`): fixo no Iniciando e no Intervalo (`Overlay_PixCard`) e, nas cenas de jogo,
aparecendo a cada 10 min por 25 s (`Overlay_PixCardJogo` — ajuste `a`, `d`, `p` na URL em `scenes/sources.json`).

### Assistente da live (chat sempre pronto + clipes)
Dê dois cliques em `iniciar-assistente.cmd` (ou coloque um atalho dele em `shell:startup` para ligar com o Windows).
- **Chat:** a cada minuto acha a live atual de `@RODIKIL` e aponta o chat da Resenha para ela — nada de copiar link.
- **Clipe:** `Ctrl+Alt+C` ou o botão **✂ CLIPE** do Painel salva os últimos **40 s** (Replay Buffer, liga sozinho quando a
  live começa). O arquivo vai para `<pasta de gravação>/Clipes Rodikil/` e, com o **ffmpeg** instalado
  (`winget install Gyan.FFmpeg`), sai também a versão **vertical 1080x1920** para Shorts (webcam em cima, jogo embaixo).
- Log em `logs/assistente.log`.

## Dia a dia

| Tarefa | Comando |
|---|---|
| Conferir conexão | `.venv\Scripts\python scripts\test_connection.py` |
| Aplicar uma cena | `.venv\Scripts\python scripts\apply_scene.py scenes\lives\dota.json` |
| Aplicar tudo | `.venv\Scripts\python scripts\apply_scene.py --all` |
| Salvar no Git um ajuste feito no OBS | `.venv\Scripts\python scripts\export_snapshot.py "Live - Dota 2"` (compare e leve para o JSON) |
| Reaplicar perfil de saída (OBS fechado) | `.venv\Scripts\python scripts\setup_obs_profile.py` |
| Chat de uma live nova | troque o `v=` de `YOUTUBE_CHAT_URL` no `.env` e aplique `scenes\base\resenha.json` |

Fluxo recomendado: mude o JSON/overlay → `--dry-run` → aplique → confira no OBS → **commit**.

## O que NÃO vai para o Git

| Item | Onde fica |
|---|---|
| Senha do WebSocket, ID do microfone, link do chat | `.env` (ignorado; modelo em `.env.example`) |
| Chave de transmissão e login do YouTube | perfil do OBS (`service.json`) — nunca copie para o repo |
| Escolha da webcam / janelas | no próprio OBS |
| Gravações e vídeos | `D:/TRANSMISSOES` (extensões de vídeo são ignoradas) |
