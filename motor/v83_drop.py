"""v8.3: Drop Tune proprio para baixo ("Drop Starcz") no pedal "Drop Tune"; o SEGUNDO Drop Tune do mesmo rig ("Drop Tune 2")
fica com o original, para comparar. (No MX5 o "... 2" nao e um pedal a parte: e a segunda copia do mesmo pedal no rig,
entao so da para escolher o "Drop Tune" no menu.)
Os dois pedais usam a mesma classe no Evil; a instancia e reconhecida pelo nome guardado no involucro
(vtable 0x17da344, ponteiro para o motor em +0x270, objeto do nome em +0x27c com std::string em +0x14).
Forcar o original em tudo, sem reiniciar: criar o arquivo /tmp/drop_original (apagar para voltar).
uso (WSL): python3 v83_drop.py <build>/patch/nam_hook.cpp   (aplica por ultimo; precisa de drop_tune.h ao lado)

O algoritmo (drop_tune.h) toca a entrada mais devagar e pula um periodo inteiro da nota quando o atraso
passa de um periodo; em cada ataque o leitor volta para junto da entrada (ataque com ~2 ms, sem emenda).
Entra trocando, na memoria, a funcao de processamento (slot 8) da tabela virtual do Drop Tune
(0x17e0af0; original 0x2bba00) -- so se os valores conferirem com o Evil esperado.
Custo medido no MX5: ~21 us por bloco de 1000 us (max 138). Desliga com nam_drop_off.txt na pasta NAM.
No Drop Starcz o botao MIX vira TIMBRE (devolve os medios que o drop empurra para baixo e segura o subgrave:
0% cru, 50% corpo do som seco, 100% = maximo de medios); o estalo seco da palhetada entra sempre, natural;
misturar o som seco afinado com o dropado nao faz sentido musical.
Campos do objeto: bypass +0x26b, modo (0 = Down 1 ... 7 = Down 8) byte +0x650, Mix 0..1 +0x654,
Level normalizado +0x668 (0,909 = 0 dB; 66 dB de faixa). Sao os campos escritos pelo ajuste do
parametro; os outros (+0x628, +0x5fc...) so mudam dentro do processamento original, que fica desligado."""
import sys

p = sys.argv[1]
s = open(p, encoding='utf-8').read()
if 'namespace dropt' in s:
    sys.exit('v83: ja aplicado')
s += r'''

// ---------------------------------------------------------------------------------------
// [mx5-v83] Drop Tune proprio (ver drop_tune.h)
#include <sys/mman.h>
#include <fcntl.h>
#include "drop_tune.h"
namespace dropt
{
using Fn = void (*)(void*, uint32_t, float**, uint32_t, float**, int32_t, uint32_t*, void*);
constexpr uintptr_t kVtable = 0x17e0af0;
constexpr uint32_t kOrigProcess = 0x2bba00;
Fn g_orig = nullptr;
std::atomic<uint32_t> g_blocks{0};

struct Inst
{
  std::atomic<void*> key{nullptr};
  DropTune ch[2];
  bool was_off = true;
  float gain = 1.f, mix = 1.f;
  int kind = -1; // 1 = "Drop Tune" (Drop Starcz, algoritmo novo); 0 = "Drop Tune 2" (original)
};

// O involucro do pedal fica logo antes do motor, na mesma alocacao, e aponta para ele em +0x270.
int kind_of(void* this_)
{
  const uint32_t self = static_cast<uint32_t>(reinterpret_cast<uintptr_t>(this_));
  const uint32_t* p = reinterpret_cast<const uint32_t*>(this_);
  for (int k = 1; k <= 0x100; ++k)
  {
    if (p[-k] != self)
      continue;
    const uint32_t* wr = reinterpret_cast<const uint32_t*>(reinterpret_cast<const uint8_t*>(p - k) - 0x270);
    if (reinterpret_cast<const uint32_t*>(this_) - wr > 0x140 || wr[0] != 0x17da344)
      continue;
    const uint32_t q = wr[0x27c / 4]; // objeto do nome: vtable 0x17e0164, std::string em +0x14 (ponteiro) e +0x18 (tamanho)
    if (q < 0x2000000 || (q & 3))
      return 0;
    const uint32_t* qd = reinterpret_cast<const uint32_t*>(static_cast<uintptr_t>(q));
    if (qd[0] != 0x17e0164)
      return 0;
    const uint32_t ptr = qd[5], size = qd[6];
    if (size < 9 || size > 40 || ptr < 0x2000000)
      return 0;
    const char* name = reinterpret_cast<const char*>(static_cast<uintptr_t>(ptr));
    return name[size - 1] == '2' ? 0 : 1; // "Drop Tune" = Drop Starcz; "Drop Tune 2" = original
  }
  return 0;
}
Inst g_inst[6];

// Autoteste (diagnostico): com o arquivo /tmp/drop_test_in.f32 (float32 mono 48 kHz) presente, o pedal
// processa esse sinal no lugar da entrada, grava o resultado em /tmp/drop_test_out.f32 e deixa a
// saida muda enquanto isso. Serve para conferir o pedal no aparelho sem cabo de reamp.
std::atomic<int> g_test{0}; // 0 parado, 1 carregado, 2 rodando, 3 terminou
std::atomic<bool> g_use_orig{false}; // /tmp/drop_original existe: toca o Drop Tune original (comparacao A/B)
std::vector<float> g_tin, g_tout, g_tnat; // entrada, saida do novo, saida do original
size_t g_tpos = 0;
void test_watcher()
{
  spawn_detached([]() {
    lower_background_thread_priority();
    for (;;)
    {
      sleep(1);
      g_use_orig.store(access("/tmp/drop_original", F_OK) == 0, std::memory_order_relaxed);
      if (g_test.load() == 0 && access("/tmp/drop_test_in.f32", R_OK) == 0)
      {
        if (FILE* f = std::fopen("/tmp/drop_test_in.f32", "rb"))
        {
          std::fseek(f, 0, SEEK_END);
          const long n = std::ftell(f) / 4;
          std::fseek(f, 0, SEEK_SET);
          if (n > 0 && n < 48000 * 120)
          {
            g_tin.assign(static_cast<size_t>(n), 0.f);
            g_tout.assign(static_cast<size_t>(n), 0.f);
            g_tnat.assign(static_cast<size_t>(n), 0.f);
            if (std::fread(g_tin.data(), 4, static_cast<size_t>(n), f) == static_cast<size_t>(n))
            {
              g_tpos = 0;
              g_test.store(1);
            }
          }
          std::fclose(f);
        }
        std::remove("/tmp/drop_test_in.f32");
      }
      else if (g_test.load() == 0 && access("/tmp/drop_tap", F_OK) == 0)
      { // escuta: grava 20 s da entrada real do pedal (em drop_test_nat.f32) e da saida (drop_test_out.f32)
        std::remove("/tmp/drop_tap");
        const size_t n = 48000 * 20;
        g_tin.assign(n, 0.f);
        g_tout.assign(n, 0.f);
        g_tnat.assign(n, 0.f);
        g_tpos = 0;
        g_test.store(4);
      }
      else if (g_test.load() == 0 && access("/tmp/drop_inject.f32", R_OK) == 0)
      { // gerador: o Drop Starcz toca este arquivo como se fosse a saida dele (sinal de teste para o resto da cadeia)
        if (FILE* f = std::fopen("/tmp/drop_inject.f32", "rb"))
        {
          std::fseek(f, 0, SEEK_END);
          const long n = std::ftell(f) / 4;
          std::fseek(f, 0, SEEK_SET);
          if (n > 0 && n < 48000 * 120)
          {
            g_tin.assign(static_cast<size_t>(n), 0.f);
            if (std::fread(g_tin.data(), 4, static_cast<size_t>(n), f) == static_cast<size_t>(n))
            {
              g_tpos = 0;
              g_test.store(6);
            }
          }
          std::fclose(f);
        }
        std::remove("/tmp/drop_inject.f32");
      }
      else if (g_test.load() == 3)
      {
        if (FILE* f = std::fopen("/tmp/drop_test_out.tmp", "wb"))
        {
          std::fwrite(g_tout.data(), 4, g_tout.size(), f);
          std::fclose(f);
          if (FILE* f2 = std::fopen("/tmp/drop_test_nat.f32", "wb"))
          {
            std::fwrite(g_tnat.data(), 4, g_tnat.size(), f2);
            std::fclose(f2);
          }
          std::rename("/tmp/drop_test_out.tmp", "/tmp/drop_test_out.f32");
        }
        g_test.store(0);
      }
    }
  });
}

// TIMBRE: 0% = drop cru, 50% = corpo do som seco (neutro), 100% = +6 dB de medios (os presets de fabrica do pedal vem em 100%)
inline float tone_of(float mix) { return mix * 2.f; }

Inst* inst_for(void* key)
{
  for (auto& i : g_inst)
    if (i.key.load(std::memory_order_relaxed) == key)
      return &i;
  for (auto& i : g_inst)
  {
    void* e = nullptr;
    if (i.key.compare_exchange_strong(e, key))
      return &i;
  }
  return nullptr;
}

void process(void* this_, uint32_t p2, float** in, uint32_t nch, float** out, int32_t nf, uint32_t* flags, void* ctx)
{
  const uint8_t* m = reinterpret_cast<const uint8_t*>(this_);
  Inst* I = (this_ && in && out && nch >= 1 && nf > 0 && nf <= 1024 && in[0] && out[0]) ? inst_for(this_) : nullptr;
  if (I && I->kind < 0)
  {
    I->kind = kind_of(this_);
    nam_a2_log("drop: instancia %p = %s", this_, I->kind == 1 ? "Drop Starcz (Drop Tune)" : "Drop original (Drop Tune 2)");
  }
  if (!I || I->kind != 1 || m[0x26b] != 0 || (g_use_orig.load(std::memory_order_relaxed) && g_test.load(std::memory_order_relaxed) == 0))
  { // desligado ou caso inesperado: comportamento original
    if (I)
      I->was_off = true;
    g_orig(this_, p2, in, nch, out, nf, flags, ctx);
    return;
  }
  flush_denormals_to_zero();
  const int mode = std::min<int>(m[0x650], 11);
  const float semis = -static_cast<float>(mode + 1);
  float mix_t, lvl;
  std::memcpy(&mix_t, m + 0x654, 4);
  std::memcpy(&lvl, m + 0x668, 4);
  mix_t = std::clamp(mix_t, 0.f, 1.f);
  const float gain_t = lvl <= 0.001f ? 0.f : std::pow(10.f, (std::clamp(lvl, 0.f, 1.f) * 66.f - 60.f) / 20.f);
  if (I->was_off)
  {
    I->ch[0].reset();
    I->ch[1].reset();
    I->gain = gain_t;
    I->mix = mix_t;
    I->was_off = false;
  }
  const uint32_t n2 = std::min<uint32_t>(nch, 2u);
  const size_t bytes = static_cast<size_t>(nf) * sizeof(float);
  const bool same = n2 == 2 && in[1] && out[1] && (in[0] == in[1] || std::memcmp(in[0], in[1], bytes) == 0);
  float wet[1024];
  int tst = g_test.load(std::memory_order_relaxed);
  if (tst == 1)
  {
    I->ch[0].reset();
    g_test.store(2);
    tst = 2;
  }
  if (tst == 6)
  {
    if (g_tpos + static_cast<size_t>(nf) > g_tin.size())
      g_test.store(0);
    else
    {
      for (uint32_t c = 0; c < nch; ++c)
        if (out[c])
        {
          if (c < 2) std::memcpy(out[c], &g_tin[g_tpos], bytes);
          else std::memset(out[c], 0, bytes);
        }
      g_tpos += static_cast<size_t>(nf);
      return;
    }
  }
  if (tst == 2)
  {
    if (g_tpos + static_cast<size_t>(nf) > g_tin.size())
      g_test.store(3);
    else
    {
      I->ch[0].set_semitones(semis);
      I->ch[0].punch = 1.f;
      I->ch[0].set_tone(tone_of(mix_t));
      I->ch[0].process(&g_tin[g_tpos], wet, nf);
      for (int32_t i = 0; i < nf; ++i)
        g_tout[g_tpos + i] = wet[i] * gain_t;
      { // o original com o mesmo sinal, em buffers proprios
        static float tb_in[6][1024], tb_out[6][1024];
        float* ip[6];
        float* op[6];
        const uint32_t nn = std::min<uint32_t>(nch, 6u);
        for (uint32_t c = 0; c < nn; ++c)
        {
          std::memcpy(tb_in[c], &g_tin[g_tpos], bytes);
          std::memset(tb_out[c], 0, bytes);
          ip[c] = tb_in[c];
          op[c] = tb_out[c];
        }
        g_orig(this_, p2, ip, nn, op, nf, flags, ctx);
        std::memcpy(&g_tnat[g_tpos], tb_out[0], bytes);
      }
      g_tpos += static_cast<size_t>(nf);
      for (uint32_t c = 0; c < nch; ++c)
        if (out[c])
          std::memset(out[c], 0, bytes);
      return;
    }
  }
  const float g0 = I->gain, dg = (gain_t - g0) / nf;
  for (uint32_t c = 0; c < n2; ++c)
  {
    if (!in[c] || !out[c])
      continue;
    if (c == 1 && same)
    {
      if (out[1] != out[0])
        std::memcpy(out[1], out[0], bytes);
      continue;
    }
    I->ch[c].set_semitones(semis);
    I->ch[c].punch = 1.f;            // estalo seco da palhetada, natural
    I->ch[c].set_tone(tone_of(mix_t)); // o botao MIX vira TIMBRE
    const bool tap = c == 0 && tst == 4 && g_tpos + static_cast<size_t>(nf) <= g_tnat.size();
    if (tap)
      std::memcpy(&g_tnat[g_tpos], in[0], bytes);
    I->ch[c].process(in[c], wet, nf);
    float g = g0;
    for (int32_t i = 0; i < nf; ++i)
    {
      out[c][i] = wet[i] * g;
      g += dg;
    }
    if (tap)
    {
      std::memcpy(&g_tout[g_tpos], out[0], bytes);
      g_tpos += static_cast<size_t>(nf);
      if (g_tpos + 1024 > g_tnat.size())
        g_test.store(3);
    }
  }
  I->gain = gain_t;
  I->mix = mix_t;
  for (uint32_t c = 2; c < nch; ++c)
    if (in[c] && out[c] && in[c] != out[c])
      std::memcpy(out[c], in[c], bytes);
  g_blocks.fetch_add(1, std::memory_order_relaxed);
}

__attribute__((constructor)) void install()
{
  char exe[256];
  const ssize_t n = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
  if (n <= 0)
    return;
  exe[n] = 0;
  if (std::strcmp(exe, "/usr/Evil/Evil") != 0)
    return;
  std::error_code ec;
  if (std::filesystem::exists(model_dir() / "nam_drop_off.txt", ec))
  {
    nam_a2_log("drop: desligado (nam_drop_off.txt), fica o original");
    return;
  }
  uint32_t w[16] = {0};
  const int fd = open("/proc/self/mem", O_RDONLY);
  if (fd < 0)
    return;
  const ssize_t r = pread(fd, w, sizeof w, static_cast<off_t>(kVtable));
  close(fd);
  if (r != static_cast<ssize_t>(sizeof w) || w[8] != kOrigProcess || w[2] != 0x6e218 || w[13] != 0x44073c)
  {
    nam_a2_log("drop: tabela do Drop Tune diferente do esperado (%x), fica o original", w[8]);
    return;
  }
  const long pg = sysconf(_SC_PAGESIZE);
  void* page = reinterpret_cast<void*>(kVtable & ~static_cast<uintptr_t>(pg - 1));
  if (mprotect(page, static_cast<size_t>(pg), PROT_READ | PROT_WRITE) != 0)
  {
    nam_a2_log("drop: mprotect falhou, fica o original");
    return;
  }
  g_orig = reinterpret_cast<Fn>(static_cast<uintptr_t>(w[8]));
  reinterpret_cast<uint32_t*>(kVtable)[8] = static_cast<uint32_t>(reinterpret_cast<uintptr_t>(&process));
  mprotect(page, static_cast<size_t>(pg), PROT_READ | PROT_EXEC); // a pagina fica no segmento r-x do Evil
  test_watcher();
  nam_a2_log("drop: Drop Tune proprio instalado");
}
} // namespace dropt
'''
open(p, 'w', encoding='utf-8').write(s)
print('ok v83_drop')
