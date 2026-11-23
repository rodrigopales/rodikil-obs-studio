/* RODIKIL // efeitos sonoros sintetizados (Web Audio) — sem arquivos, sem direitos autorais.
   Todas as funções recebem `t` = tempo absoluto do AudioContext em que o som começa. */
(function () {
  "use strict";

  function mulberry32(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function create() {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const rnd = mulberry32(42);

    // Saída: master -> compressor (cola e evita clipar) -> alto-falante
    const master = ctx.createGain();
    master.gain.value = 0.85;
    const comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -12; comp.knee.value = 6; comp.ratio.value = 6;
    comp.attack.value = 0.003; comp.release.value = 0.25;
    master.connect(comp); comp.connect(ctx.destination);

    // Reverb (impulso gerado)
    function impulse(sec, decay) {
      const len = Math.floor(ctx.sampleRate * sec);
      const b = ctx.createBuffer(2, len, ctx.sampleRate);
      for (let c = 0; c < 2; c++) {
        const d = b.getChannelData(c);
        for (let i = 0; i < len; i++) d[i] = (rnd() * 2 - 1) * Math.pow(1 - i / len, decay);
      }
      return b;
    }
    const verb = ctx.createConvolver();
    verb.buffer = impulse(3, 2.6);
    verb.connect(master);

    const noiseBuf = (function () {
      const b = ctx.createBuffer(1, ctx.sampleRate * 3, ctx.sampleRate);
      const d = b.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = rnd() * 2 - 1;
      return b;
    })();

    function out(node, wet, pan) {
      let last = node;
      if (pan !== undefined) {
        const p = ctx.createStereoPanner(); p.pan.value = pan;
        node.connect(p); last = p;
      }
      last.connect(master);
      if (wet) { const s = ctx.createGain(); s.gain.value = wet; last.connect(s); s.connect(verb); }
      return last;
    }
    function gainEnv(t, attack, peak, decay) {
      const g = ctx.createGain();
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(peak, t + attack);
      g.gain.exponentialRampToValueAtTime(0.0001, t + attack + decay);
      return g;
    }
    function noise(t, dur) {
      const s = ctx.createBufferSource();
      s.buffer = noiseBuf; s.loop = true;
      s.start(t, rnd() * 2); s.stop(t + dur + 0.05);
      return s;
    }
    function osc(type, freq, t, dur) {
      const o = ctx.createOscillator();
      o.type = type; o.frequency.setValueAtTime(freq, t);
      o.start(t); o.stop(t + dur + 0.05);
      return o;
    }

    const api = {
      ctx: ctx,

      /** Passagem de ar (ruído com filtro varrendo). f0 -> f1 em Hz; panL -> panR. */
      whoosh(t, dur, f0, f1, peak, wet, panFrom, panTo) {
        dur = dur || 0.8; f0 = f0 || 300; f1 = f1 || 3500; peak = peak || 0.5;
        const n = noise(t, dur);
        const bp = ctx.createBiquadFilter();
        bp.type = "bandpass"; bp.Q.value = 1.4;
        bp.frequency.setValueAtTime(f0, t);
        bp.frequency.exponentialRampToValueAtTime(f1, t + dur);
        const g = ctx.createGain();
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(peak, t + dur * 0.65);
        g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
        const p = ctx.createStereoPanner();
        p.pan.setValueAtTime(panFrom === undefined ? -0.7 : panFrom, t);
        p.pan.linearRampToValueAtTime(panTo === undefined ? 0.7 : panTo, t + dur);
        n.connect(bp); bp.connect(g); g.connect(p);
        out(p, wet === undefined ? 0.25 : wet);
      },

      /** Subida de tensão (serra + ruído agudo crescendo) que termina em `t + dur`. */
      riser(t, dur, peak) {
        peak = peak || 0.22;
        const lp = ctx.createBiquadFilter();
        lp.type = "lowpass"; lp.Q.value = 6;
        lp.frequency.setValueAtTime(250, t);
        lp.frequency.exponentialRampToValueAtTime(7000, t + dur);
        const g = ctx.createGain();
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(peak, t + dur);
        g.gain.setValueAtTime(0.0001, t + dur + 0.02);
        [1, 1.006, 0.5].forEach(function (m) {
          const o = osc("sawtooth", 110 * m, t, dur);
          o.frequency.exponentialRampToValueAtTime(880 * m, t + dur);
          o.connect(lp);
        });
        const n = noise(t, dur);
        const hp = ctx.createBiquadFilter();
        hp.type = "highpass";
        hp.frequency.setValueAtTime(1500, t);
        hp.frequency.exponentialRampToValueAtTime(9000, t + dur);
        n.connect(hp); hp.connect(lp);
        lp.connect(g);
        out(g, 0.3);
      },

      /** Impacto cinematográfico: sub grave descendo + soco de ruído + cauda de reverb. */
      impact(t, peak) {
        peak = peak || 1;
        const sub = osc("sine", 140, t, 1.6);
        sub.frequency.exponentialRampToValueAtTime(34, t + 0.7);
        const gs = gainEnv(t, 0.004, peak, 1.5);
        sub.connect(gs); out(gs, 0.15);

        const n = noise(t, 0.6);
        const lp = ctx.createBiquadFilter();
        lp.type = "lowpass";
        lp.frequency.setValueAtTime(5000, t);
        lp.frequency.exponentialRampToValueAtTime(300, t + 0.4);
        const gn = gainEnv(t, 0.002, peak * 0.7, 0.45);
        n.connect(lp); lp.connect(gn); out(gn, 0.8);
      },

      /** Bumbo curto (batida). */
      kick(t, peak) {
        peak = peak || 0.9;
        const o = osc("sine", 170, t, 0.5);
        o.frequency.exponentialRampToValueAtTime(42, t + 0.14);
        const g = gainEnv(t, 0.002, peak, 0.42);
        o.connect(g); out(g, 0.1);
        const c = osc("square", 2400, t, 0.02);
        const gc = gainEnv(t, 0.001, peak * 0.12, 0.018);
        c.connect(gc); out(gc);
      },

      /** Brilho: sinos agudos em cascata (combina com a estrela de 4 pontas). */
      shimmer(t, peak, notes) {
        peak = peak || 0.12;
        notes = notes || [1568, 2093, 2637, 3136, 3951];
        notes.forEach(function (f, i) {
          const tt = t + i * 0.055;
          const pan = i % 2 ? 0.5 : -0.5;
          const a = osc("sine", f, tt, 1.6);
          const b = osc("triangle", f * 2, tt, 0.6);
          const ga = gainEnv(tt, 0.006, peak, 1.5);
          const gb = gainEnv(tt, 0.004, peak * 0.25, 0.5);
          a.connect(ga); b.connect(gb);
          out(ga, 0.6, pan); out(gb, 0.6, pan);
        });
      },

      /** Bipe digital curto. */
      blip(t, freq, peak, dur, type) {
        dur = dur || 0.05;
        const o = osc(type || "square", freq || 1200, t, dur);
        const lp = ctx.createBiquadFilter();
        lp.type = "lowpass"; lp.frequency.value = 5000;
        const g = gainEnv(t, 0.002, peak || 0.06, dur);
        o.connect(lp); lp.connect(g); out(g, 0.15);
      },

      /** Glitch digital: picotes aleatórios (determinísticos) de bipes e ruído. */
      glitch(t, dur, peak) {
        peak = peak || 0.18;
        let tt = t;
        while (tt < t + dur) {
          const len = 0.015 + rnd() * 0.05;
          if (rnd() > 0.45) {
            const o = osc("square", 120 + rnd() * 2800, tt, len);
            const g = gainEnv(tt, 0.001, peak * (0.4 + rnd() * 0.6), len);
            o.connect(g); out(g, 0.05, rnd() * 2 - 1);
          } else {
            const n = noise(tt, len);
            const bp = ctx.createBiquadFilter();
            bp.type = "bandpass"; bp.Q.value = 3; bp.frequency.value = 400 + rnd() * 6000;
            const g = gainEnv(tt, 0.001, peak * 1.6, len);
            n.connect(bp); bp.connect(g); out(g, 0.05, rnd() * 2 - 1);
          }
          tt += len + rnd() * 0.035;
        }
      },

      /** Tique de contagem: clique agudo + batida grave. */
      tick(t, peak) {
        peak = peak || 0.8;
        const o = osc("sine", 1760, t, 0.08);
        const g = gainEnv(t, 0.001, peak * 0.22, 0.07);
        o.connect(g); out(g, 0.3);
        api.kick(t, peak);
      },

      /** Fanfarra de vitória: arpejo maior subindo + acorde final. */
      fanfare(t, peak) {
        peak = peak || 0.16;
        [523.25, 659.25, 783.99, 1046.5].forEach(function (f, i) {
          const tt = t + i * 0.09;
          ["sawtooth", "square"].forEach(function (type, k) {
            const o = osc(type, f * (k ? 0.5 : 1), tt, 0.5);
            const lp = ctx.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 3200;
            const g = gainEnv(tt, 0.01, peak * (k ? 0.5 : 1), i === 3 ? 1.1 : 0.3);
            o.connect(lp); lp.connect(g); out(g, 0.35, k ? -0.3 : 0.3);
          });
        });
      },

      /** Buzina de estádio: três toques de serra grave (BWAAA BWA BWAAA). */
      horn(t, peak) {
        peak = peak || 0.22;
        [[0, 0.42], [0.5, 0.16], [0.72, 0.6]].forEach(function (p) {
          const tt = t + p[0], d = p[1];
          [466.16, 587.33, 698.46].forEach(function (f) {
            const o = osc("sawtooth", f, tt, d);
            o.frequency.setValueAtTime(f * 0.97, tt);
            o.frequency.linearRampToValueAtTime(f, tt + 0.05);
            const lp = ctx.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 2600; lp.Q.value = 2;
            const g = ctx.createGain();
            g.gain.setValueAtTime(0.0001, tt);
            g.gain.exponentialRampToValueAtTime(peak, tt + 0.02);
            g.gain.setValueAtTime(peak, tt + d - 0.04);
            g.gain.exponentialRampToValueAtTime(0.0001, tt + d);
            o.connect(lp); lp.connect(g); out(g, 0.25);
          });
        });
      },

      /** Trombone triste (wah wah wah waaah) — para o "F". */
      trombone(t, peak) {
        peak = peak || 0.2;
        [[392, 0.42], [369.99, 0.42], [349.23, 0.42], [329.63, 1.3]].forEach(function (n, i) {
          const tt = t + i * 0.48, d = n[1];
          const o = osc("sawtooth", n[0], tt, d);
          if (i === 3) {
            const lfo = osc("sine", 6, tt, d), lg = ctx.createGain();
            lg.gain.value = 9; lfo.connect(lg); lg.connect(o.frequency);
          }
          const lp = ctx.createBiquadFilter(); lp.type = "lowpass"; lp.Q.value = 5;
          lp.frequency.setValueAtTime(400, tt);
          lp.frequency.linearRampToValueAtTime(1500, tt + d * 0.3);
          lp.frequency.linearRampToValueAtTime(500, tt + d);
          const g = gainEnv(tt, 0.04, peak, d);
          o.connect(lp); lp.connect(g); out(g, 0.3);
        });
      },

      /** Boing de desenho animado (mola). */
      boing(t, peak) {
        peak = peak || 0.3;
        const o = osc("sine", 180, t, 0.9);
        o.frequency.exponentialRampToValueAtTime(520, t + 0.12);
        o.frequency.exponentialRampToValueAtTime(220, t + 0.9);
        const lfo = osc("sine", 18, t, 0.9), lg = ctx.createGain();
        lg.gain.setValueAtTime(60, t); lg.gain.exponentialRampToValueAtTime(1, t + 0.9);
        lfo.connect(lg); lg.connect(o.frequency);
        const g = gainEnv(t, 0.005, peak, 0.85);
        o.connect(g); out(g, 0.2);
      },

      /** Zumbido distorcido de raiva (tilt). */
      buzz(t, dur, peak) {
        dur = dur || 0.8; peak = peak || 0.16;
        const o = osc("sawtooth", 55, t, dur), o2 = osc("square", 58, t, dur);
        const ws = ctx.createWaveShaper(), curve = new Float32Array(256);
        for (let i = 0; i < 256; i++) { const x = i / 128 - 1; curve[i] = Math.tanh(x * 6); }
        ws.curve = curve;
        const g = ctx.createGain();
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(peak, t + 0.03);
        g.gain.setValueAtTime(peak, t + dur - 0.1);
        g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
        o.connect(ws); o2.connect(ws); ws.connect(g); out(g, 0.1);
      },

      /** Cama grave (pad) para dar clima; some sozinha no fim. */
      drone(t, dur, freq, peak) {
        freq = freq || 55; peak = peak || 0.12;
        const lp = ctx.createBiquadFilter();
        lp.type = "lowpass"; lp.frequency.setValueAtTime(200, t);
        lp.frequency.linearRampToValueAtTime(900, t + dur * 0.7);
        const g = ctx.createGain();
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(peak, t + dur * 0.35);
        g.gain.setValueAtTime(peak, t + dur * 0.7);
        g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
        [1, 1.5, 2.003].forEach(function (m) {
          const o = osc("sawtooth", freq * m, t, dur);
          o.connect(lp);
        });
        lp.connect(g); out(g, 0.5);
      }
    };
    return api;
  }

  window.RKSfx = { create: create };
})();
