"""v8: NAM em núcleo próprio + carregamento fora do núcleo do áudio + medidor de entrada.
uso (WSL): python3 v8_nucleos.py <build>/patch/nam_hook.cpp   (aplica sobre o hook já com os patches da v7)"""
import sys, re
p = sys.argv[1]
s = open(p).read()


def troca(velho, novo, n=1):
    global s
    c = s.count(velho)
    if c != n:
        sys.exit('trecho %dx (esperado %d): %r' % (c, n, velho[:80]))
    s = s.replace(velho, novo)


# 1) threads de fundo (carregar/preparar modelo, estatísticas) fora do núcleo 1, onde roda o áudio do Evil
troca('''  pthread_t tid;
  if (pthread_create(&tid, nullptr, trampoline, ctx) != 0)
  {
    delete ctx;
    return;
  }
  pthread_detach(tid);''', '''  pthread_t tid;
  pthread_attr_t attr;
  pthread_attr_init(&attr);
  // [mx5-v8] a MX5 tem 4 nucleos: o audio do Evil fica no 1; o trabalho pesado de fundo vai para 0/2/3
  if (sysconf(_SC_NPROCESSORS_ONLN) >= 4)
  {
    cpu_set_t cs;
    CPU_ZERO(&cs);
    CPU_SET(0, &cs); // qualquer nucleo menos o 1 (audio do Evil)
    CPU_SET(2, &cs);
    CPU_SET(3, &cs);
    pthread_attr_setaffinity_np(&attr, sizeof(cs), &cs);
  }
  const int rc = pthread_create(&tid, &attr, trampoline, ctx);
  pthread_attr_destroy(&attr);
  if (rc != 0)
  {
    delete ctx;
    return;
  }
  pthread_detach(tid);''')

# 2) estatísticas: pico de entrada (calibração) e blocos atrasados do núcleo próprio
troca('std::atomic<uint32_t> g_st_mono{0}, g_st_stereo{0}, g_st_ch1{0};\n',
      'std::atomic<uint32_t> g_st_mono{0}, g_st_stereo{0}, g_st_ch1{0};\n'
      'std::atomic<uint32_t> g_in_peak_bits{0}, g_st_late{0}; // [mx5-v8]\n'
      'std::atomic<int> g_off_active{0}, g_off_why{0};\n')
troca('''      const uint32_t ch1 = g_st_ch1.exchange(0);''', '''      const uint32_t ch1 = g_st_ch1.exchange(0);
      const uint32_t pkb = g_in_peak_bits.exchange(0), late = g_st_late.exchange(0);
      float pk;
      std::memcpy(&pk, &pkb, 4);''')
troca('''"mono_colapsado=%u estereo=%u um_canal=%u\\n",''', '''"mono_colapsado=%u estereo=%u um_canal=%u entrada_pico_dbfs=%.1f atrasados_2s=%u nucleo_proprio=%d motivo=%d\\n",''')
troca('''count_claimed_instances(), mono, st, ch1);''',
      '''count_claimed_instances(), mono, st, ch1,
                pk > 0.f ? 20.f * std::log10(pk) : -200.f, late, g_off_active.load(), g_off_why.load());''')

# 3) entrada real vira a versão síncrona; a nova entrada manda o bloco para um núcleo próprio
troca('extern "C" void nam_process_gonk(void* this_, uint32_t param2, float** input, uint32_t numChannels, float** output,\n'
      '                                 int32_t numFrames, uint32_t* flags, void* ctx)\n{\n  if (numFrames <= 0',
      'static void nam_process_gonk_sync(void* this_, uint32_t param2, float** input, uint32_t numChannels, float** output,\n'
      '                                 int32_t numFrames, uint32_t* flags, void* ctx)\n{\n  if (numFrames <= 0')

novo = r'''
// [mx5-v8] NAM num nucleo proprio (2 ou 3). A thread de audio do Evil (nucleo 1) entrega o bloco n e
// devolve o resultado do bloco n-1: +1 bloco de atraso, e o nucleo 1 fica livre para os outros efeitos.
// Desliga com o arquivo nam_nucleos_off.txt na pasta NAM (volta ao processamento no proprio nucleo 1).
namespace
{
constexpr int kOffMaxF = 512;
struct Offload
{
  void* key = nullptr;
  bool ok = false;
  uint32_t nch = 0;
  int32_t nf = 0;
  uint64_t last_ms = 0;
  float in[2][kOffMaxF];
  float out[2][kOffMaxF];
  sem_t go;
  std::atomic<uint32_t> req{0}, done{0};
};
Offload g_off[kMaxInstances];
std::atomic<int> g_off_next{0};

int offload_enabled()
{
  static const int v = []() {
    if (const char* e = std::getenv("NAM_OFFLOAD"))
      return std::atoi(e);
    if (sysconf(_SC_NPROCESSORS_ONLN) < 4)
      return 0;
    std::error_code ec;
    return std::filesystem::exists(model_dir() / "nam_nucleos_off.txt", ec) ? 0 : 1;
  }();
  return v;
}

void* off_worker(void* arg)
{
  auto* o = static_cast<Offload*>(arg);
  flush_denormals_to_zero();
  for (;;)
  {
    while (sem_wait(&o->go) != 0)
    {
    }
    float* ip[2] = {o->in[0], o->in[1]};
    float* op[2] = {o->out[0], o->out[1]};
    nam_process_gonk_sync(o->key, 0, ip, o->nch, op, o->nf, nullptr, nullptr);
    o->done.store(o->req.load(std::memory_order_acquire), std::memory_order_release);
  }
  return nullptr;
}

Offload* off_for(void* key)
{
  for (auto& o : g_off)
    if (o.key == key)
      return o.ok ? &o : nullptr;
  // troca de rig cria instancia nova: reaproveita a thread de uma instancia parada ha mais de 1 s
  const uint64_t now = now_ms();
  for (auto& o : g_off)
    if (o.ok && o.key && o.last_ms && now - o.last_ms > 1000
        && o.req.load(std::memory_order_relaxed) == o.done.load(std::memory_order_acquire))
    {
      o.key = key;
      o.last_ms = 0;
      return &o;
    }
  for (auto& o : g_off)
  {
    if (o.key)
      continue;
    o.key = key;
    sem_init(&o.go, 0, 0);
    pthread_attr_t a;
    pthread_attr_init(&a);
    pthread_attr_setinheritsched(&a, PTHREAD_EXPLICIT_SCHED);
    pthread_attr_setschedpolicy(&a, SCHED_FIFO);
    sched_param sp{};
    sp.sched_priority = 45; // acima dos ajudantes do Evil (40), abaixo do audio (49)
    pthread_attr_setschedparam(&a, &sp);
    cpu_set_t cs;
    CPU_ZERO(&cs);
    CPU_SET(2 + (g_off_next.fetch_add(1) % 2), &cs);
    pthread_attr_setaffinity_np(&a, sizeof(cs), &cs);
    pthread_t t;
    o.ok = pthread_create(&t, &a, off_worker, &o) == 0;
    pthread_attr_destroy(&a);
    if (o.ok)
    {
      pthread_detach(t);
      g_off_active.fetch_add(1);
    }
    else
      o.key = reinterpret_cast<void*>(1); // slot inutilizavel, nao tenta de novo
    nam_a2_log("nucleo proprio: instancia %p %s", key, o.ok ? "ok" : "FALHOU (fica no nucleo do audio)");
    return o.ok ? &o : nullptr;
  }
  return nullptr;
}
} // namespace

extern "C" void nam_process_gonk(void* this_, uint32_t param2, float** input, uint32_t numChannels, float** output,
                                 int32_t numFrames, uint32_t* flags, void* ctx)
{
  if (numFrames > 0 && input && input[0])
  {
    float pk = 0.f;
    for (int32_t i = 0; i < numFrames; ++i)
      pk = std::max(pk, std::fabs(input[0][i]));
    uint32_t b;
    std::memcpy(&b, &pk, 4);
    uint32_t cur = g_in_peak_bits.load(std::memory_order_relaxed);
    while (b > cur && !g_in_peak_bits.compare_exchange_weak(cur, b, std::memory_order_relaxed))
    {
    }
  }
  // o Evil chama com ate 6 canais; como na versao sincrona (kMaxChannels), so os 2 primeiros sao processados
  numChannels = std::min<uint32_t>(numChannels, 2u);
  bool can = offload_enabled() && this_ && input && output && numChannels >= 1 && numFrames > 0
             && numFrames <= kOffMaxF;
  for (uint32_t ch = 0; can && ch < numChannels; ++ch)
    can = input[ch] && output[ch];
  g_off_why.store(!offload_enabled() ? 1 : !can ? 10 + static_cast<int>(numChannels) * 1000 + (numFrames > kOffMaxF ? 100 : 0) : 0,
                  std::memory_order_relaxed);
  Offload* o = can ? off_for(this_) : nullptr;
  if (can && !o)
    g_off_why.store(2, std::memory_order_relaxed);
  if (!o)
  {
    nam_process_gonk_sync(this_, param2, input, numChannels, output, numFrames, flags, ctx);
    return;
  }
  // espera o nucleo proprio terminar o bloco anterior (normalmente ja terminou)
  if (o->req.load(std::memory_order_relaxed) != o->done.load(std::memory_order_acquire))
  {
    const auto t0 = std::chrono::steady_clock::now();
    while (o->req.load(std::memory_order_relaxed) != o->done.load(std::memory_order_acquire)
           && std::chrono::steady_clock::now() - t0 < std::chrono::microseconds(600))
    {
    }
    if (o->req.load(std::memory_order_relaxed) != o->done.load(std::memory_order_acquire))
    {
      g_st_late.fetch_add(1, std::memory_order_relaxed);
      for (uint32_t ch = 0; ch < numChannels; ++ch)
        std::memset(output[ch], 0, static_cast<size_t>(numFrames) * sizeof(float));
      return;
    }
  }
  const uint64_t now = now_ms();
  const bool fresh = o->last_ms == 0 || now - o->last_ms > 50 || o->nch != numChannels || o->nf != numFrames;
  o->last_ms = now;
  const size_t bytes = static_cast<size_t>(numFrames) * sizeof(float);
  float res[2][kOffMaxF];
  for (uint32_t ch = 0; ch < numChannels; ++ch)
  {
    if (fresh)
      std::memset(res[ch], 0, bytes);
    else
      std::memcpy(res[ch], o->out[ch], bytes);
    std::memcpy(o->in[ch], input[ch], bytes);
  }
  o->nch = numChannels;
  o->nf = numFrames;
  o->req.fetch_add(1, std::memory_order_release);
  sem_post(&o->go);
  for (uint32_t ch = 0; ch < numChannels; ++ch)
    std::memcpy(output[ch], res[ch], bytes);
}

static void nam_process_gonk_impl(void* this_, uint32_t /*param2*/, float** input, uint32_t numChannels,
                                  float** output, int32_t numFrames, uint32_t* /*flags*/, void* /*ctx*/)
{'''
troca('''
static void nam_process_gonk_impl(void* this_, uint32_t /*param2*/, float** input, uint32_t numChannels,
                                  float** output, int32_t numFrames, uint32_t* /*flags*/, void* /*ctx*/)
{''', novo)
if '#include <semaphore.h>' not in s:
    s = '#include <semaphore.h>\n#include <sched.h>\n#include <unistd.h>\n#include <cmath>\n' + s
open(p, 'w').write(s)
print('ok v8_nucleos')
