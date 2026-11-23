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
   - *Configurações › Áudio* → Áudio do desktop = *Padrão*; **microfone do Áudio Global desativado** (o `Mic_Main` já está nas cenas).
   - Opcional: renomeie o "Áudio do desktop" para `Desktop_Audio`.

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
