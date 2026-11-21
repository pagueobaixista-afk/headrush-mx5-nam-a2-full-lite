"""v8.2: troca de modelo NAM imediata (reserva de modelos prontos).
uso (WSL): python3 v82_reserva.py <build>/patch/nam_hook.cpp   (aplica depois de v81_troca.py)

Uma thread de fundo (nucleo 3) mantem TODOS os modelos da pasta ja montados, no nivel certo
(LITE/FULL/AUTO) e aquecidos. Na troca, a thread de audio so pega o modelo pronto:
knob parado 25 ms -> fade-out 30 ms -> troca -> fade-in 30 ms. Vale tambem para o primeiro
modelo de um rig novo. O modelo retirado e reposto em segundo plano.
Sem reserva pronta (estereo real, nivel mudando, memoria baixa) vale o caminho da v8.1.
Desliga com o arquivo nam_reserva_off.txt na pasta NAM."""
import re
import sys

p = sys.argv[1]
s = open(p, encoding='utf-8').read()


def troca(a, b, n=1):
    global s
    c = s.count(a)
    if c != n:
        sys.exit('v82: trecho encontrado %d vezes (esperado %d): %r' % (c, n, a[:90]))
    s = s.replace(a, b)


# 1) contador para as estatisticas
troca('std::atomic<int> g_dbg_act{-9},', 'std::atomic<int> g_pool_ready_count{0}; // [mx5-v82]\nstd::atomic<int> g_dbg_act{-9},')
troca('modelos=%d prontos=%d\\n"', 'modelos=%d prontos=%d reserva=%d\\n"')
troca('g_dbg_nm.load(), g_dbg_rd.load());', 'g_dbg_nm.load(), g_dbg_rd.load(), g_pool_ready_count.load());')

# 2) estado por instancia
troca('  std::atomic<bool> saw_stereo{false};',
      '''  // [mx5-v82] so a thread de audio: o modelo em pending_dsp veio da reserva?
  bool pend_pool = false, pend_slim = false, act_pool = false;
  int pend_load = 0, pend_mode = -1;
  int v82_cand = -3, v82_cand_mode = -1;
  // carregamento antigo (thread de fundo) entrega aqui; a thread de audio decide se usa
  std::unique_ptr<nam::DSP> bg_dsp[kMaxChannels];
  int bg_index = -1;
  std::atomic<bool> bg_ready{false};
  int64_t v82_since = 0, v82_first_ms = 0;
  std::atomic<bool> saw_stereo{false};''')

# 3) a reserva
POOL = r'''// ---------------------------------------------------------------------------------------
// [mx5-v82] Reserva de modelos prontos. Um slot por arquivo; estados: 0 vazio, 1 pronto,
// 2 ocupado (quem fez o CAS para 2 e o dono ate gravar outro estado), 4 usado (so precisa
// reaquecer com silencio, bem mais rapido que montar de novo), 5 falhou (nao tenta mais).
struct PoolSlot
{
  std::atomic<int> st{0};
  nam::DSP* d = nullptr;
  int load = 0, mode = -1;
  bool slim = false;
};
constexpr int kPoolMax = 128;
constexpr int64_t kPoolSettleMs = 25;
PoolSlot g_pool[3][kPoolMax]; // uma reserva por nivel: 0 AUTO, 1 FULL, 2 LITE
std::atomic<int> g_pool_want_mode{-1};
std::atomic<int> g_pool_focus{0};
std::atomic<bool> g_pool_started{false};
std::atomic<bool> g_pool_off{false};
std::atomic<nam::DSP*> g_trash[32];

// a thread de audio nunca libera memoria: entrega para a thread de fundo
inline void pool_trash(nam::DSP* d)
{
  if (!d)
    return;
  for (auto& t : g_trash)
  {
    nam::DSP* e = nullptr;
    if (t.compare_exchange_strong(e, d))
      return;
  }
  delete d;
}

inline bool pool_tag_ok(const PoolSlot& p, int mode, int load)
{
  return p.mode == mode && (mode != 0 || !p.slim || p.load == load);
}

inline nam::DSP* pool_take(int idx, int mode, int load, bool* slim, int* eload)
{
  if (idx < 0 || idx >= kPoolMax || mode < 0 || mode > 2)
    return nullptr;
  auto& p = g_pool[mode][idx];
  int e = 1;
  if (!p.st.compare_exchange_strong(e, 2))
    return nullptr;
  if (!pool_tag_ok(p, mode, load))
  {
    p.st.store(1);
    return nullptr;
  }
  nam::DSP* d = p.d;
  p.d = nullptr;
  *slim = p.slim;
  *eload = p.load;
  p.st.store(0);
  return d;
}

// devolve um modelo que saiu da reserva e nunca tocou
inline void pool_give(int idx, nam::DSP* d, int mode, int load, bool slim, int st_final = 1)
{
  if (!d)
    return;
  int e = 0;
  if (idx < 0 || idx >= kPoolMax || mode < 0 || mode > 2 || !g_pool[mode][idx].st.compare_exchange_strong(e, 2))
  {
    pool_trash(d);
    return;
  }
  auto& p = g_pool[mode][idx];
  p.d = d;
  p.mode = mode;
  p.load = load;
  p.slim = slim;
  p.st.store(st_final);
}

inline void v82_drop(ModelState& s)
{
  nam::DSP* d0 = s.pending_dsp[0].release();
  if (s.pend_pool)
    pool_give(s.pending_index, d0, s.pend_mode, s.pend_load, s.pend_slim);
  else
    pool_trash(d0);
  pool_trash(s.pending_dsp[1].release());
  s.pend_pool = false;
  s.pending_ready.store(false, std::memory_order_release);
}

inline bool v82_stage(ModelState& s, int idx, int want)
{
  bool slim = false;
  int el = 0;
  nam::DSP* d = pool_take(idx, want, std::max(1, count_claimed_instances()), &slim, &el);
  if (!d)
    return false;
  v82_drop(s);
  s.pending_dsp[0].reset(d);
  s.pending_index = idx;
  s.pend_pool = true;
  s.pend_slim = slim;
  s.pend_load = el;
  s.pend_mode = want;
  s.pending_ready.store(true, std::memory_order_release);
  return true;
}

inline void v82_install(ModelState& s)
{
  for (int i = 0; i < kMaxChannels; ++i)
  {
    nam::DSP* old = s.dsp[i].release();
    if (i == 0 && s.act_pool) // veio da reserva: volta como "usado" e so e reaquecido
      pool_give(s.active_index.load(std::memory_order_relaxed), old, s.calib_mode.load(std::memory_order_relaxed),
                s.calib_load.load(std::memory_order_relaxed), s.slimmable_active.load(std::memory_order_relaxed), 4);
    else
      pool_trash(old);
    s.dsp[i] = std::move(s.pending_dsp[i]);
  }
  s.act_pool = s.pend_pool;
  if (s.pend_pool)
  {
    s.slimmable_active.store(s.pend_slim, std::memory_order_relaxed);
    s.calib_load.store(s.pend_load, std::memory_order_relaxed);
    s.calib_mode.store(s.pend_mode, std::memory_order_relaxed);
    s.pend_pool = false;
  }
}

nam::DSP* pool_build(int idx, int want, int load, bool* slim)
{
  std::unique_ptr<nam::DSP> d = nam::get_dsp(g_cached_models[static_cast<size_t>(idx)].config);
  d->Reset(kSampleRate, 128);
  *slim = false;
  if (auto* sl = dynamic_cast<nam::SlimmableModel*>(d.get()))
  {
    *slim = true;
    std::lock_guard<std::mutex> lock(g_calibration_cache_mutex);
    auto& entry = g_calibration_cache[static_cast<size_t>(idx)];
    const int live_epoch = g_topology_epoch.load(std::memory_order_acquire);
    if (entry.ratio < 0.0 || entry.epoch != live_epoch || entry.load != load || entry.mode != want)
    {
      entry.ratio = calibrate_slimmable_quality(*d, *sl, want);
      entry.epoch = live_epoch;
      entry.load = load;
      entry.mode = want;
    }
    else
      sl->SetSlimmableSize(entry.ratio);
  }
  d->Reset(kSampleRate, 128);
  std::vector<float> silence(128, 0.0f), scratch(128, 0.0f);
  float* in_arr[1] = {silence.data()};
  float* out_arr[1] = {scratch.data()};
  for (int32_t done = 0; done < 16384; done += 128)
  {
    d->process(in_arr, out_arr, 128);
    usleep(250); // sem pressa: deixa o barramento de memoria para o audio
  }
  return d.release();
}

long pool_mem_available_mb()
{
  long kb = -1;
  if (FILE* f = std::fopen("/proc/meminfo", "r"))
  {
    char line[128];
    while (std::fgets(line, sizeof line, f))
      if (std::sscanf(line, "MemAvailable: %ld kB", &kb) == 1)
        break;
    std::fclose(f);
  }
  return kb < 0 ? 100000 : kb / 1024;
}

void pool_start()
{
  bool e = false;
  if (!g_pool_started.compare_exchange_strong(e, true))
    return;
  spawn_detached([]() {
    flush_denormals_to_zero();
    lower_background_thread_priority();
    { cpu_set_t c3; CPU_ZERO(&c3); CPU_SET(3, &c3); sched_setaffinity(0, sizeof(c3), &c3); }
    std::error_code ec;
    if (std::filesystem::exists(model_dir() / "nam_reserva_off.txt", ec))
    {
      g_pool_off.store(true);
      nam_a2_log("reserva: desligada (nam_reserva_off.txt)");
      for (;;)
      {
        for (auto& t : g_trash)
          delete t.exchange(nullptr);
        usleep(50000);
      }
    }
    int cand_load = 0, stable_load = 1, last_full = -1;
    int64_t cand_since = 0;
    bool low_mem_logged = false;
    for (;;)
    {
      for (auto& t : g_trash)
        delete t.exchange(nullptr);
      const int want = g_pool_want_mode.load(std::memory_order_relaxed);
      if (!g_models_ready.load(std::memory_order_acquire) || want < 0 || want > 2)
      {
        usleep(100000);
        continue;
      }
      const int n = std::min(static_cast<int>(g_cached_models.size()), kPoolMax);
      const int claimed = count_claimed_instances();
      const int load_now = claimed > 0 ? claimed : stable_load;
      if (load_now != cand_load)
      {
        cand_load = load_now;
        cand_since = now_ms();
      }
      if (now_ms() - cand_since >= 600) // a carga so vale depois de estavel (troca de rig)
        stable_load = cand_load;
      const int load = stable_load;
      const int focus = std::clamp(g_pool_focus.load(std::memory_order_relaxed), 0, std::max(0, n - 1));
      int ready_n = 0;
      for (int i = 0; i < n; ++i)
        if (g_pool[want][i].st.load() == 1 && pool_tag_ok(g_pool[want][i], want, load))
          ++ready_n;
      g_pool_ready_count.store(ready_n, std::memory_order_relaxed);
      // primeiro o nivel em uso, do modelo mais perto do knob para fora; depois os outros niveis
      int pick = -1, mode = want;
      for (int k = 0; k < 3 && pick < 0; ++k)
      {
        mode = (want + k) % 3;
        for (int dist = 0; dist < n && pick < 0; ++dist)
          for (int sgn = 0; sgn < 2 && pick < 0; ++sgn)
          {
            const int i = sgn ? focus + dist : focus - dist;
            if (i < 0 || i >= n)
              continue;
            const int st = g_pool[mode][i].st.load();
            if (st == 0 || st == 4 || (st == 1 && !pool_tag_ok(g_pool[mode][i], mode, load)))
              pick = i;
          }
      }
      if (pick < 0)
      {
        if (last_full != ready_n)
          nam_a2_log("reserva: completa, %d modelos x 3 niveis (carga %d, livre %ld MB)", n, load,
                     pool_mem_available_mb());
        last_full = ready_n;
        usleep(20000);
        continue;
      }
      last_full = -1;
      if (pool_mem_available_mb() < 150)
      {
        if (!low_mem_logged)
          nam_a2_log("reserva: memoria baixa, parou (nivel em uso com %d modelos)", ready_n);
        low_mem_logged = true;
        usleep(500000);
        continue;
      }
      auto& p = g_pool[mode][pick];
      int st = p.st.load();
      if ((st != 0 && st != 1 && st != 4) || !p.st.compare_exchange_strong(st, 2))
        continue;
      if (st == 4 && p.d && pool_tag_ok(p, mode, load))
      {
        // usado: silencio por mais que o campo receptivo zera o estado, igual a um modelo novo
        std::vector<float> silence(128, 0.0f), scratch(128, 0.0f);
        float* in_arr[1] = {silence.data()};
        float* out_arr[1] = {scratch.data()};
        for (int32_t done = 0; done < 24064; done += 128)
          p.d->process(in_arr, out_arr, 128);
        p.st.store(1);
        continue;
      }
      delete p.d; // pronto mas no nivel antigo
      p.d = nullptr;
      try
      {
        bool slim = false;
        p.d = pool_build(pick, mode, load, &slim);
        p.mode = mode;
        p.load = load;
        p.slim = slim;
        p.st.store(1);
      }
      catch (...)
      {
        p.d = nullptr;
        p.st.store(5);
      }
    }
  });
}
// ---------------------------------------------------------------------------------------

void switch_model_in_background(ModelState& s, float raw, bool force_reload_same_model = false)
{'''
troca('void switch_model_in_background(ModelState& s, float raw, bool force_reload_same_model = false)\n{', POOL)

# 3b) a thread de carregamento antiga entrega em bg_dsp (assim a reserva pode agir com ela em andamento)
troca('''        for (int i = 0; i < kMaxChannels; ++i)
          s.pending_dsp[i].reset();
        s.pending_index = idx;
        s.pending_ready.store(true, std::memory_order_release);
        return;''',
      '''        for (int i = 0; i < kMaxChannels; ++i)
          s.bg_dsp[i].reset();
        s.bg_index = idx;
        s.bg_ready.store(true, std::memory_order_release); // [mx5-v82]
        return;''')
troca('''      for (int i = 0; i < kMaxChannels; ++i)
        s.pending_dsp[i] = std::move(loaded[i]);
      s.pending_index = idx;
      s.pending_ready.store(true, std::memory_order_release);''',
      '''      for (int i = 0; i < kMaxChannels; ++i)
        s.bg_dsp[i] = std::move(loaded[i]);
      s.bg_index = idx;
      s.bg_ready.store(true, std::memory_order_release); // [mx5-v82]''')
troca('''|| s.pending_ready.load(std::memory_order_acquire))
    return;

  bool expected = false;''',
      '''|| s.pending_ready.load(std::memory_order_acquire)
      || s.bg_ready.load(std::memory_order_acquire))
    return;

  bool expected = false;''')
# com a reserva ativa, o caminho antigo so entra se ela nao entregar em 700 ms
troca('''             && now_ms() - s.candidate_since_ms >= kKnobSettleMs)''',
      '''             && now_ms() - s.candidate_since_ms
                  >= ((s.saw_stereo.load(std::memory_order_relaxed) || g_pool_off.load(std::memory_order_relaxed))
                        ? kKnobSettleMs : 700)) // [mx5-v82]''')

# 4) thread de audio: so a partir da implementacao real
cut = s.rindex('static void nam_process_gonk_impl(')
head, tail = s[:cut], s[cut:]


def sub(pat, rep, n, nome):
    global tail
    tail, c = re.subn(pat, rep, tail)
    if c != n:
        sys.exit('v82: %s encontrado %d vezes (esperado %d)' % (nome, c, n))


sub(r'for \(int i = 0; i < kMaxChannels; \+\+i\)\n\s*s\.dsp\[i\] = std::move\(s\.pending_dsp\[i\]\);',
    'v82_install(s); // [mx5-v82]', 3, 'instalacao')
sub(r'for \(int i = 0; i < kMaxChannels; \+\+i\)(?: //[^\n]*)?\n\s*s\.pending_dsp\[i\]\.reset\(\);',
    'v82_drop(s); // [mx5-v82]', 3, 'descarte')
sub(r's\.dsp\[ch\]->process\(in_arr, out_arr, numFrames\);',
    'if (s.dsp[ch]) s.dsp[ch]->process(in_arr, out_arr, numFrames); '
    'else std::fill(output[ch], output[ch] + numFrames, 0.0f); // [mx5-v82]', 4, 'process')
s = head + tail

# 4a) pedido imediato a reserva (troca de modelo e primeiro modelo de um rig)
troca('  s.last_seen_knob_raw.store(drive_raw, std::memory_order_release);\n',
      '''  s.last_seen_knob_raw.store(drive_raw, std::memory_order_release);
  { // [mx5-v82] modelo pronto na reserva: troca sem esperar carregamento
    const int t82 = knob_value_to_index(drive_raw, static_cast<int>(g_cached_models.size()));
    const int want82 = desired_mode(s);
    const int64_t now82 = now_ms();
    g_pool_want_mode.store(want82, std::memory_order_relaxed);
    if (t82 >= 0)
      g_pool_focus.store(t82, std::memory_order_relaxed);
    pool_start();
    if (s.v82_first_ms == 0)
      s.v82_first_ms = now82;
    if (t82 != s.v82_cand || want82 != s.v82_cand_mode)
    {
      s.v82_cand = t82;
      s.v82_cand_mode = want82;
      s.v82_since = now82;
    }
    const int cm82 = s.calib_mode.load(std::memory_order_relaxed);
    if (s.bg_ready.load(std::memory_order_acquire))
    { // resultado do carregamento antigo: so serve se ainda for o alvo e nada estiver preparado
      if (!s.pending_ready.load(std::memory_order_acquire) && (s.bg_index == t82 || t82 == -2))
      {
        v82_drop(s);
        for (int i = 0; i < kMaxChannels; ++i)
          s.pending_dsp[i] = std::move(s.bg_dsp[i]);
        s.pending_index = s.bg_index;
        s.pending_ready.store(true, std::memory_order_release);
      }
      else
        for (int i = 0; i < kMaxChannels; ++i)
          pool_trash(s.bg_dsp[i].release());
      s.bg_ready.store(false, std::memory_order_release);
    }
    const bool rdy82 = s.ready.load(std::memory_order_acquire);
    if (t82 >= 0 && g_models_ready.load(std::memory_order_acquire)
        && !s.pending_ready.load(std::memory_order_acquire) && !s.saw_stereo.load(std::memory_order_relaxed)
        && (!rdy82
            || ((t82 != s.active_index.load(std::memory_order_acquire)
                 || (cm82 >= 0 && cm82 != want82 && s.slimmable_active.load(std::memory_order_relaxed)))
                && s.fade_state.load(std::memory_order_relaxed) == 0 && !s.force_recalibrate
                && now82 - s.v82_since >= kPoolSettleMs)))
      v82_stage(s, t82, want82);
  }
''')

# 4b) primeiro modelo: da 60 ms para a reserva (a carga do rig anterior sai da janela) antes do caminho antigo
troca('''    // means the very next call after preload finishes picks it up.
    switch_model_in_background(s, drive_raw, s.force_recalibrate);''',
      '''    // means the very next call after preload finishes picks it up.
    if (!s.pending_ready.load(std::memory_order_acquire) && now_ms() - s.v82_first_ms >= 60) // [mx5-v82]
      switch_model_in_background(s, drive_raw, s.force_recalibrate);''')

# 4c) fim do fade-out: se o knob andou, pega o alvo atual direto da reserva
troca('''      if (s.pending_ready.load(std::memory_order_acquire) && current_idx == s.pending_index)
      {
        // [mx5-v81] troca direta''',
      '''      if (current_idx >= 0
          && (current_idx != s.active_index.load(std::memory_order_acquire)
              || (s.pend_pool && s.pend_mode != desired_mode(s)))
          && !(s.pending_ready.load(std::memory_order_acquire) && current_idx == s.pending_index)
          && !s.saw_stereo.load(std::memory_order_relaxed) && !s.force_recalibrate)
        v82_stage(s, current_idx, desired_mode(s)); // [mx5-v82]
      if (s.pending_ready.load(std::memory_order_acquire) && current_idx == s.pending_index)
      {
        // [mx5-v81] troca direta''')

# 4d) estereo real numa instancia que veio da reserva (so canal 1): refaz com os dois canais
troca('''    s.saw_stereo.store(true, std::memory_order_relaxed); // [mx5-v81]''',
      '''  {
    s.saw_stereo.store(true, std::memory_order_relaxed); // [mx5-v81]
    if (!s.dsp[1] && s.active_index.load(std::memory_order_relaxed) >= 0)
      s.force_recalibrate = true; // [mx5-v82]
  }''')

open(p, 'w', encoding='utf-8').write(s)
print('ok v82_reserva')

# 5) transicao minima: knob parado 8 ms -> fade-out 10 ms -> troca -> fade-in 15 ms
s = open(p, encoding='utf-8').read()
troca('return 1440; // [mx5-v81] 30 ms: o modelo novo ja chega pronto', 'return 480; // [mx5-v82] 10 ms')
troca('return 1440; // [mx5-v81] 30 ms\n', 'return 720; // [mx5-v82] 15 ms\n')
troca('constexpr int64_t kPoolSettleMs = 25;', 'constexpr int64_t kPoolSettleMs = 8;')
open(p, 'w', encoding='utf-8').write(s)
print('ok v82 transicao minima')
