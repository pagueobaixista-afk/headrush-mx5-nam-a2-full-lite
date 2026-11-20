"""v8: NAM A2 Pro no 8-Bit Crush (classe BitDist). Aplica depois de v8_nucleos.py.
Lê os botões do objeto BitDist (offsets medidos no MX5, ver PLANO_v8.md) e acrescenta gate, EQ e blend.
uso: python3 v8_pro.py <build>/patch/nam_hook.cpp <v8_resampling_tab.json>"""
import sys, json
p, tabf = sys.argv[1], sys.argv[2]
s = open(p).read()
tab = json.load(open(tabf))


def troca(velho, novo, n=1):
    global s
    c = s.count(velho)
    if c != n:
        sys.exit('trecho %dx (esperado %d): %r' % (c, n, velho[:90]))
    s = s.replace(velho, novo)


helpers = r'''
// ---- [mx5-v8] NAM A2 Pro: botoes do 8-Bit Crush (objeto BitDist) ----
namespace pro
{
inline float f(void* o, int off) { return *reinterpret_cast<float*>(reinterpret_cast<uint8_t*>(o) + off); }
// Resample guarda Hz (292..20000, nao linear); a tabela converte de volta para a posicao 0..1 do botao
const float kResTab[101] = {%s};
inline float resample_norm(void* o)
{
  // [mx5-v8] 1 clique do botao = 0,001 = 1 modelo; acima do ultimo modelo fica no ultimo
  const int n = std::min(static_cast<int>(g_cached_models.size()), 101);
  const int idx = std::clamp(static_cast<int>(std::lround(f(o, 0x588) * 1000.f)), 0, std::max(n - 1, 0));
  return idx / 100.f; // knob_value_to_index usa 101 passos: idx/100 -> idx
  const float hz = f(o, 0x39c);
  if (hz <= kResTab[0]) return 0.f;
  for (int k = 1; k < 101; ++k)
    if (hz <= kResTab[k])
      return (k - 1 + (hz - kResTab[k - 1]) / std::max(kResTab[k] - kResTab[k - 1], 1e-3f)) / 100.f;
  return 1.f;
}
// INPUT (Drive guarda ganho linear 0..+12 dB): 50%% = 0 dB, faixa -12..+12 dB  ->  g^2 * 10^(-12/20)
inline float in_gain(void* o) { const float g = f(o, 0x524); return g * g * 0.25118864f; }
// OUTPUT (FX Out guarda ganho linear -24..0 dB): 50%% = 0 dB, faixa -12..+12 dB  ->  g * 10^(12/20)
inline float out_gain(void* o) { return f(o, 0x538) * 3.9810717f; }
inline float blend(void* o) { return std::clamp(f(o, 0x54c), 0.f, 1.f); }
// LITE / FULL / AUTO no Bit Mode: o MX5 guarda o padrao de bits do modo (+0x5d8, 24 bytes), nao o indice
inline int mode(void* o)
{
  // bytes do padrao do Bit Mode que o setter escreve (medidos com o desvio ativo):
  // A: +0x5dd=2 +0x5e6=2 | B: +0x5d7=3 +0x5e0=2 +0x5e3=2 +0x5e6=2 | Off/Cust: zeros
  const uint8_t* m = reinterpret_cast<uint8_t*>(o);
  if (m[0x5d7] == 3 && m[0x5e0] == 2 && m[0x5e3] == 2 && m[0x5e6] == 2) return 1; // B = FULL
  if (m[0x5dd] == 2 && m[0x5e6] == 2 && m[0x5d7] == 0 && m[0x5e0] == 0 && m[0x5e3] == 0) return 0; // A = LITE
  return 2; // resto = AUTO
}
struct Biquad
{
  float b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0, z1[2] = {0, 0}, z2[2] = {0, 0};
  inline float run(int ch, float x)
  {
    const float y = b0 * x + z1[ch];
    z1[ch] = b1 * x - a1 * y + z2[ch];
    z2[ch] = b2 * x - a2 * y;
    return y;
  }
  void set(int type, float fc, float q, float db) // 0 low shelf, 1 peak, 2 high shelf, 3 high-pass
  {
    const float fs = 48000.f, A = std::pow(10.f, db / 40.f), w = 2.f * 3.14159265f * std::clamp(fc, 10.f, 20000.f) / fs;
    const float cw = std::cos(w), sw = std::sin(w), al = sw / (2.f * std::max(q, 0.1f));
    float B0, B1, B2, A0, A1, A2;
    if (type == 1) { B0 = 1 + al * A; B1 = -2 * cw; B2 = 1 - al * A; A0 = 1 + al / A; A1 = -2 * cw; A2 = 1 - al / A; }
    else if (type == 3) { B0 = (1 + cw) / 2; B1 = -(1 + cw); B2 = (1 + cw) / 2; A0 = 1 + al; A1 = -2 * cw; A2 = 1 - al; }
    else
    {
      const float sa = 2 * std::sqrt(A) * al, sg = type == 0 ? 1.f : -1.f;
      B0 = A * ((A + 1) - sg * (A - 1) * cw + sa); B1 = sg * 2 * A * ((A - 1) - sg * (A + 1) * cw);
      B2 = A * ((A + 1) - sg * (A - 1) * cw - sa); A0 = (A + 1) + sg * (A - 1) * cw + sa;
      A1 = -sg * 2 * ((A - 1) + sg * (A + 1) * cw); A2 = (A + 1) + sg * (A - 1) * cw - sa;
    }
    b0 = B0 / A0; b1 = B1 / A0; b2 = B2 / A0; a1 = A1 / A0; a2 = A2 / A0;
  }
};
struct Extra
{
  void* key = nullptr;
  float last[6] = {-1, -1, -1, -1, -1, -1};
  bool eq_on = false;
  Biquad lo, mid, hi, hp;
  float env = 0.f, gg = 1.f;
  float dry[2][512];
};
Extra g_extra[16];
Extra& extra_for(void* key)
{
  for (auto& e : g_extra) if (e.key == key) return e;
  for (auto& e : g_extra) if (!e.key) { e.key = key; return e; }
  return g_extra[15];
}
} // namespace pro
'''
tabs = ', '.join('%.3ff' % v for v in tab)
troca('// [mx5-a2] Entrada real chamada pelo trampolim.', helpers.replace('%s', tabs).replace('%%', '%') + '\n// [mx5-a2] Entrada real chamada pelo trampolim.')

# leituras dos botoes: Anxiety OD -> BitDist
troca('const float drive_raw = *reinterpret_cast<float*>(reinterpret_cast<uint8_t*>(this_) + 0x534); // model select',
      'const float drive_raw = pro::resample_norm(this_); // [mx5-v8] RESAMPLE = MODEL NAM')
troca('const float tone_raw = *reinterpret_cast<float*>(reinterpret_cast<uint8_t*>(this_) + 0x548);   // input trim',
      'const float tone_raw = 0.5f; // [mx5-v8] entrada vem do Drive (pro::in_gain)')
troca('const float level_raw = *reinterpret_cast<float*>(reinterpret_cast<uint8_t*>(this_) + 0x520);  // output trim',
      'const float level_raw = 0.5f; // [mx5-v8] saida vem do FX Out (pro::out_gain)')
troca('  const float in_gain = trim_gain(tone_raw);\n  const float out_gain = trim_gain(level_raw);',
      '  (void)tone_raw; (void)level_raw;\n  const float in_gain = pro::in_gain(this_);\n  const float out_gain = pro::out_gain(this_);')
troca('const int hl = *(reinterpret_cast<uint8_t*>(this_) + 0x554) != 0 ? 1 : 0;',
      'const int hl = pro::mode(this_); // [mx5-v8] 0 LITE, 1 FULL, 2 AUTO (Bit Mode)')
troca('    return s.hilo.load(std::memory_order_relaxed) ? 1 : 2; // High = Full, Low = Lite',
      '  {\n    const int h = s.hilo.load(std::memory_order_relaxed);\n    return h == 2 ? 0 : h ? 1 : 2; // [mx5-v8] AUTO / FULL / LITE\n  }')

# gate na entrada + copia seca (antes do ganho de entrada; entrada e saida podem ser o mesmo buffer)
troca('''  for (uint32_t ch = 0; ch < numChannels; ++ch)
    if (input[ch] && output[ch])
      for (int32_t i = 0; i < numFrames; ++i)
        output[ch][i] = std::clamp(input[ch][i] * in_gain, -1.0f, 1.0f);
''', '''  auto& px = pro::extra_for(this_);
  {
    // GATE (THRESH guarda o limiar linear, -60..0 dB; no minimo = desligado)
    const float thr = pro::f(this_, 0x5b0);
    const bool gate_on = thr > 0.0011f;
    for (int32_t i = 0; i < numFrames && i < 512; ++i)
    {
      float a = 0.f;
      for (uint32_t ch = 0; ch < numChannels; ++ch)
        if (input[ch]) a = std::max(a, std::fabs(input[ch][i]));
      px.env = a > px.env ? a : px.env * 0.99958f; // ~50 ms
      const float target = !gate_on ? 1.f : px.env > thr ? 1.f : px.env < thr * 0.5f ? 0.f : px.gg;
      px.gg += (target - px.gg) * (target > px.gg ? 0.02f : 0.0015f);
      for (uint32_t ch = 0; ch < numChannels && ch < 2; ++ch)
        if (input[ch]) px.dry[ch][i] = input[ch][i] * px.gg;
    }
  }
  for (uint32_t ch = 0; ch < numChannels; ++ch)
    if (input[ch] && output[ch])
      for (int32_t i = 0; i < numFrames; ++i)
        output[ch][i] = std::clamp((ch < 2 && i < 512 ? px.dry[ch][i] : input[ch][i]) * in_gain, -1.0f, 1.0f);
''')

# EQ no NAM + blend com o seco + saida
troca('''  for (uint32_t ch = 0; ch < numChannels; ++ch)
    if (input[ch] && output[ch])
      for (int32_t i = 0; i < numFrames; ++i)
        output[ch][i] = std::clamp(output[ch][i] * out_gain, -1.0f, 1.0f);
}''', '''  {
    // EQ (BASS = Bit Power, TREBLE = Res Smooth, MID = Crush Comp + Freq + Q) e BLEND (Mix)
    const float bass = (pro::f(this_, 0x5c8) - 0.5f) * 24.f, treb = (pro::f(this_, 0x59c) - 0.5f) * 24.f;
    const float midg = pro::f(this_, 0x5bc);
    const float mid = midg > 0.f ? ((20.f * std::log10(midg) + 30.f) / 30.f - 0.5f) * 24.f : 0.f;
    const float fq = pro::f(this_, 0x560), q = pro::f(this_, 0x574), mix = pro::blend(this_);
    const float now[6] = {bass, treb, mid, fq, q, mix};
    if (std::memcmp(now, px.last, sizeof now))
    {
      px.lo.set(0, 100.f, 0.707f, bass);
      px.hi.set(2, 4000.f, 0.707f, treb);
      px.mid.set(1, fq, q, mid);
      px.hp.set(3, 120.f, 0.707f, 0.f);
      px.eq_on = q > 0.85f && (std::fabs(bass) > 0.05f || std::fabs(treb) > 0.05f || std::fabs(mid) > 0.05f); // MID Q em 0% = EQ desligado
      std::memcpy(px.last, now, sizeof now);
    }
    const bool blend_on = mix < 0.995f;
    for (uint32_t ch = 0; ch < numChannels && ch < 2; ++ch)
    {
      if (!input[ch] || !output[ch]) continue;
      float* o = output[ch];
      for (int32_t i = 0; i < numFrames && i < 512; ++i)
      {
        float w = o[i];
        if (px.eq_on) w = px.hi.run(ch, px.mid.run(ch, px.lo.run(ch, w)));
        if (blend_on) w = px.hp.run(ch, w) * mix + px.dry[ch][i] * (1.f - mix); // grave do lado limpo
        o[i] = w;
      }
    }
  }
  for (uint32_t ch = 0; ch < numChannels; ++ch)
    if (input[ch] && output[ch])
      for (int32_t i = 0; i < numFrames; ++i)
        output[ch][i] = std::clamp(output[ch][i] * out_gain, -1.0f, 1.0f);
}''')
open(p, 'w').write(s)
print('ok v8_pro')

# ---- diagnostico (estado do modelo) nas estatisticas
s = open(p).read()
def troca2(v, n):
    global s
    assert s.count(v) == 1, v[:60]
    s = s.replace(v, n)
troca2('std::atomic<int> g_off_active{0}, g_off_why{0};\n', 'std::atomic<int> g_off_active{0}, g_off_why{0};\nstd::atomic<int> g_dbg_act{-9}, g_dbg_fade{-9}, g_dbg_idx{-9}, g_dbg_nm{-9}, g_dbg_rd{-9};\n')
troca2('motivo=%d\\n",', 'motivo=%d ativo=%d fade=%d alvo=%d modelos=%d prontos=%d\\n",')
troca2('late, g_off_active.load(), g_off_why.load());', 'late, g_off_active.load(), g_off_why.load(), g_dbg_act.load(), g_dbg_fade.load(), g_dbg_idx.load(), g_dbg_nm.load(), g_dbg_rd.load());')
troca2('  auto& px = pro::extra_for(this_);\n', '  auto& px = pro::extra_for(this_);\n  g_dbg_act.store(s.active_index.load(std::memory_order_relaxed), std::memory_order_relaxed);\n  g_dbg_fade.store(s.fade_state.load(std::memory_order_relaxed), std::memory_order_relaxed);\n  g_dbg_idx.store(knob_value_to_index(drive_raw, static_cast<int>(g_cached_models.size())), std::memory_order_relaxed);\n  g_dbg_nm.store(static_cast<int>(g_cached_models.size()), std::memory_order_relaxed);\n  g_dbg_rd.store(g_models_ready.load() ? 1 : 0, std::memory_order_relaxed);\n')
open(p, 'w').write(s)
print('ok diag')

