"""Assistente da live Rodikil — roda em segundo plano (pythonw) e cuida de duas coisas sozinho:

1. CHAT SEMPRE PRONTO: a cada minuto consulta a página pública https://www.youtube.com/<canal>/live.
   Se houver live no ar (ou agendada), aponta o Overlay_ChatFeed para ela e atualiza YOUTUBE_CHAT_URL no .env.
   Só mexe no endereço do chat — nunca troca cena nem nada que esteja no ar.
2. CLIPES PARA SHORTS: quando o Replay Buffer salva um clipe (atalho Ctrl+Alt+C ou botão CLIPE do Painel),
   move o arquivo para "<pasta de gravação>/Clipes Rodikil/" com data e cena no nome e, se houver ffmpeg
   (PATH ou FFMPEG no .env), gera a versão VERTICAL 1080x1920: webcam em cima, jogo (centro) embaixo.

Uso:
  .venv\\Scripts\\python scripts\\assistente_live.py            # com janela (log na tela)
  .venv\\Scripts\\pythonw scripts\\assistente_live.py           # sem janela (é o que a inicialização do Windows usa)
  .venv\\Scripts\\python scripts\\assistente_live.py --uma-vez  # só confere o chat uma vez e sai
Log: logs/assistente.log. Variáveis opcionais no .env: YOUTUBE_CANAL (padrão @RODIKIL), FFMPEG (caminho do ffmpeg.exe).
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obs_common as oc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
LOG_DIR = ROOT / "logs"
CHAT_SOURCE = "Overlay_ChatFeed"
WEBCAM = "Webcam_Main"
CHECK_CHAT_EVERY = 60  # s
LOCK_PORT = 48787      # impede duas cópias rodando ao mesmo tempo

log = logging.getLogger("assistente")


# ----------------------------------------------------------------------------- utilidades
def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s  %(message)s", "%d/%m %H:%M:%S")
    fh = logging.FileHandler(LOG_DIR / "assistente.log", encoding="utf-8")
    fh.setFormatter(fmt)
    log.addHandler(fh)
    if sys.stdout and sys.stdout.isatty():
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        log.addHandler(sh)
    log.setLevel(logging.INFO)


def single_instance() -> socket.socket | None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", LOCK_PORT))
        s.listen(1)
        return s
    except OSError:
        return None


def set_env_line(key: str, value: str) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    out, done = [], False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        out.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(out) + "\n", encoding="utf-8")
    os.environ[key] = value


# ----------------------------------------------------------------------------- chat
def current_live_video(channel: str) -> str | None:
    """ID do vídeo da live no ar (ou agendada) do canal, pela página pública /live. None se não houver."""
    req = urllib.request.Request(f"https://www.youtube.com/{channel}/live",
                                 headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "pt-BR"})
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8", "ignore")
    m = re.search(r'<link rel="canonical" href="https://www\.youtube\.com/watch\?v=([\w-]{11})"', html)
    if not m:
        return None
    if '"isLiveNow":true' in html or '"isUpcoming":true' in html or '"isLive":true' in html:
        return m.group(1)
    return None


def check_chat(cl, channel: str) -> None:
    try:
        vid = current_live_video(channel)
    except Exception as exc:  # rede fora, YouTube mudou etc.
        log.info(f"chat: não consegui consultar o YouTube ({exc})")
        return
    if not vid:
        return
    want = f"https://www.youtube.com/live_chat?is_popout=1&v={vid}"
    try:
        current = cl.get_input_settings(CHAT_SOURCE).input_settings.get("url", "")
    except Exception:
        return  # fonte do chat não existe nesta coleção
    if current != want:
        cl.set_input_settings(CHAT_SOURCE, {"url": want}, True)
        set_env_line("YOUTUBE_CHAT_URL", want)
        log.info(f"chat: apontado para a live {vid}")


# ----------------------------------------------------------------------------- clipes
def ffmpeg_path() -> str | None:
    """FFMPEG do .env > PATH > onde o winget instala (funciona mesmo sem reiniciar o assistente)."""
    p = os.getenv("FFMPEG", "").strip()
    if p and Path(p).exists():
        return p
    found = shutil.which("ffmpeg")
    if found:
        return found
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    link = local / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"
    if link.exists():
        return str(link)
    for exe in (local / "Microsoft" / "WinGet" / "Packages").glob("Gyan.FFmpeg*/*/bin/ffmpeg.exe"):
        return str(exe)
    return None


def webcam_rect(cl, scene: str) -> tuple[int, int, int, int] | None:
    """Retângulo (x, y, w, h) da Webcam_Main no canvas da cena, se estiver visível."""
    try:
        for it in cl.get_scene_item_list(scene).scene_items:
            if it["sourceName"] == WEBCAM and it.get("sceneItemEnabled"):
                t = it["sceneItemTransform"]
                w = t.get("boundsWidth") or t.get("width")
                h = t.get("boundsHeight") or t.get("height")
                return int(t["positionX"]), int(t["positionY"]), int(w), int(h)
    except Exception:
        pass
    return None


def scene_has_game(cl, scene: str) -> bool:
    try:
        return any(it["sourceName"].startswith("Game_Capture") and it.get("sceneItemEnabled")
                   for it in cl.get_scene_item_list(scene).scene_items)
    except Exception:
        return True


def make_vertical(ff: str, src: Path, dst: Path, cam: tuple[int, int, int, int] | None, canvas: tuple[int, int],
                  game: bool = True) -> bool:
    """Jogo: webcam em cima (1080x608) + centro do jogo embaixo (1080x1312). Sem jogo: um corte 9:16 centrado na webcam."""
    cw, ch = canvas
    if cam and not game:
        x, y, w, h = cam
        gw = int(ch * 9 / 16) // 2 * 2
        gx = min(max(0, x + w // 2 - gw // 2), cw - gw)
        graph = f"[0:v]crop={gw}:{ch}:{gx}:0,scale=1080:1920:flags=lanczos,setsar=1,format=yuv420p[v]"
    elif cam:
        x, y, w, h = cam
        x, y = max(0, x), max(0, y)
        w, h = min(w, cw - x), min(h, ch - y)
        gw = int(ch * 1080 / 1312) // 2 * 2
        gx = (cw - gw) // 2
        graph = (f"[0:v]split=2[a][b];"
                 f"[a]crop={w}:{h}:{x}:{y},scale=1080:608:flags=lanczos,setsar=1[cam];"
                 f"[b]crop={gw}:{ch}:{gx}:0,scale=1080:1312:flags=lanczos,setsar=1[game];"
                 f"[cam][game]vstack=inputs=2,format=yuv420p[v]")
    else:
        gw = int(ch * 9 / 16) // 2 * 2
        graph = f"[0:v]crop={gw}:{ch}:{(cw - gw) // 2}:0,scale=1080:1920:flags=lanczos,setsar=1,format=yuv420p[v]"
    base = [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", str(src), "-filter_complex", graph,
            "-map", "[v]", "-map", "0:a?", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart"]
    for venc in (["-c:v", "h264_nvenc", "-preset", "p5", "-b:v", "12M"], ["-c:v", "libx264", "-preset", "medium", "-crf", "20"]):
        r = subprocess.run(base + venc + [str(dst)], capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode == 0:
            return True
        log.info(f"clipe: ffmpeg falhou com {venc[1]} ({r.stderr.strip()[:200]})")
    return False


def on_clip_saved(path: str, req) -> None:
    src = Path(path)
    if not src.exists():
        log.info(f"clipe: arquivo não encontrado {src}")
        return
    try:
        scene = req.get_scene_list().current_program_scene_name
        video = req.get_video_settings()
        canvas = (int(video.base_width), int(video.base_height))
        cam = webcam_rect(req, scene)
        game = scene_has_game(req, scene)
    except Exception:
        scene, canvas, cam, game = "Live", (1920, 1080), None, True
    folder = src.parent / "Clipes Rodikil"
    folder.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    safe_scene = re.sub(r'[\\/:*?"<>|]', "", scene)
    dst = folder / f"{stamp} - {safe_scene}{src.suffix}"
    for _ in range(20):  # o OBS pode ainda estar fechando o arquivo
        try:
            shutil.move(str(src), str(dst))
            break
        except PermissionError:
            time.sleep(0.5)
    log.info(f"clipe: salvo {dst.name}")
    ff = ffmpeg_path()
    if not ff:
        log.info("clipe: sem ffmpeg — versão vertical não gerada (instale o ffmpeg ou defina FFMPEG no .env)")
        return
    vertical = folder / f"{stamp} - {safe_scene} - SHORTS.mp4"
    if make_vertical(ff, dst, vertical, cam, canvas, game):
        log.info(f"clipe: vertical pronto {vertical.name}")


# ----------------------------------------------------------------------------- laço principal
def run(once: bool) -> None:
    import obsws_python as obsws
    from dotenv import load_dotenv

    load_dotenv(ENV_FILE)
    channel = os.getenv("YOUTUBE_CANAL", "@RODIKIL").strip() or "@RODIKIL"
    req = events = None
    last_chat = 0.0
    while True:
        try:
            if req is None:
                req = oc.connect()
                events = obsws.EventClient(host=os.getenv("OBS_HOST", "localhost"), port=int(os.getenv("OBS_PORT", "4455")),
                                           password=os.getenv("OBS_PASSWORD", ""))

                def on_replay_buffer_saved(data):
                    on_clip_saved(data.saved_replay_path, req)

                events.callback.register(on_replay_buffer_saved)
                log.info("conectado ao OBS")
            req.get_version()  # ainda conectado?
            if time.time() - last_chat >= CHECK_CHAT_EVERY:
                check_chat(req, channel)
                last_chat = time.time()
            if once:
                return
        except Exception as exc:
            if req is not None:
                log.info(f"OBS desconectado ({type(exc).__name__}) — tentando de novo")
            for c in (events, req):
                try:
                    c and c.disconnect()
                except Exception:
                    pass
            req = events = None
            if once:
                return
        time.sleep(10)


def main() -> None:
    ap = argparse.ArgumentParser(description="Assistente da live Rodikil (chat sempre pronto + clipes para Shorts).")
    ap.add_argument("--uma-vez", action="store_true", help="Confere o chat uma vez e sai")
    ap.add_argument("--vertical", type=Path, help="Gera a versão vertical de um clipe já salvo e sai")
    args = ap.parse_args()
    setup_logging()
    logging.getLogger("obsws_python").setLevel(logging.CRITICAL)
    if args.vertical:
        ff = ffmpeg_path()
        if not ff:
            sys.exit("ffmpeg não encontrado — instale com: winget install Gyan.FFmpeg")
        src = args.vertical
        m = re.search(r" - (.+?)$", src.stem)  # "2026-11-23 19-28-24 - Base - Resenha" -> cena
        scene = m.group(1) if m else ""
        cam, canvas, game = None, (1920, 1080), True
        try:
            cl = oc.connect()
            v = cl.get_video_settings()
            canvas = (int(v.base_width), int(v.base_height))
            cam = webcam_rect(cl, scene) if scene else None
            game = scene_has_game(cl, scene) if scene else True
        except Exception:
            pass
        dst = src.with_name(f"{src.stem} - SHORTS.mp4")
        ok = make_vertical(ff, src, dst, cam, canvas, game)
        print(("OK: " if ok else "FALHOU: ") + str(dst))
        return
    lock = single_instance()
    if lock is None and not args.uma_vez:
        print("O assistente já está rodando.")
        return
    log.info("assistente iniciado")
    run(args.uma_vez)


if __name__ == "__main__":
    main()
