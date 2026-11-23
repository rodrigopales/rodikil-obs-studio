--[[
  Rodikil — Intro e atalhos
  * "Rodikil: abrir live": coloca "Base - Intro" no ar e, quando termina, vai sozinho para a próxima cena (Resenha).
  * "Rodikil: ir para <cena>": leva a cena DIRETO para o ar (com ou sem Modo Estúdio).
  * "Rodikil: microfone liga/desliga": alterna o mudo do Mic_Main.
  Atalhos globais: funcionam com o jogo em foco.

  Instalar: OBS › Ferramentas › Scripts › "+" › este arquivo.
  Teclas:   definidas por scripts/setup_obs_hotkeys.py (obs-config/hotkeys.json) ou em Configurações › Teclas de atalho.
]]

obs = obslua

local INTRO = "Base - Intro"
local MIC = "Mic_Main"
local next_scene = "Base - Resenha"
local duration_ms = 7200
local busy = false

-- id do atalho (gravado nas configurações do script) -> cena
local SCENES = {
  { id = "rodikil_cena_1", scene = "Base - Iniciando" },
  { id = "rodikil_cena_2", scene = "Base - Resenha" },
  { id = "rodikil_cena_3", scene = "Live - Dota 2" },
  { id = "rodikil_cena_4", scene = "Live - CS2" },
  { id = "rodikil_cena_5", scene = "Base - Intervalo" },
  { id = "rodikil_cena_6", scene = "Base - Encerrando" },
}
-- reações do Overlay_Reacoes (overlays/reacoes/index.html)
local REACOES_SRC = "Overlay_Reacoes"
local REACOES = {
  { id = "rodikil_reacao_gg",     tipo = "gg",     label = "GG" },
  { id = "rodikil_reacao_clutch", tipo = "clutch", label = "CLUTCH" },
  { id = "rodikil_reacao_f",      tipo = "f",      label = "F no chat" },
  { id = "rodikil_reacao_pateta", tipo = "pateta", label = "Pateta da partida" },
  { id = "rodikil_reacao_hype",   tipo = "hype",   label = "Agora vai (hype)" },
  { id = "rodikil_reacao_tilt",   tipo = "tilt",   label = "Tiltou" },
}
local hotkeys = {} -- id -> hotkey_id

-- Envia um evento JavaScript para um Browser Source (obs-browser: proc "javascript_event")
local function js_event(source_name, event_name, json)
  local src = obs.obs_get_source_by_name(source_name)
  if src == nil then
    obs.script_log(obs.LOG_WARNING, "Fonte não encontrada: " .. source_name)
    return
  end
  local ph = obs.obs_source_get_proc_handler(src)
  local cd = obs.calldata_create()
  obs.calldata_set_string(cd, "eventName", event_name)
  obs.calldata_set_string(cd, "jsonString", json)
  obs.proc_handler_call(ph, "javascript_event", cd)
  obs.calldata_destroy(cd)
  obs.obs_source_release(src)
end

local function reacao(tipo)
  js_event(REACOES_SRC, "rodikil-reacao", '{"tipo":"' .. tipo .. '"}')
end

local function go(name)
  local src = obs.obs_get_source_by_name(name)
  if src == nil then
    obs.script_log(obs.LOG_WARNING, "Cena não encontrada: " .. name)
    return false
  end
  if obs.obs_frontend_preview_program_mode_active() then
    obs.obs_frontend_set_current_preview_scene(src)
    obs.obs_frontend_preview_program_trigger_transition()
  else
    obs.obs_frontend_set_current_scene(src)
  end
  obs.obs_source_release(src)
  return true
end

local function after_intro()
  obs.remove_current_callback()
  busy = false
  go(next_scene)
end

local function cancel_intro()
  if busy then
    obs.timer_remove(after_intro)
    busy = false
  end
end

local function play_intro()
  if busy then return end
  if go(INTRO) then
    busy = true
    obs.timer_add(after_intro, duration_ms)
  end
end

local function toggle_mic()
  local src = obs.obs_get_source_by_name(MIC)
  if src == nil then
    obs.script_log(obs.LOG_WARNING, "Fonte não encontrada: " .. MIC)
    return
  end
  obs.obs_source_set_muted(src, not obs.obs_source_muted(src))
  obs.obs_source_release(src)
end

local function register(settings, id, label, action)
  local hk = obs.obs_hotkey_register_frontend(id, label, function(pressed)
    if pressed then action() end
  end)
  local saved = obs.obs_data_get_array(settings, id)
  obs.obs_hotkey_load(hk, saved)
  obs.obs_data_array_release(saved)
  hotkeys[id] = hk
end

function script_description()
  return "<b>Rodikil — Intro e atalhos</b><br>Abrir live (intro → próxima cena), ir para cada cena direto no ar " ..
         "e liga/desliga do microfone. Funciona com o Modo Estúdio e com o jogo em foco.<br>" ..
         "Teclas em Configurações › Teclas de atalho (busque <i>Rodikil</i>)."
end

function script_properties()
  local p = obs.obs_properties_create()
  local list = obs.obs_properties_add_list(p, "next_scene", "Depois da intro, ir para",
    obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
  local scenes = obs.obs_frontend_get_scene_names()
  if scenes ~= nil then
    for _, name in ipairs(scenes) do
      if name ~= INTRO then obs.obs_property_list_add_string(list, name, name) end
    end
  end
  obs.obs_properties_add_int(p, "duration_ms", "Duração da intro (ms)", 1000, 30000, 100)
  obs.obs_properties_add_button(p, "play", "Tocar intro agora", function() play_intro(); return false end)
  return p
end

function script_defaults(settings)
  obs.obs_data_set_default_string(settings, "next_scene", "Base - Resenha")
  obs.obs_data_set_default_int(settings, "duration_ms", 7200)
end

function script_update(settings)
  next_scene = obs.obs_data_get_string(settings, "next_scene")
  duration_ms = obs.obs_data_get_int(settings, "duration_ms")
end

function script_load(settings)
  register(settings, "rodikil_abrir_live", "Rodikil: abrir live (intro → próxima cena)", play_intro)
  for _, s in ipairs(SCENES) do
    local scene = s.scene
    register(settings, s.id, "Rodikil: ir para " .. scene, function() cancel_intro(); go(scene) end)
  end
  register(settings, "rodikil_mic", "Rodikil: microfone liga/desliga", toggle_mic)
  for _, r in ipairs(REACOES) do
    local tipo = r.tipo
    register(settings, r.id, "Rodikil: reação " .. r.label, function() reacao(tipo) end)
  end
end

function script_save(settings)
  for id, hk in pairs(hotkeys) do
    local saved = obs.obs_hotkey_save(hk)
    obs.obs_data_set_array(settings, id, saved)
    obs.obs_data_array_release(saved)
  end
end
