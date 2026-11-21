"""v8.4 (rumo a v9): IR longo = processamento original (primeiras 2048/1024 amostras) + a CAUDA que ele corta.
A cauda (v84_cauda.inc) roda numa thread propria no nucleo 3 (FFTConvolver, MIT, pasta fftconvolver/) e entra somada
na saida com os mesmos filtros, ganho e mix do bloco, lidos do proprio objeto do Evil: bypass +0x2b5; vetor das
amostras em uso +0x2d8/+0x2dc; LoCut (a1,a2,b0,b1,b2) +0x304; HiCut +0x320; ganho +0x334; mix molhado +0x33c.
O arquivo e reconhecido pelo CONTEUDO (amostras em uso x inicio de cada .wav da pasta de IRs). Arquivo fora de 48 kHz:
interpolacao linear, igual ao Evil.
Nivel automatico: o som com IR e multiplicado por 1/raiz(energia do arquivo), para Gain 0 dB = mesmo volume medio
com ou sem IR (os arquivos costumam ter +7 a +20 dB e estouravam). Comparar sem reiniciar: criar /tmp/ir_original.
uso (WSL): python3 v84_ir.py <build>/patch/nam_hook.cpp   (aplica depois de v83_drop.py)

Classe EvilDSPs::IRLoader: vtable 0x15e852c; o processamento entra pelo slot 7 (0x16d440), com a mesma
assinatura dos pedais. O original usa so as primeiras 2048 (ou 1024) amostras do arquivo, sem escala.
Autoteste: /tmp/ir_test_in.f32 -> passa pelo processamento ORIGINAL do primeiro IR ativo e grava
/tmp/ir_test_nat.f32 (saida muda enquanto isso)."""
import sys

import os
p = sys.argv[1]
CAUDA = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'v84_cauda.inc'), encoding='utf-8').read()
s = open(p, encoding='utf-8').read()
if 'namespace irl' in s:
    sys.exit('v84: ja aplicado')
s += r'''

// ---------------------------------------------------------------------------------------
@@CAUDA@@
namespace irl
{
constexpr uintptr_t kVtable = 0x15e852c;
constexpr int kSlot = 7;
constexpr uint32_t kOrigProcess = 0x16d440;
Fn g_orig = nullptr;
std::atomic<void*> g_seen[8];
std::atomic<int> g_test{0}; // 0 parado, 1 carregado, 2 rodando, 3 terminou
std::vector<float> g_tin, g_tnat;
uint32_t g_tsel = 0; // canal gravado no autoteste (arquivo /tmp/ir_test_ch com o numero)
size_t g_tpos = 0;
std::atomic<void*> g_test_obj{nullptr};
double g_te[6] = {0, 0, 0, 0, 0, 0};
uint32_t g_tflags = 0, g_tnch = 0;

void process(void* this_, uint32_t p2, float** in, uint32_t nch, float** out, int32_t nf, uint32_t* flags, void* ctx)
{
  bool known = false;
  for (auto& k : g_seen)
    if (k.load(std::memory_order_relaxed) == this_) { known = true; break; }
  if (!known)
    for (auto& k : g_seen)
    {
      void* e = nullptr;
      if (k.compare_exchange_strong(e, this_)) { nam_a2_log("ir: instancia %p (canais %u, quadros %d)", this_, nch, nf); break; }
    }
  int tst = g_test.load(std::memory_order_relaxed);
  if (tst == 1 && in && out && nch >= 1 && nf > 0 && nf <= 1024)
  {
    void* e = nullptr;
    if (g_test_obj.compare_exchange_strong(e, this_)) { g_test.store(2); tst = 2; }
  }
  if (tst == 2 && g_test_obj.load() == this_ && in && out && nch >= 1 && nf > 0 && nf <= 1024)
  {
    const size_t bytes = static_cast<size_t>(nf) * sizeof(float);
    if (g_tpos + static_cast<size_t>(nf) > g_tin.size())
    {
      nam_a2_log("ir: teste fim; canais %u, flags %x, energia por canal %.3g %.3g %.3g %.3g %.3g %.3g", g_tnch, g_tflags,
                 g_te[0], g_te[1], g_te[2], g_te[3], g_te[4], g_te[5]);
      for (auto& v : g_te) v = 0;
      g_test.store(3);
      g_test_obj.store(nullptr);
    }
    else
    {
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
      core(this_, p2, ip, nn, op, nf, flags, ctx);
      g_tnch = nch; g_tflags = flags ? *flags : 0xffffffffu;
      for (uint32_t c = 0; c < nn; ++c)
        for (int32_t i = 0; i < nf; ++i)
          g_te[c] += static_cast<double>(tb_out[c][i]) * tb_out[c][i];
      // grava o canal com mais energia fora do instante do impulso (a convolucao), senao o canal 0
      std::memcpy(&g_tnat[g_tpos], tb_out[g_tsel < nn ? g_tsel : 0], bytes);
      g_tpos += static_cast<size_t>(nf);
      for (uint32_t c = 0; c < nch; ++c)
        if (out[c])
          std::memset(out[c], 0, bytes);
      return;
    }
  }
  if (tst == 4 && in && out && in[0] && out[0] && nf > 0 && nf <= 1024 && g_tpos + static_cast<size_t>(nf) <= g_tin.size())
  { // escuta: entrada e saida reais do bloco
    void* e = nullptr;
    g_test_obj.compare_exchange_strong(e, this_);
    if (g_test_obj.load() == this_)
    {
      const size_t bytes = static_cast<size_t>(nf) * sizeof(float);
      std::memcpy(&g_tin[g_tpos], in[0], bytes);
      core(this_, p2, in, nch, out, nf, flags, ctx);
      std::memcpy(&g_tnat[g_tpos], out[0], bytes);
      g_tpos += static_cast<size_t>(nf);
      if (g_tpos + 1024 > g_tin.size())
      {
        g_test.store(5);
        g_test_obj.store(nullptr);
      }
      return;
    }
  }
  core(this_, p2, in, nch, out, nf, flags, ctx);
}

void watcher()
{
  spawn_detached([]() {
    lower_background_thread_priority();
    for (;;)
    {
      sleep(1);
      if (access("/tmp/ir_original", F_OK) == 0)
      { // comparacao A/B: desliga a cauda sem reiniciar
        for (auto& T : g_tail)
        {
          T.ready.store(false);
          T.norm.store(1.f);
          T.sig = 0;
        }
      }
      else
        for (auto& T : g_tail)
          refresh(T);
      static uint32_t last_under = 0;
      uint32_t u = 0;
      for (auto& T : g_tail)
        u += T.under.load();
      if (u != last_under)
      {
        nam_a2_log("ir: cauda atrasada em %u blocos (total)", u);
        last_under = u;
      }
      if (g_test.load() == 0 && access("/tmp/ir_test_in.f32", R_OK) == 0)
      {
        if (FILE* f = std::fopen("/tmp/ir_test_in.f32", "rb"))
        {
          std::fseek(f, 0, SEEK_END);
          const long n = std::ftell(f) / 4;
          std::fseek(f, 0, SEEK_SET);
          if (n > 0 && n < 48000 * 60)
          {
            g_tin.assign(static_cast<size_t>(n), 0.f);
            g_tnat.assign(static_cast<size_t>(n), 0.f);
            if (std::fread(g_tin.data(), 4, static_cast<size_t>(n), f) == static_cast<size_t>(n))
            {
              g_tpos = 0;
              g_test.store(1);
            }
          }
          std::fclose(f);
        }
        g_tsel = 0;
        if (FILE* fc = std::fopen("/tmp/ir_test_ch", "r"))
        {
          unsigned v = 0;
          if (std::fscanf(fc, "%u", &v) == 1 && v < 6) g_tsel = v;
          std::fclose(fc);
        }
        std::remove("/tmp/ir_test_in.f32");
      }
      else if (g_test.load() == 0 && access("/tmp/ir_tap", F_OK) == 0)
      {
        std::remove("/tmp/ir_tap");
        g_tin.assign(48000 * 6, 0.f);
        g_tnat.assign(48000 * 6, 0.f);
        g_tpos = 0;
        g_test.store(4);
      }
      else if (g_test.load() == 5)
      {
        if (FILE* f = std::fopen("/tmp/ir_tap_in.f32", "wb")) { std::fwrite(g_tin.data(), 4, g_tin.size(), f); std::fclose(f); }
        if (FILE* f = std::fopen("/tmp/ir_tap_out.tmp", "wb")) { std::fwrite(g_tnat.data(), 4, g_tnat.size(), f); std::fclose(f); std::rename("/tmp/ir_tap_out.tmp", "/tmp/ir_tap_out.f32"); }
        g_test.store(0);
      }
      else if (g_test.load() == 3)
      {
        if (FILE* f = std::fopen("/tmp/ir_test_nat.tmp", "wb"))
        {
          std::fwrite(g_tnat.data(), 4, g_tnat.size(), f);
          std::fclose(f);
          std::rename("/tmp/ir_test_nat.tmp", "/tmp/ir_test_nat.f32");
        }
        g_test.store(0);
      }
    }
  });
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
  if (std::filesystem::exists(model_dir() / "nam_ir_off.txt", ec))
  {
    nam_a2_log("ir: desligado (nam_ir_off.txt), fica o original");
    return;
  }
  uint32_t w[16] = {0};
  const int fd = open("/proc/self/mem", O_RDONLY);
  if (fd < 0)
    return;
  const ssize_t r = pread(fd, w, sizeof w, static_cast<off_t>(kVtable));
  close(fd);
  if (r != static_cast<ssize_t>(sizeof w) || w[kSlot] != kOrigProcess || w[2] != 0x6e218 || w[13] != 0x44073c)
  {
    nam_a2_log("ir: tabela do IRLoader diferente do esperado (%x), fica o original", w[kSlot]);
    return;
  }
  const long pg = sysconf(_SC_PAGESIZE);
  void* page = reinterpret_cast<void*>(kVtable & ~static_cast<uintptr_t>(pg - 1));
  if (mprotect(page, static_cast<size_t>(pg), PROT_READ | PROT_WRITE) != 0)
  {
    nam_a2_log("ir: mprotect falhou, fica o original");
    return;
  }
  g_orig = reinterpret_cast<Fn>(static_cast<uintptr_t>(w[kSlot]));
  reinterpret_cast<uint32_t*>(kVtable)[kSlot] = static_cast<uint32_t>(reinterpret_cast<uintptr_t>(&process));
  mprotect(page, static_cast<size_t>(pg), PROT_READ | PROT_EXEC);
  start_worker();
  watcher();
  nam_a2_log("ir: desvio do IRLoader instalado");
}
} // namespace irl
'''
s = s.replace('@@CAUDA@@', CAUDA)
open(p, 'w', encoding='utf-8').write(s)
print('ok v84_ir')
