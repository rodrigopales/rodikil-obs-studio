# rodikil-obs-studio

Sistema declarativo e versionado das cenas, overlays e perfis de gravação do OBS Studio do canal **Rodikil**
(lives de CS2, Dota 2, GTA 6, Fullace; gravações de curiosidades e resenha).
O Git é a fonte da verdade: cenas são JSON, overlays são HTML/CSS/JS locais, e scripts Python aplicam tudo no OBS via WebSocket v5.

## Arquitetura

```
identidade-visual/     PNGs originais da identidade (referência — não editar)
brand/
  brand-tokens.json    Tokens visuais oficiais (cores, fontes, forma, regras) — fonte única
  assets/              Logos, símbolo, marca d'água, brilho.svg usados pelos overlays
overlays/
  shared/theme.css     Variáveis CSS + componentes (pílula, elipse, órbita, brilho, fundo espacial)
  shared/rodikil.js    Helpers: param() e campo de estrelas determinístico
  starting-screen/     Telas cheias 1920x1080: iniciando.html, intervalo.html, encerrando.html, resenha.html
  camera-frame/        Moldura da câmera 720x480 (furo 640x360 em x=40,y=100)
  chat-frame/          Moldura do chat 480x800 (área do feed 420x656 em x=30,y=72) + feed.css do chat do YouTube
  alerts-frame/        Alertas 900x260 (inscrito, superchat, membro, raid)
  lower-third/         Faixa de nome 1100x200
  webcam-bg/           Fundo virtual 1920x1080 (Overlay_WebcamBg) atrás da Webcam_Main
  intro/               Intros com som sintetizado (Web Audio): opcao-1-orbita, opcao-2-glitch, opcao-3-contagem
site/                  Site do canal (usa overlays/shared/theme.css e brand/assets)
scenes/
  sources.json         Catálogo de INPUTS (globais no OBS): kind, settings, filtros
  base/ lives/ gravacao/   Uma cena por arquivo: itens, transform, enabled, locked, ordem
obs-config/profile/    Perfil de saída de referência (basic.ini parcial + encoders) — sem segredos
scripts/
  setup_machine.ps1    Máquina nova: venv, .env, plugin (versão fixa + SHA-256), perfil — idempotente
  setup_obs_profile.py Mescla obs-config/profile/ no perfil do OBS (OBS fechado; nunca toca service.json)
  obs_common.py        Conexão (.env), placeholders, normalização de transform
  test_connection.py   Valida conexão e lista cenas/fontes
  apply_scene.py       JSON → OBS (idempotente)
  export_snapshot.py   OBS → JSON limpo
assets/overlays, assets/audio   Mídias leves versionáveis (vídeos pesados são ignorados pelo Git)
```

### Formato das cenas
- `scene`: nome no OBS (`Base - …`, `Live - …`, `Gravação - …`).
- `items`: **primeiro = fundo**, último = topo. Cada item: `source`, `transform` (chaves nativas do OBS:
  `positionX/Y`, `scaleX/Y`, `alignment` 5 = topo-esquerda, `boundsType/Width/Height`, `cropToBounds`, `crop*`),
  `enabled`, `locked`, e opcionalmente `input` (override do catálogo).
- Inputs são **globais** no OBS: settings e filtros ficam em `scenes/sources.json`. A mesma fonte nunca pode ter
  definições diferentes entre cenas (`apply_scene.py` aborta se isso acontecer).
- Placeholders: `${PROJECT_ROOT}` (raiz do repo), `${VAR}` (do `.env`), `"@file:caminho"` (conteúdo do arquivo).
  Se uma variável faltar, a chave não é enviada e o item fica **desativado**.
- IDs de dispositivo/janela (webcam, mic, monitor) **não** vão para o Git — escolha-os uma vez no OBS.
- Overlays em "Arquivo local" **não recebem query string**; para variações crie um HTML que defina
  `window.RK_PARAMS = {...}` antes de `rodikil.js` (ver `starting-screen/*.html`).
- Encaixe câmera/moldura com escala `s` no `Overlay_CameraFrame` em `(fx, fy)`: `Webcam_Main` em
  `(fx + 40s, fy + 100s)`, bounds `640s × 360s`, `OBS_BOUNDS_SCALE_OUTER` + `cropToBounds`. Webcam fica abaixo da moldura.
  Chat com escala `s` em `(cx, cy)`: `Overlay_ChatFeed` em `(cx + 30s, cy + 72s)` com a mesma escala, acima da moldura.
- Fundo da webcam (modo atual = **desfoque + clima**): o filtro `background_removal` desfoca o quarto
  (`blur_background`) e o `Overlay_WebcamClima` fica **logo acima** da `Webcam_Main`, com o **mesmo transform**, pondo a
  identidade nas bordas. `Overlay_WebcamBg` (fundo trocado) segue abaixo da webcam, **desativado**: para voltar a ele,
  zere `blur_background` e ative o item. Plugin obs-backgroundremoval 1.4.1 em `C:/ProgramData/obs-studio/plugins` (instalado à mão).
  Filtro "Cor da Webcam" (color_filter_v2) corrige o tom esverdeado da webcam simples.
  Roda na CPU; a webcam fica em **1280x720** de propósito (em 1080p o filtro custava ~15 ms/quadro e derrubava frames
  com o Dota aberto; em 720p ~8 ms, 0 perdidos). DirectML foi mais lento na GTX 1060. Confira `GetStats` após mudanças.

## Regra de idempotência (obrigatória)
`apply_scene.py` deve poder rodar N vezes e produzir exatamente o estado de 1 execução:
- cena/input/item/filtro **existente → atualiza**; inexistente → cria. **Nunca duplica fonte.**
- Input com mesmo nome e `kind` diferente → erro, nada é alterado.
- Transform, enabled, locked e ordem são sempre reaplicados a partir do JSON.
- Itens fora do JSON só são removidos com `--prune` (o input continua existindo).
- Sempre testar com `--dry-run` antes, e confirmar que uma 2ª execução não mostra nenhum `+`.
Todo script novo que escreva no OBS deve seguir a mesma regra.

## Nomenclatura obrigatória de fontes no OBS
| Nome | Uso |
|---|---|
| `Game_Capture` | Captura de jogo do Dota 2 (`game_capture`, janela fixa em `dota2.exe`) |
| `Game_Capture_<Jogo>` | Captura própria de outro jogo, para cada cena pegar o seu jogo automaticamente (`Game_Capture_CS2` → `cs2.exe`) |
| `Display_Capture` | Captura de monitor |
| `Webcam_Main` | Webcam principal (`dshow_input`) |
| `Mic_Main` | Microfone principal |
| `Desktop_Audio` | Áudio do sistema |
| `Overlay_<Nome>` | Qualquer overlay/imagem/browser source, PascalCase (`Overlay_CameraFrame`, `Overlay_ChatFeed`, `Overlay_Logo`) |

Áudio:
- `Mic_Main` (microfone **Fifine**) é **fonte de cena**, presente **só** onde se fala: lives
  (`Live - *`), `Base - Resenha` e gravações. Iniciando, Intervalo e Encerrando ficam **sem** mic de propósito
  (o mic some do mixer nessas telas — é esperado). Cuidado no Modo Estúdio: a cena no ar é uma cópia feita na
  transição; mudanças só valem para ela na próxima transição. O ID do dispositivo vem de `MIC_DEVICE_ID` no `.env`
  (liste com `test_connection.py --devices`). O Áudio Global de microfone deve ficar **desativado** no OBS, senão duplica.
- `Desktop_Audio` continua como **Áudio Global** (toca em todas as cenas) e por isso não aparece nos JSONs.
- Cadeia de filtros do `Mic_Main`: Compressor → Filtro de ruídos (gate) → Supressão de ruídos → Ganho → VST (Accusonus ERA6)
  → Limitador. O Git gerencia só **Compressor** e **Limitador** (`scenes/sources.json`); os demais são ajustados no OBS.
  `apply_scene.py` nunca apaga filtros, só cria/atualiza os declarados.
- O OBS não permite pôr uma fonte de Áudio Global dentro de uma cena (CreateSceneItem retorna 700).

## Configuração de saída (perfil OBS "Sem nome")
1920x1080 base e saída, 60 FPS, 48 kHz estéreo · Saída Avançada, NVENC H.264 (GTX 1060) · CBR 9000 Kbps, keyframe 2 s,
preset p5, tune HQ, multipass qres, profile high, 2 B-frames · áudio AAC 160 Kbps · serviço YouTube RTMPS.
Os parâmetros do encoder ficam em `%APPDATA%/obs-studio/basic/profiles/Sem nome/streamEncoder.json` (o WebSocket não
os altera); edite com o OBS fechado ou reinicie o OBS depois.

## Identidade visual Rodikil — resumo dos tokens
Fonte completa: `brand/brand-tokens.json` (espelhado em `overlays/shared/theme.css`; altere os dois juntos).

| Token | Valor | Uso |
|---|---|---|
| Vermelho Rodikil | `#FA2B28` | Só destaque: elipse, palavra-chave do título, pílulas, borda da câmera |
| Preto Glitter | `#0A0A0B` | Fundo (com textura de estrelas), painéis, "R" do logo |
| Osso | `#F4F1EA` | Texto principal, wordmark, brilhos |
| Poeira | `#8C8C92` | Texto secundário/mono, legendas, handles |
| Painel | `rgba(10,10,11,.92)` / vidro `.72` | Faixas, alertas / painel do chat |
| Borda / divisória | `#2C2C2C` / `#363535` | Contornos sutis |

Tipografia: **Rammetto One** (só o logo) · **Barlow Condensed** 700–800 em CAIXA ALTA (títulos/rótulos) ·
**Space Mono** em CAIXA ALTA com tracking largo e separador `//` (detalhes, kicker, handles).
Elementos: elipse vermelha vertical · órbita (contorno vermelho fino inclinado ~-8°) · brilho de 4 pontas Osso · textura estrelada.
Forma: raios 8/20/28px e pílula 999px; moldura de câmera = 2px vermelho + 8–10px preto.

**Regras:** o "R" é sempre preto dentro da elipse vermelha · não distorcer, girar ou recolorir o logo ·
vermelho só como destaque, nunca fundo inteiro · títulos com uma palavra-chave em vermelho.

## Comandos
```bash
python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt
cp .env.example .env            # preencher OBS_PASSWORD (Ferramentas > Configurações do servidor WebSocket)
.venv/Scripts/python scripts/test_connection.py
.venv/Scripts/python scripts/apply_scene.py scenes/lives/dota.json --dry-run
.venv/Scripts/python scripts/apply_scene.py scenes/lives/dota.json
.venv/Scripts/python scripts/apply_scene.py --all
.venv/Scripts/python scripts/export_snapshot.py "Live - Dota 2" -o scenes/lives/dota.json
```
No terminal do Windows, use `PYTHONIOENCODING=utf-8` se os acentos saírem quebrados.
