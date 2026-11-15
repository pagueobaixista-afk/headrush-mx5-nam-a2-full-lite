// t3k_a2.cpp -- motores NAM A2 da tone-3000 (github.com/tone-3000/embedded, MIT), portados para
// ARMv7 NEON, expostos como nam::DSP e escolhidos em tempo de execucao contra o caminho A2
// original do NeuralAmpModelerCore (A2FastModel).
//
// Regra de seguranca: o motor novo so e usado se, NESTE aparelho, (1) produzir a mesma saida que
// o motor original para os mesmos pesos e (2) for mais rapido. Qualquer falha -> motor original.
//
// Variaveis de ambiente (so para teste): NAM_A2_ENGINE=auto|core|fma|mla (padrao auto).
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <vector>
#include <unistd.h>

#include "NAM/dsp.h"
#include "NAM/model_config.h"
#include "NAM/wavenet/a2_fast.h"
#include "json.hpp"

extern "C" {
#include "nam_a2lite.h"
#include "nam_a2full.h"
// As duas variantes de cada motor (mesmo fonte, simbolos renomeados no build):
#define T3K_DECL(P, M, m)                                                                                     \
  void P##nam_##m##_init(nam_##m##_t*, const nam_##m##_weights_t*, nam_##m##_state_t*);                       \
  void P##nam_##m##_reset(nam_##m##_t*);                                                                      \
  void P##nam_##m##_process(nam_##m##_t*, const float* const*, float* const*, int);                           \
  int P##nam_##m##_load_weights(nam_##m##_weights_t*, const float*, int);
T3K_DECL(fma_, A2LITE, a2lite)
T3K_DECL(fma_, A2FULL, a2full)
T3K_DECL(mla_, A2LITE, a2lite)
T3K_DECL(mla_, A2FULL, a2full)
}

// ---------------------------------------------------------------------------------------------
// Registro: stderr (journal do aparelho) + /tmp/nam_a2_report.txt (tmpfs, nunca o drive USB).
// ---------------------------------------------------------------------------------------------
extern "C" void nam_a2_log(const char* fmt, ...)
{
  char line[512];
  va_list ap;
  va_start(ap, fmt);
  vsnprintf(line, sizeof(line), fmt, ap);
  va_end(ap);
  fprintf(stderr, "[nam_a2] %s\n", line);
  static std::mutex m;
  std::lock_guard<std::mutex> lock(m);
  const char* path = std::getenv("NAM_A2_REPORT");
  if (!path)
    path = "/tmp/nam_a2_report.txt";
  if (FILE* f = fopen(path, "a"))
  {
    if (ftell(f) < 256 * 1024) // teto de tamanho
      fprintf(f, "%s\n", line);
    fclose(f);
  }
}

namespace
{
constexpr int kChunk = 48; // tamanho de bloco do aparelho; os motores foram gerados para 48

#define T3K_TRAITS(Name, P, M, m)                                                                             \
  struct Name                                                                                                 \
  {                                                                                                           \
    using W = nam_##m##_weights_t;                                                                            \
    using S = nam_##m##_state_t;                                                                              \
    using I = nam_##m##_t;                                                                                    \
    static constexpr int kPrewarm = NAM_##M##_PREWARM_SAMPLES;                                                \
    static constexpr int kMax = NAM_##M##_MAX_BUFFER_SIZE;                                                    \
    static int load(W* d, const float* w, int n) { return P##nam_##m##_load_weights(d, w, n); }               \
    static void init(I* i, const W* w, S* s) { P##nam_##m##_init(i, w, s); }                                  \
    static void reset(I* i) { P##nam_##m##_reset(i); }                                                        \
    static void process(I* i, const float* const* in, float* const* out, int n)                               \
    {                                                                                                         \
      P##nam_##m##_process(i, in, out, n);                                                                    \
    }                                                                                                         \
  };
T3K_TRAITS(LiteFma, fma_, A2LITE, a2lite)
T3K_TRAITS(FullFma, fma_, A2FULL, a2full)
T3K_TRAITS(LiteMla, mla_, A2LITE, a2lite)
T3K_TRAITS(FullMla, mla_, A2FULL, a2full)

template <class T>
class T3kA2Model : public nam::DSP
{
  static_assert(kChunk <= T::kMax, "bloco maior que o maximo do motor");

public:
  T3kA2Model(const std::vector<float>& weights, double sr)
  : nam::DSP(1, 1, sr)
  , _w(new typename T::W)
  , _s(new typename T::S)
  , _i(new typename T::I)
  {
    if (T::load(_w.get(), weights.data(), static_cast<int>(weights.size())) != 0)
      throw std::runtime_error("t3k: numero de pesos nao corresponde ao motor A2");
    T::init(_i.get(), _w.get(), _s.get());
  }

  void process(NAM_SAMPLE** input, NAM_SAMPLE** output, const int num_frames) override
  {
    const float* in = input[0];
    float* out = output[0];
    for (int off = 0; off < num_frames;)
    {
      const int k = std::min(kChunk, num_frames - off);
      // O motor exige entrada e saida sem sobreposicao: passa por buffers proprios.
      std::memcpy(_in, in + off, static_cast<size_t>(k) * sizeof(float));
      const float* ip = _in;
      float* op = _out;
      T::process(_i.get(), &ip, &op, k);
      std::memcpy(out + off, _out, static_cast<size_t>(k) * sizeof(float));
      off += k;
    }
  }

  int GetPrewarmSamples() override { return T::kPrewarm; }

protected:
  // Igual ao A2FastModel: (re)definir o tamanho de buffer zera o historico; o prewarm vem depois
  // (DSP::Reset -> SetMaxBufferSize -> prewarm()).
  void SetMaxBufferSize(const int maxBufferSize) override
  {
    nam::DSP::SetMaxBufferSize(maxBufferSize);
    T::reset(_i.get());
  }

private:
  std::unique_ptr<typename T::W> _w;
  std::unique_ptr<typename T::S> _s;
  std::unique_ptr<typename T::I> _i;
  float _in[kChunk];
  float _out[kChunk];
};

enum Engine { kCore = 0, kFma = 1, kMla = 2, kNumEngines = 3 };
const char* const kEngineName[kNumEngines] = {"core(lolgab)", "t3k-fma", "t3k-mla"};

std::unique_ptr<nam::DSP> make_t3k(Engine e, int channels, const std::vector<float>& w, double sr)
{
  if (channels == 3)
    return e == kFma ? std::unique_ptr<nam::DSP>(new T3kA2Model<LiteFma>(w, sr))
                     : std::unique_ptr<nam::DSP>(new T3kA2Model<LiteMla>(w, sr));
  return e == kFma ? std::unique_ptr<nam::DSP>(new T3kA2Model<FullFma>(w, sr))
                   : std::unique_ptr<nam::DSP>(new T3kA2Model<FullMla>(w, sr));
}

// Mede os 3 motores com os pesos reais, confere que as saidas coincidem e devolve o mais rapido.
Engine benchmark(int channels, const std::vector<float>& weights, nam::ModelConfig* core, double sr)
{
  constexpr int kRounds = 24;
  std::unique_ptr<nam::DSP> dsp[kNumEngines];
  bool ok[kNumEngines] = {false, false, false};
  for (int e = 0; e < kNumEngines; ++e)
  {
    try
    {
      dsp[e] = e == kCore ? core->create(weights, sr) : make_t3k(static_cast<Engine>(e), channels, weights, sr);
      dsp[e]->Reset(48000.0, kChunk); // zera + prewarm: todos partem do mesmo estado
      ok[e] = true;
    }
    catch (const std::exception& ex)
    {
      nam_a2_log("select ch=%d %s indisponivel: %s", channels, kEngineName[e], ex.what());
    }
    catch (...)
    {
      nam_a2_log("select ch=%d %s indisponivel", channels, kEngineName[e]);
    }
    usleep(500);
  }
  if (!ok[kCore])
    return kCore; // sem referencia nao ha como validar: deixa o caminho original decidir (e falhar, se for o caso)

  float in[kChunk], out[kNumEngines][kChunk];
  double best_us[kNumEngines] = {1e12, 1e12, 1e12};
  double max_err[kNumEngines] = {0, 0, 0}, peak = 1e-9;
  long phase = 0;
  for (int r = 0; r < kRounds; ++r)
  {
    for (int i = 0; i < kChunk; ++i, ++phase)
      in[i] = 0.3f * static_cast<float>(std::sin(2.0 * 3.14159265358979323846 * 220.0 * phase / 48000.0));
    for (int e = 0; e < kNumEngines; ++e)
    {
      if (!ok[e])
        continue;
      float* ip[1] = {in};
      float* op[1] = {out[e]};
      const auto t0 = std::chrono::steady_clock::now();
      dsp[e]->process(ip, op, kChunk);
      const auto t1 = std::chrono::steady_clock::now();
      const double us = std::chrono::duration<double, std::micro>(t1 - t0).count();
      best_us[e] = std::min(best_us[e], us);
      usleep(300); // cede a CPU ao audio entre blocos
    }
    for (int i = 0; i < kChunk; ++i)
    {
      peak = std::max(peak, static_cast<double>(std::fabs(out[kCore][i])));
      for (int e = kFma; e < kNumEngines; ++e)
        if (ok[e])
        {
          const double d = std::fabs(static_cast<double>(out[e][i]) - out[kCore][i]);
          max_err[e] = std::isfinite(d) ? std::max(max_err[e], d) : 1e9;
        }
    }
  }
  Engine pick = kCore;
  for (int e = kFma; e < kNumEngines; ++e)
  {
    if (!ok[e])
      continue;
    const bool same = max_err[e] <= 1e-3 * std::max(peak, 1e-3); // -60 dB do pico; o esperado e ~-130 dB
    nam_a2_log("select ch=%d %s: %.0f us/bloco, erro max %.2e (pico %.3f) %s", channels, kEngineName[e],
               best_us[e], max_err[e], peak, same ? "saida confere" : "SAIDA DIFERENTE -> descartado");
    if (same && best_us[e] < best_us[pick])
      pick = static_cast<Engine>(e);
  }
  nam_a2_log("select ch=%d %s: %.0f us/bloco (referencia)", channels, kEngineName[kCore], best_us[kCore]);
  nam_a2_log("select ch=%d -> %s (%.2fx o original)", channels, kEngineName[pick], best_us[kCore] / best_us[pick]);
  return pick;
}

Engine choose(int channels, const std::vector<float>& weights, nam::ModelConfig* core, double sr)
{
  static std::mutex m;
  static int choice[2] = {-1, -1};
  const int idx = channels == 8 ? 1 : 0;
  std::lock_guard<std::mutex> lock(m);
  if (choice[idx] >= 0)
    return static_cast<Engine>(choice[idx]);
  Engine e = kCore;
  const char* env = std::getenv("NAM_A2_ENGINE");
  const std::string mode = env ? env : "auto";
  if (mode == "core")
    e = kCore;
  else if (mode == "fma")
    e = kFma;
  else if (mode == "mla")
    e = kMla;
  else
    e = benchmark(channels, weights, core, sr);
  choice[idx] = e;
  return e;
}

struct T3kConfig : public nam::ModelConfig
{
  int channels = 0;
  std::unique_ptr<nam::ModelConfig> core; // caminho original (A2FastModel)

  std::unique_ptr<nam::DSP> create(std::vector<float> weights, double sampleRate) override
  {
    Engine e = kCore;
    try
    {
      e = choose(channels, weights, core.get(), sampleRate);
      if (e != kCore)
        return make_t3k(e, channels, weights, sampleRate);
    }
    catch (...)
    {
      // qualquer problema com o motor novo: segue com o original
    }
    return core->create(std::move(weights), sampleRate);
  }
};
} // namespace

namespace nam
{
namespace wavenet
{
namespace t3k
{
// Chamado por wavenet::create_config no lugar de a2_fast::create_a2_fast_config.
std::unique_ptr<nam::ModelConfig> create_config(const nlohmann::json& config, double sampleRate)
{
  auto c = std::make_unique<T3kConfig>();
  if (!nam::wavenet::a2_fast::is_a2_shape(config, &c->channels))
    throw std::runtime_error("t3k: configuracao nao e A2");
  c->core = nam::wavenet::a2_fast::create_a2_fast_config(config, sampleRate);
  return c;
}
} // namespace t3k
} // namespace wavenet
} // namespace nam
