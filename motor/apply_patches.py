#!/usr/bin/env python3
"""Aplica as alteracoes sobre uma copia das fontes do lolgab (v0.1.6) + nam_core fixado.
Cada substituicao exige que o trecho original apareca exatamente uma vez."""
import sys, os
root = sys.argv[1]

def patch(path, pairs):
    p = os.path.join(root, path)
    s = open(p, encoding='utf-8').read()
    for old, new in pairs:
        assert s.count(old) == 1, '%s: trecho esperado aparece %d vezes:\n%s' % (path, s.count(old), old)
        s = s.replace(old, new)
    open(p, 'w', encoding='utf-8').write(s)
    print('ok', path, len(pairs), 'trechos')

# ---- nam_core: o detector A2 passa a entregar a configuracao com selecao de motor ----
patch('nam_core/NAM/wavenet/model.cpp', [
    ('// Config parser for ConfigParserRegistry\n',
     '#if defined(NAM_T3K_A2)\n'
     'namespace nam { namespace wavenet { namespace t3k {\n'
     'std::unique_ptr<nam::ModelConfig> create_config(const nlohmann::json& config, double sampleRate);\n'
     '} } }\n'
     '#endif\n\n'
     '// Config parser for ConfigParserRegistry\n'),
    ('    return nam::wavenet::a2_fast::create_a2_fast_config(config, sampleRate);\n',
     '#if defined(NAM_T3K_A2)\n'
     '    return nam::wavenet::t3k::create_config(config, sampleRate);\n'
     '#else\n'
     '    return nam::wavenet::a2_fast::create_a2_fast_config(config, sampleRate);\n'
     '#endif\n'),
])

# ---- nam_hook.cpp: nam_config.txt (qualidade/margem) e registro da calibracao ----
CONFIG = r'''
// ---------------------------------------------------------------------------
// [mx5-a2] Ajustes do usuario: <pasta NAM>/nam_config.txt, lido UMA vez junto
// com a varredura dos .nam (mesmo momento, mesma thread -- nenhum acesso a
// disco novo depois disso). Linhas "chave=valor", '#' comenta.
//   quality=switch|auto|full|lite
//       switch (padrao): a chave Hi-Lo do pedal decide -- Low = A2 Lite, High = A2 Full
//       auto: maior nivel que cabe no tempo real (ignora a chave)
//       full / lite: fixo (ignora a chave)
//   margin=0.50              fracao do orcamento aceita no modo auto (0.30-0.95)
// ---------------------------------------------------------------------------
extern "C" void nam_a2_log(const char* fmt, ...);
std::atomic<int> g_cfg_quality{0}; // 0 switch (chave Hi-Lo), 1 full, 2 lite, 3 auto
std::atomic<double> g_cfg_margin{-1.0}; // <0: usa kCalibrationSafetyMargin

void load_user_config()
{
  std::ifstream in(model_dir() / "nam_config.txt");
  if (!in)
    return;
  std::string line;
  while (std::getline(in, line))
  {
    std::string t;
    for (char c : line)
    {
      if (c == '#')
        break;
      if (!std::isspace(static_cast<unsigned char>(c)))
        t.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
    }
    const auto eq = t.find('=');
    if (eq == std::string::npos)
      continue;
    const std::string key = t.substr(0, eq), val = t.substr(eq + 1);
    if (key == "quality")
      g_cfg_quality.store(val == "full" ? 1 : val == "lite" ? 2 : val == "auto" ? 3 : 0);
    else if (key == "margin")
    {
      const double m = std::strtod(val.c_str(), nullptr);
      if (m >= 0.30 && m <= 0.95)
        g_cfg_margin.store(m);
    }
  }
  nam_a2_log("config: quality=%d (0 chave Hi-Lo,1 full,2 lite,3 auto) margin=%.2f", g_cfg_quality.load(),
             g_cfg_margin.load());
}

// [mx5-a2] Estatisticas do custo real por bloco, medidas na thread de audio (so atomicos la) e
// gravadas a cada 2 s por uma thread propria em /tmp/nam_a2_stats.txt (tmpfs).
std::atomic<uint32_t> g_st_blocks{0}, g_st_sum_us{0}, g_st_max_us{0}, g_st_over{0};
std::atomic<uint32_t> g_st_mono{0}, g_st_stereo{0}, g_st_ch1{0};
int count_claimed_instances();

void start_stats_writer()
{
  spawn_detached([]() {
    lower_background_thread_priority();
    const char* env = std::getenv("NAM_A2_STATS");
    const std::string path = env ? env : "/tmp/nam_a2_stats.txt";
    uint32_t total_over = 0;
    for (;;)
    {
      sleep(2);
      const uint32_t blocks = g_st_blocks.exchange(0), sum = g_st_sum_us.exchange(0), mx = g_st_max_us.exchange(0);
      const uint32_t over = g_st_over.exchange(0), mono = g_st_mono.exchange(0), st = g_st_stereo.exchange(0);
      const uint32_t ch1 = g_st_ch1.exchange(0);
      total_over += over;
      if (FILE* f = fopen(path.c_str(), "w"))
      {
        fprintf(f,
                "blocos_2s=%u media_us=%u max_us=%u acima_do_bloco_2s=%u acima_do_bloco_total=%u carga=%d "
                "mono_colapsado=%u estereo=%u um_canal=%u\n",
                blocks, blocks ? sum / blocks : 0, mx, over, total_over, count_claimed_instances(), mono, st, ch1);
        fclose(f);
      }
    }
  });
}
'''
patch('patch/nam_hook.cpp', [
    ('''  return "/media/az01-internal/Evil/usb_mnt/NAM";
}
''', '''  return "/media/az01-internal/Evil/usb_mnt/NAM";
}
''' + CONFIG),
    ('''    std::vector<CachedModel> found;
    std::error_code ec;
''', '''    std::vector<CachedModel> found;
    std::error_code ec;
    try
    {
      load_user_config(); // [mx5-a2]
    }
    catch (...)
    {
    }
    start_stats_writer(); // [mx5-a2]
'''),
    # ---- v2: threads de carga fora do nucleo/prioridade do audio ----
    ('#include <pthread.h>\n', '#include <pthread.h>\n#include <sched.h>\n'),
    ('''inline void lower_background_thread_priority()
{
  setpriority(PRIO_PROCESS, 0, 19); // 19 = lowest (nicest) niceness
}
''', '''inline void lower_background_thread_priority()
{
  // [mx5-a2] Medido no MX5 real: a thread de audio do Evil e SCHED_RR (prio 49) e presa a UM
  // nucleo (o aparelho tem 4). Threads criadas a partir dela herdam a politica de tempo real E
  // a afinidade -- ou seja, disputavam o mesmo nucleo, na mesma prioridade, com o audio (o
  // niceness abaixo nao tem efeito em SCHED_RR). Volta para a politica normal e sai do nucleo
  // do audio; so mexe na afinidade se a herdada for de um unico nucleo.
  sched_param sp{};
  sp.sched_priority = 0;
  sched_setscheduler(0, SCHED_OTHER, &sp);
  cpu_set_t cur, others;
  CPU_ZERO(&cur);
  CPU_ZERO(&others);
  if (sched_getaffinity(0, sizeof(cur), &cur) == 0 && CPU_COUNT(&cur) == 1)
  {
    const long n = sysconf(_SC_NPROCESSORS_ONLN);
    int cnt = 0;
    for (long c = 0; c < n && c < CPU_SETSIZE; ++c)
      if (!CPU_ISSET(c, &cur))
      {
        CPU_SET(c, &others);
        ++cnt;
      }
    if (cnt > 0)
      sched_setaffinity(0, sizeof(others), &others);
  }
  setpriority(PRIO_PROCESS, 0, 19); // 19 = lowest (nicest) niceness
}
'''),
    # ---- v2: carga real (instancias ativas x canais) em vez de "instancias que ja existiram" ----
    ('''  std::atomic<void*> owner_this{nullptr};
};
''', '''  std::atomic<void*> owner_this{nullptr};

  // [mx5-a2] carga real desta instancia
  std::atomic<int64_t> last_active_ms{0}; // ultima chamada NAO em bypass
  std::atomic<int> eff_channels{1};       // canais realmente processados (1 se L == R)
  std::atomic<int> calib_load{0};         // carga total usada na ultima calibracao
  std::atomic<bool> slimmable_active{false};
  int load_check_countdown = 0; // so a thread de audio
  int overload_hits = 0;        // so a thread de audio

  // [mx5-a2] chave Hi-Lo do Anxiety OD: byte em this_+0x554 (0 = Low, 1 = High), achado por
  // comparacao de memoria no MX5 real (unico byte que muda ao alternar a chave).
  std::atomic<int> hilo{0};
  std::atomic<int> calib_mode{-1}; // modo usado na ultima calibracao (-1 = nenhuma)
  int mode_mismatch_blocks = 0;    // so a thread de audio
};

// Nivel desejado para esta instancia: 0 = automatico, 1 = Full, 2 = Lite.
inline int desired_mode(const ModelState& s)
{
  const int cfg = g_cfg_quality.load(std::memory_order_relaxed);
  if (cfg == 0)
    return s.hilo.load(std::memory_order_relaxed) ? 1 : 2; // High = Full, Low = Lite
  return cfg == 3 ? 0 : cfg;
}
'''),
    ('''int count_claimed_instances()
{
  int n = 0;
  for (auto& inst : g_instances)
    if (inst.owner_this.load(std::memory_order_acquire) != nullptr)
      ++n;
  return n;
}
''', '''// [mx5-a2] Antes: contava toda instancia que JA EXISTIU neste boot (cada troca de rig somava
// uma), e o orcamento encolhia ate tudo cair para o Lite -- medido no MX5 real ("3 inst." com
// no maximo 2 pedais). Agora: soma os canais processados pelas instancias que rodaram fora de
// bypass nos ultimos kInstanceActiveWindowMs.
constexpr int64_t kInstanceActiveWindowMs = 40;
int count_claimed_instances()
{
  const int64_t now = now_ms();
  int n = 0;
  for (auto& inst : g_instances)
    if (inst.owner_this.load(std::memory_order_acquire) != nullptr
        && now - inst.last_active_ms.load(std::memory_order_relaxed) < kInstanceActiveWindowMs)
      n += std::max(1, inst.eff_channels.load(std::memory_order_relaxed));
  return n;
}
'''),
    ('''  int epoch = -1;
};
''', '''  int epoch = -1;
  int load = -1; // [mx5-a2] carga para a qual este nivel foi calculado
  int mode = -1; // [mx5-a2] modo (auto/full/lite) para o qual foi calculado
};
'''),
    ('''        d = nam::get_dsp(config);
        d->Reset(kSampleRate, 128); // establish sample rate/buffer size FIRST --
''', '''        d = nam::get_dsp(config);
        if (i == 0) // [mx5-a2]
          s.slimmable_active.store(dynamic_cast<nam::SlimmableModel*>(d.get()) != nullptr,
                                   std::memory_order_relaxed);
        d->Reset(kSampleRate, 128); // establish sample rate/buffer size FIRST --
'''),
    ('''            if (entry.ratio < 0.0 || entry.epoch != live_epoch)
            {
              entry.ratio = calibrate_slimmable_quality(*d, *slimmable);
              entry.epoch = live_epoch;
            }
            else
              slimmable->SetSlimmableSize(entry.ratio);
            chosen_ratio = entry.ratio;
''', '''            // [mx5-a2] espera instancias de um rig anterior sairem da janela de atividade
            usleep(static_cast<useconds_t>((kInstanceActiveWindowMs + 20) * 1000));
            const int cur_load = std::max(1, count_claimed_instances());
            const int want = desired_mode(s);
            if (entry.ratio < 0.0 || entry.epoch != live_epoch || entry.load != cur_load || entry.mode != want)
            {
              entry.ratio = calibrate_slimmable_quality(*d, *slimmable, want);
              entry.epoch = live_epoch;
              entry.load = cur_load;
              entry.mode = want;
            }
            else
              slimmable->SetSlimmableSize(entry.ratio);
            chosen_ratio = entry.ratio;
            s.calib_load.store(cur_load, std::memory_order_relaxed);
            s.calib_mode.store(want, std::memory_order_relaxed);
'''),
    # ---- v2: envoltorio da entrada de audio: mono (L == R), carga, estatisticas ----
    ('''extern "C" void nam_process_gonk(void* this_, uint32_t /*param2*/, float** input, uint32_t numChannels,
''', '''static void nam_process_gonk_impl(void*, uint32_t, float**, uint32_t, float**, int32_t, uint32_t*, void*);

// [mx5-a2] Entrada real chamada pelo trampolim. Envolve a implementacao original para:
//  1. processar UMA vez quando os dois canais trazem o mesmo sinal (guitarra mono antes de
//     qualquer efeito estereo) e copiar o resultado -- metade do custo, mesmo som;
//  2. registrar a carga real (instancia ativa, canais processados) para a calibracao;
//  3. se a carga passar do que foi calibrado, recalibrar (mesmo mecanismo de fade do original);
//  4. medir o tempo gasto por bloco (estatisticas em /tmp/nam_a2_stats.txt).
extern "C" void nam_process_gonk(void* this_, uint32_t param2, float** input, uint32_t numChannels, float** output,
                                 int32_t numFrames, uint32_t* flags, void* ctx)
{
  if (numFrames <= 0 || !input || !output || numChannels == 0 || !this_)
  {
    nam_process_gonk_impl(this_, param2, input, numChannels, output, numFrames, flags, ctx);
    return;
  }
  const auto t0 = std::chrono::steady_clock::now();
  const size_t bytes = static_cast<size_t>(numFrames) * sizeof(float);
  const bool collapsed = numChannels >= 2 && input[0] && input[1] && output[0] && output[1] && input[0] != input[1]
                         && output[0] != output[1] && std::memcmp(input[0], input[1], bytes) == 0;
  auto& s = state_for(this_);
  const int eff = collapsed ? 1 : static_cast<int>(std::min<uint32_t>(numChannels, kMaxChannels));
  if (s.eff_channels.load(std::memory_order_relaxed) != eff)
    s.eff_channels.store(eff, std::memory_order_relaxed);
  const bool bypassed = *(reinterpret_cast<uint8_t*>(this_) + 0x26b) != 0;
  if (!bypassed)
    s.last_active_ms.store(now_ms(), std::memory_order_relaxed);

  // Chave Hi-Lo: se o nivel pedido deixou de ser o calibrado (e ficou assim por ~150 ms),
  // recarrega o mesmo modelo no nivel novo, com o fade normal de troca.
  const int hl = *(reinterpret_cast<uint8_t*>(this_) + 0x554) != 0 ? 1 : 0;
  if (s.hilo.load(std::memory_order_relaxed) != hl)
    s.hilo.store(hl, std::memory_order_relaxed);
  const int cm = s.calib_mode.load(std::memory_order_relaxed);
  if (cm >= 0 && s.slimmable_active.load(std::memory_order_relaxed) && desired_mode(s) != cm)
  {
    if (++s.mode_mismatch_blocks >= 150 && s.fade_state.load(std::memory_order_relaxed) == 0
        && s.active_index.load(std::memory_order_acquire) >= 0)
    {
      s.mode_mismatch_blocks = 0;
      s.force_recalibrate = true;
      s.fade_state.store(1, std::memory_order_relaxed);
      s.fade_progress = 0;
    }
  }
  else
    s.mode_mismatch_blocks = 0;

  nam_process_gonk_impl(this_, param2, input, collapsed ? 1u : numChannels, output, numFrames, flags, ctx);
  if (collapsed)
    std::memcpy(output[1], output[0], bytes);

  if (!bypassed)
  {
    if (++s.load_check_countdown >= 256)
    {
      s.load_check_countdown = 0;
      const int cal = s.calib_load.load(std::memory_order_relaxed);
      // so no modo automatico: com nivel fixo (chave Hi-Lo ou nam_config) nao ha o que recalcular
      if (cal > 0 && desired_mode(s) == 0 && s.slimmable_active.load(std::memory_order_relaxed)
          && count_claimed_instances() > cal)
      {
        // duas verificacoes seguidas (~0,5 s) antes de agir: ignora sobreposicoes de troca de rig
        if (++s.overload_hits >= 2 && s.fade_state.load(std::memory_order_relaxed) == 0
            && s.active_index.load(std::memory_order_acquire) >= 0)
        {
          s.overload_hits = 0;
          s.force_recalibrate = true;
          s.fade_state.store(1, std::memory_order_relaxed);
          s.fade_progress = 0;
        }
      }
      else
        s.overload_hits = 0;
    }
    const uint32_t us = static_cast<uint32_t>(
      std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now() - t0).count());
    g_st_blocks.fetch_add(1, std::memory_order_relaxed);
    g_st_sum_us.fetch_add(us, std::memory_order_relaxed);
    uint32_t mx = g_st_max_us.load(std::memory_order_relaxed);
    while (us > mx && !g_st_max_us.compare_exchange_weak(mx, us, std::memory_order_relaxed))
    {
    }
    if (us > 1000u * static_cast<uint32_t>(numFrames) / 48u)
      g_st_over.fetch_add(1, std::memory_order_relaxed);
    (collapsed ? g_st_mono : numChannels >= 2 ? g_st_stereo : g_st_ch1).fetch_add(1, std::memory_order_relaxed);
  }
}

static void nam_process_gonk_impl(void* this_, uint32_t /*param2*/, float** input, uint32_t numChannels,
'''),

    ('''  const size_t num_tiers = breakpoints.size() + 1;
''', '''  const size_t num_tiers = breakpoints.size() + 1;

  // [mx5-a2] margem e nivel forcado vindos de nam_config.txt
  const double cfg_margin = g_cfg_margin.load();
  const double margin = cfg_margin > 0.0 ? cfg_margin : kCalibrationSafetyMargin;
  const int forced = want; // 1 full, 2 lite (chave Hi-Lo ou nam_config.txt); 0 = automatico
  if (forced == 1 || forced == 2)
  {
    const size_t tier = forced == 1 ? num_tiers - 1 : 0;
    const double ratio = (static_cast<double>(tier) + 0.5) / static_cast<double>(num_tiers);
    slimmable.SetSlimmableSize(ratio);
    dsp.Reset(kSampleRate, kCalibrationBlockSize);
    nam_a2_log("calib: nivel %zu/%zu escolhido (%s; quality=%d)", tier + 1, num_tiers,
               forced == 1 ? "FULL" : "LITE", g_cfg_quality.load());
    return ratio;
  }
'''),
    ('''double calibrate_slimmable_quality(nam::DSP& dsp, nam::SlimmableModel& slimmable)
{
''', '''double calibrate_slimmable_quality(nam::DSP& dsp, nam::SlimmableModel& slimmable, int want)
{
'''),
    ('''    if (avg_us < budget_us * kCalibrationSafetyMargin)
      return ratio;
''', '''    const bool fits = avg_us < budget_us * margin;
    nam_a2_log("calib: nivel %zu/%zu = %.0f us/bloco; limite %.0f us (orcamento %.0f us, %d inst., margem %.2f) -> %s",
               tier + 1, num_tiers, avg_us, budget_us * margin, budget_us, concurrent_instances, margin,
               fits ? "USADO" : "nao cabe");
    if (fits)
      return ratio;
'''),
])
