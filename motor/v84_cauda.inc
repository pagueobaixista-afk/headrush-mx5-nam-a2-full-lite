// [mx5-v84] IR longo
#include <semaphore.h>
#include "fftconvolver/FFTConvolver.h"
#include "fftconvolver/TwoStageFFTConvolver.h"
namespace irl
{
constexpr int kR = 16384, kM = kR - 1;
constexpr const char* kIrDir = "/media/az01-internal/Evil/usb_mnt/Impulse Responses";
using Fn = void (*)(void*, uint32_t, float**, uint32_t, float**, int32_t, uint32_t*, void*);
extern Fn g_orig;

struct Conv
{ // cauda curta: particao uniforme; cauda longa: dois estagios
  fftconvolver::FFTConvolver u;
  fftconvolver::TwoStageFFTConvolver t2;
  bool two = false;
  bool init(int B, const float* h, size_t n)
  {
    two = n > 16384;
    return two ? t2.init(static_cast<size_t>(B), 4096, h, n) : u.init(static_cast<size_t>(B), h, n);
  }
  void run(const float* in, float* out, int n)
  {
    if (two)
      t2.process(in, out, static_cast<size_t>(n));
    else
      u.process(in, out, static_cast<size_t>(n));
  }
};

struct Tail
{
  std::atomic<void*> key{nullptr};
  float in[2][kR], out[2][kR];
  std::atomic<uint64_t> wpos{0}, done{0}, start{0};
  std::atomic<bool> ready{false};
  std::atomic<int> nch{1};
  std::mutex mx; // thread da cauda x thread que carrega
  std::unique_ptr<Conv> cv[2];
  int B = 512, N = 2048;
  uint32_t sig = 0;
  size_t tail_len = 0;
  float zl[2][4] = {{0}}, zh[2][4] = {{0}}; // estados dos filtros (so a thread de audio)
  std::atomic<uint32_t> under{0};
  // nivel automatico: 1/raiz(energia do arquivo). Com Gain em 0 dB o bloco fica com o mesmo volume medio do som sem IR.
  std::atomic<float> norm{1.f};
};
Tail g_tail[8];
sem_t g_sem;
std::atomic<bool> g_worker_on{false};

Tail* tail_for(void* key)
{
  for (auto& t : g_tail)
    if (t.key.load(std::memory_order_relaxed) == key)
      return &t;
  for (auto& t : g_tail)
  {
    void* e = nullptr;
    if (t.key.compare_exchange_strong(e, key))
      return &t;
  }
  return nullptr;
}

struct IrFile
{
  std::string path;
  int rate = 0, ch = 0, bits = 0, fmt = 0;
  long data_off = 0, frames = 0;
  long frames48 = 0; // tamanho depois de convertido para 48 kHz
  float head[128];
};
std::vector<IrFile> g_files;

bool wav_open(const std::string& path, IrFile& f, FILE*& fp)
{
  fp = std::fopen(path.c_str(), "rb");
  if (!fp)
    return false;
  uint8_t hd[12];
  if (std::fread(hd, 1, 12, fp) != 12 || std::memcmp(hd, "RIFF", 4) || std::memcmp(hd + 8, "WAVE", 4))
    return false;
  bool have_fmt = false;
  for (;;)
  {
    uint8_t ck[8];
    if (std::fread(ck, 1, 8, fp) != 8)
      return false;
    const uint32_t len = ck[4] | (ck[5] << 8) | (ck[6] << 16) | (static_cast<uint32_t>(ck[7]) << 24);
    if (!std::memcmp(ck, "fmt ", 4))
    {
      uint8_t b[40] = {0};
      const size_t want = std::min<size_t>(len, sizeof b);
      if (std::fread(b, 1, want, fp) != want)
        return false;
      f.fmt = b[0] | (b[1] << 8);
      f.ch = b[2] | (b[3] << 8);
      f.rate = b[4] | (b[5] << 8) | (b[6] << 16) | (b[7] << 24);
      f.bits = b[14] | (b[15] << 8);
      if (f.fmt == 0xfffe && want >= 26)
        f.fmt = b[24] | (b[25] << 8);
      if (len > want)
        std::fseek(fp, static_cast<long>(len - want), SEEK_CUR);
      have_fmt = true;
    }
    else if (!std::memcmp(ck, "data", 4))
    {
      if (!have_fmt || f.ch < 1 || f.ch > 8)
        return false;
      f.data_off = std::ftell(fp);
      f.frames = static_cast<long>(len / static_cast<uint32_t>(f.ch * (f.bits / 8)));
      return (f.fmt == 1 && (f.bits == 16 || f.bits == 24 || f.bits == 32)) || (f.fmt == 3 && f.bits == 32);
    }
    else
      std::fseek(fp, static_cast<long>(len + (len & 1)), SEEK_CUR);
  }
}

// le n quadros (canal 0) a partir do quadro `from`
size_t wav_read(FILE* fp, const IrFile& f, long from, float* dst, size_t n)
{
  const int bps = f.bits / 8, fr = bps * f.ch;
  std::fseek(fp, f.data_off + from * fr, SEEK_SET);
  std::vector<uint8_t> raw(static_cast<size_t>(fr) * 4096);
  size_t got = 0;
  while (got < n)
  {
    const size_t want = std::min<size_t>(4096, n - got);
    const size_t r = std::fread(raw.data(), static_cast<size_t>(fr), want, fp);
    for (size_t i = 0; i < r; ++i)
    {
      const uint8_t* q = raw.data() + i * fr;
      float v;
      if (f.fmt == 3)
        std::memcpy(&v, q, 4);
      else if (bps == 2)
        v = static_cast<int16_t>(q[0] | (q[1] << 8)) / 32768.f;
      else if (bps == 3)
        v = static_cast<float>(static_cast<int32_t>((static_cast<uint32_t>(q[0]) << 8) | (static_cast<uint32_t>(q[1]) << 16)
                                                    | (static_cast<uint32_t>(q[2]) << 24)) >> 8) / 8388608.f;
      else
        v = static_cast<float>(static_cast<int32_t>(q[0] | (q[1] << 8) | (q[2] << 16) | (static_cast<uint32_t>(q[3]) << 24))) / 2147483648.f;
      dst[got + i] = v;
    }
    got += r;
    if (r < want)
      break;
  }
  return got;
}

// le n amostras JA EM 48 kHz a partir da posicao `from` (em 48 kHz). Arquivo em outra taxa: interpolacao linear,
// exatamente como o Evil faz ao carregar (medido: amostra i = arquivo na posicao i*taxa/48000).
size_t wav_read48(FILE* fp, const IrFile& f, long from, float* dst, size_t n)
{
  if (f.rate == 48000)
    return wav_read(fp, f, from, dst, n);
  const double ratio = static_cast<double>(f.rate) / 48000.0;
  const long s0 = static_cast<long>(std::floor(from * ratio));
  const long s1 = static_cast<long>(std::floor((from + static_cast<long>(n)) * ratio)) + 2;
  std::vector<float> src(static_cast<size_t>(s1 - s0), 0.f);
  const size_t got = wav_read(fp, f, s0, src.data(), src.size());
  size_t out = 0;
  for (; out < n; ++out)
  {
    const double pos = (from + static_cast<long>(out)) * ratio - static_cast<double>(s0);
    const size_t i0 = static_cast<size_t>(pos);
    if (i0 + 1 >= got)
    {
      if (i0 < got) { dst[out] = src[i0]; ++out; }
      break;
    }
    const float fr = static_cast<float>(pos - static_cast<double>(i0));
    dst[out] = src[i0] + (src[i0 + 1] - src[i0]) * fr;
  }
  return out;
}

void index_files()
{
  g_files.clear();
  std::error_code ec;
  for (auto it = std::filesystem::recursive_directory_iterator(kIrDir, ec);
       !ec && it != std::filesystem::recursive_directory_iterator(); it.increment(ec))
  {
    if (it.depth() > 2 || !it->is_regular_file(ec))
      continue;
    std::string ext = it->path().extension().string();
    for (auto& c : ext)
      c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    if (ext != ".wav")
      continue;
    IrFile f;
    f.path = it->path().string();
    FILE* fp = nullptr;
    if (wav_open(f.path, f, fp) && f.rate >= 8000 && f.rate <= 192000 && f.frames > 1)
    {
      f.frames48 = static_cast<long>((static_cast<double>(f.frames) - 1.0) * 48000.0 / f.rate) + 1;
      std::memset(f.head, 0, sizeof f.head);
      wav_read48(fp, f, 0, f.head, static_cast<size_t>(std::min<long>(128, f.frames48)));
      g_files.push_back(f);
    }
    if (fp)
      std::fclose(fp);
  }
  nam_a2_log("ir: %zu arquivos .wav na pasta de IRs", g_files.size());
}

bool mem_read(uintptr_t addr, void* dst, size_t n)
{ // leitura segura (o Evil pode trocar o vetor enquanto olhamos)
  static const int fd = open("/proc/self/mem", O_RDONLY);
  return fd >= 0 && pread(fd, dst, n, static_cast<off_t>(addr)) == static_cast<ssize_t>(n);
}

// confere um IRLoader: se as amostras em uso mudaram, acha o arquivo e monta a cauda
void refresh(Tail& T)
{
  void* key = T.key.load();
  if (!key)
    return;
  uint32_t vec[2];
  if (!mem_read(reinterpret_cast<uintptr_t>(key) + 0x2d8, vec, 8) || vec[1] <= vec[0])
    return;
  const int N = static_cast<int>((vec[1] - vec[0]) / 4);
  if (N != 1024 && N != 2048)
    return;
  float taps[128];
  if (!mem_read(vec[0], taps, sizeof taps))
    return;
  uint32_t sig = 2166136261u ^ static_cast<uint32_t>(N);
  for (float v : taps)
  {
    uint32_t b;
    std::memcpy(&b, &v, 4);
    sig = (sig ^ b) * 16777619u;
  }
  if (sig == T.sig)
    return;
  T.ready.store(false, std::memory_order_release);
  T.sig = sig;
  if (g_files.empty())
    index_files();
  const IrFile* hit = nullptr;
  for (int pass = 0; pass < 2 && !hit; ++pass)
  {
    for (const auto& f : g_files)
    {
      float worst = 0;
      const int cmp = static_cast<int>(std::min<long>(128, f.frames48));
      for (int k = 1; k < cmp; ++k)
        worst = std::max(worst, std::fabs(f.head[k] - taps[k]));
      if (cmp >= 16 && worst < 2e-4f)
      {
        hit = &f;
        break;
      }
    }
    if (!hit && pass == 0)
      index_files(); // a pasta pode ter mudado
  }
  if (!hit)
  {
    nam_a2_log("ir: %p usa %d amostras de um arquivo que nao achei; fica so o original", key, N);
    return;
  }
  const long total = std::min<long>(hit->frames48, 48000L * 12);
  std::vector<float> all(static_cast<size_t>(total), 0.f);
  IrFile f = *hit;
  FILE* fp = nullptr;
  size_t got_all = 0;
  if (wav_open(f.path, f, fp))
    got_all = wav_read48(fp, f, 0, all.data(), all.size());
  if (fp)
    std::fclose(fp);
  double en = 0;
  for (size_t i = 0; i < got_all; ++i)
    en += static_cast<double>(all[i]) * all[i];
  const float norm = en > 1e-12 ? std::clamp(static_cast<float>(1.0 / std::sqrt(en)), 0.02f, 8.f) : 1.f;
  T.norm.store(norm, std::memory_order_relaxed);
  if (total <= N + 32 || got_all <= static_cast<size_t>(N) + 32)
  {
    nam_a2_log("ir: %p %s cabe inteiro no original (%ld amostras); nivel automatico %+.1f dB", key, hit->path.c_str(),
               hit->frames48, 20.0 * std::log10(norm));
    return;
  }
  std::vector<float> h(all.begin() + N, all.begin() + static_cast<long>(got_all));
  const size_t got = h.size();
  // corta o silencio do fim (abaixo de -100 dB do maior valor da cauda)
  float pk = 0;
  for (size_t i = 0; i < got; ++i)
    pk = std::max(pk, std::fabs(h[i]));
  size_t len = got;
  while (len > 0 && std::fabs(h[len - 1]) < pk * 1e-5f)
    --len;
  if (len < 16 || pk <= 0)
    return;
  const int B = N == 2048 ? 512 : 256;
  std::unique_ptr<Conv> c0(new Conv), c1(new Conv);
  if (!c0->init(B, h.data(), len) || !c1->init(B, h.data(), len))
  {
    nam_a2_log("ir: falha ao montar a cauda de %s", f.path.c_str());
    return;
  }
  {
    std::lock_guard<std::mutex> lk(T.mx);
    T.cv[0] = std::move(c0);
    T.cv[1] = std::move(c1);
    T.B = B;
    T.N = N;
    T.tail_len = len;
    const uint64_t w = T.wpos.load(std::memory_order_acquire);
    const uint64_t al = (w / static_cast<uint64_t>(B)) * static_cast<uint64_t>(B);
    T.done.store(al, std::memory_order_release);
    T.start.store(al, std::memory_order_release);
  }
  T.ready.store(true, std::memory_order_release);
  nam_a2_log("ir: %p cauda longa ligada: %s (%ld amostras em 48 kHz, arquivo de %d Hz; original usa %d; cauda %zu = %.2f s; bloco %d; nivel automatico %+.1f dB)", key,
             f.path.c_str(), hit->frames48, f.rate, N, len, len / 48000.0, B, 20.0 * std::log10(norm));
}

void* worker(void*)
{
  flush_denormals_to_zero();
  static float ib[1024], ob[1024];
  for (;;)
  {
    timespec ts;
    clock_gettime(CLOCK_REALTIME, &ts);
    ts.tv_nsec += 50000000;
    if (ts.tv_nsec >= 1000000000)
    {
      ts.tv_nsec -= 1000000000;
      ++ts.tv_sec;
    }
    sem_timedwait(&g_sem, &ts);
    for (auto& T : g_tail)
    {
      if (!T.ready.load(std::memory_order_acquire) || !T.mx.try_lock())
        continue;
      const int B = T.B, nc = T.nch.load(std::memory_order_relaxed);
      uint64_t d = T.done.load(std::memory_order_relaxed);
      while (T.wpos.load(std::memory_order_acquire) - d >= static_cast<uint64_t>(B))
      {
        for (int c = 0; c < nc && c < 2; ++c)
        {
          for (int i = 0; i < B; ++i)
            ib[i] = T.in[c][(d + static_cast<uint64_t>(i)) & kM];
          T.cv[c]->run(ib, ob, B);
          for (int i = 0; i < B; ++i)
            T.out[c][(d + static_cast<uint64_t>(i)) & kM] = ob[i];
        }
        d += static_cast<uint64_t>(B);
        T.done.store(d, std::memory_order_release);
      }
      T.mx.unlock();
    }
  }
  return nullptr;
}

void start_worker()
{
  sem_init(&g_sem, 0, 0);
  pthread_attr_t a;
  pthread_attr_init(&a);
  pthread_attr_setinheritsched(&a, PTHREAD_EXPLICIT_SCHED);
  pthread_attr_setschedpolicy(&a, SCHED_FIFO);
  sched_param sp{};
  sp.sched_priority = 44; // abaixo do NAM (45) e do audio (49)
  pthread_attr_setschedparam(&a, &sp);
  cpu_set_t cs;
  CPU_ZERO(&cs);
  CPU_SET(3, &cs);
  pthread_attr_setaffinity_np(&a, sizeof(cs), &cs);
  pthread_t th;
  const bool ok = pthread_create(&th, &a, worker, nullptr) == 0;
  pthread_attr_destroy(&a);
  if (ok)
    pthread_detach(th);
  g_worker_on.store(ok);
  nam_a2_log("ir: thread da cauda %s", ok ? "ok (nucleo 3)" : "FALHOU");
}

inline float bq(const float* c, float* z, float x)
{ // c = a1, a2, b0, b1, b2 (como o Evil guarda); z = x1, x2, y1, y2
  const float y = c[2] * x + c[3] * z[0] + c[4] * z[1] - c[0] * z[2] - c[1] * z[3];
  z[1] = z[0];
  z[0] = x;
  z[3] = z[2];
  z[2] = y;
  return y;
}

// original + cauda + nivel automatico, nos buffers dados
void core(void* this_, uint32_t p2, float** in, uint32_t nch, float** out, int32_t nf, uint32_t* flags, void* ctx)
{
  Tail* T = (g_worker_on.load(std::memory_order_relaxed) && in && out && nch >= 1 && nf > 0 && nf <= 1024 && in[0] && out[0])
              ? tail_for(this_) : nullptr;
  const bool tail = T && T->ready.load(std::memory_order_acquire);
  const float norm = T ? T->norm.load(std::memory_order_relaxed) : 1.f;
  if (!T || (!tail && norm == 1.f))
  {
    g_orig(this_, p2, in, nch, out, nf, flags, ctx);
    return;
  }
  const uint8_t* m = reinterpret_cast<const uint8_t*>(this_);
  const size_t bytes = static_cast<size_t>(nf) * sizeof(float);
  const bool two = nch >= 2 && in[1] && out[1] && in[1] != in[0];
  const bool st = two && std::memcmp(in[0], in[1], bytes) != 0;
  const int nc = st ? 2 : 1;
  float dryin[2][1024]; // a entrada pode ser o mesmo buffer da saida
  std::memcpy(dryin[0], in[0], bytes);
  if (st)
    std::memcpy(dryin[1], in[1], bytes);
  const uint64_t w0 = T->wpos.load(std::memory_order_relaxed);
  if (tail)
  {
    for (int c = 0; c < nc; ++c)
      for (int32_t i = 0; i < nf; ++i)
        T->in[c][(w0 + static_cast<uint64_t>(i)) & kM] = dryin[c][i];
    T->nch.store(nc, std::memory_order_relaxed);
    T->wpos.store(w0 + static_cast<uint64_t>(nf), std::memory_order_release);
    if ((w0 / static_cast<uint64_t>(T->B)) != ((w0 + static_cast<uint64_t>(nf)) / static_cast<uint64_t>(T->B)))
      sem_post(&g_sem);
  }
  g_orig(this_, p2, in, nch, out, nf, flags, ctx);
  if (m[0x2b5] != 0)
    return; // bloco desligado
  float coef[10];
  std::memcpy(coef, m + 0x304, 5 * 4);     // LoCut
  std::memcpy(coef + 5, m + 0x320, 5 * 4); // HiCut
  float g, dry, wet;
  std::memcpy(&g, m + 0x334, 4);
  std::memcpy(&dry, m + 0x338, 4);
  std::memcpy(&wet, m + 0x33c, 4);
  const float k = g * wet;
  const uint64_t done = T->done.load(std::memory_order_acquire), start = T->start.load(std::memory_order_acquire);
  const uint64_t lag = static_cast<uint64_t>(T->N) + 1; // o original atrasa 1 amostra
  bool miss = false;
  float add[1024];
  const int outs = two ? 2 : 1;
  for (int c = 0; c < outs; ++c)
  {
    const int sc = st ? c : 0; // mono: a mesma cauda nos dois canais
    if (c == 0 || st)
      for (int32_t i = 0; i < nf; ++i)
      {
        float t = 0.f;
        if (tail)
        {
          const uint64_t n = w0 + static_cast<uint64_t>(i);
          if (n >= lag + start)
          {
            const uint64_t idx = n - lag;
            if (idx < done)
              t = T->out[sc][idx & kM];
            else
              miss = true;
          }
          t = bq(coef + 5, T->zh[sc], bq(coef, T->zl[sc], t)) * k;
        }
        add[i] = t;
      }
    float* o = out[c];
    const float* d = dryin[sc];
    if (norm == 1.f)
      for (int32_t i = 0; i < nf; ++i)
        o[i] += add[i];
    else
      for (int32_t i = 0; i < nf; ++i)
      { // separa o som seco (mix) do som com IR e ajusta so o som com IR
        const float dp = d[i] * dry * g;
        o[i] = dp + (o[i] + add[i] - dp) * norm;
      }
  }
  if (miss)
    T->under.fetch_add(1, std::memory_order_relaxed);
}
} // namespace irl
