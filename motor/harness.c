/* harness.c -- chama nam_process_gonk() do libnam_hook.so como o trampolim do Evil faz:
 * blocos de 48 amostras, processamento no lugar (entrada == saida), knobs nos offsets reais
 * (Drive 0x534, Tone 0x548, Level 0x520, bypass 0x26b).
 *
 * uso: harness <libnam_hook.so> <indice do modelo> <entrada.raw> <saida.raw> [canais=1]
 * Variaveis de ambiente:
 *   H_SAME=1  com 2 canais, R recebe o MESMO sinal de L (guitarra mono)
 *   H_RIGS=n  antes do teste, cria e abandona n instancias (simula trocas de rig)
 *   H_DUAL=1  uma segunda instancia e processada junto (2 pedais NAM no mesmo rig)
 * Espera o modelo carregar (saida != entrada), alimenta 1,5 s de silencio para assentar o
 * estado e o fade, e entao processa a entrada inteira. */
#include <dlfcn.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

typedef void (*gonk_fn)(void*, uint32_t, float**, uint32_t, float**, int32_t, uint32_t*, void*);
enum { N = 48, THIS_SIZE = 0x800 };
static gonk_fn fn;
static uint32_t flags;

static uint8_t* new_this(int idx)
{
  uint8_t* t = calloc(1, THIS_SIZE);
  *(float*)(t + 0x534) = (float)idx / 100.0f; /* Drive: seleciona o modelo */
  *(float*)(t + 0x548) = 0.5f;                /* Tone: entrada em 0 dB */
  *(float*)(t + 0x520) = 0.5f;                /* Level: saida em 0 dB */
  t[0x26b] = 0;                               /* nao esta em bypass */
  t[0x554] = getenv("H_HILO") ? (uint8_t)atoi(getenv("H_HILO")) : 0; /* chave Hi-Lo: 0 Low, 1 High */
  return t;
}

/* espera carregar; devolve 1 se carregou. *first_pt = primeira chamada foi passthrough exato */
static int wait_loaded(uint8_t* t, uint32_t nch, int* first_pt, uint8_t* other)
{
  float bl[N], br[N], ol[N], probe[N];
  float* bufs[2] = {bl, br};
  float* ob[2] = {ol, ol};
  *first_pt = -1;
  for (int tries = 0; tries < 6000; tries++)
  {
    for (int i = 0; i < N; i++) probe[i] = bl[i] = br[i] = 0.25f * sinf(6.2831853f * 220.0f * (float)i / 48000.0f);
    fn(t, 0, bufs, nch, bufs, N, &flags, NULL);
    if (other) { memset(ol, 0, sizeof(ol)); fn(other, 0, ob, 1, ob, N, &flags, NULL); }
    if (*first_pt < 0) *first_pt = memcmp(probe, bl, sizeof(bl)) == 0;
    if (memcmp(probe, bl, sizeof(bl)) != 0) return 1;
    usleep(20 * 1000);
  }
  return 0;
}

int main(int argc, char** argv)
{
  if (argc < 5)
    return 2;
  void* lib = dlopen(argv[1], RTLD_NOW);
  if (!lib) { fprintf(stderr, "dlopen: %s\n", dlerror()); return 1; }
  fn = (gonk_fn)dlsym(lib, "nam_process_gonk");
  if (!fn) { fprintf(stderr, "dlsym: %s\n", dlerror()); return 1; }
  const int idx = atoi(argv[2]);
  const uint32_t nch = argc > 5 ? (uint32_t)atoi(argv[5]) : 1;
  const int same = getenv("H_SAME") != NULL, dual = getenv("H_DUAL") != NULL;
  const int rigs = getenv("H_RIGS") ? atoi(getenv("H_RIGS")) : 0;

  FILE* f = fopen(argv[3], "rb");
  if (!f) { perror(argv[3]); return 1; }
  fseek(f, 0, SEEK_END); long n = ftell(f) / 4; fseek(f, 0, SEEK_SET);
  float* x = malloc((size_t)n * 4); float* y = malloc((size_t)n * 4 * 2);
  if (fread(x, 4, (size_t)n, f) != (size_t)n) return 1;
  fclose(f);

  float bl[N], br[N], ol[N];
  float* bufs[2] = {bl, br};
  float* ob[2] = {ol, ol};
  int pt;
  /* 0) trocas de rig: instancias usadas por um tempo e depois abandonadas */
  for (int r = 0; r < rigs; r++)
  {
    uint8_t* old = new_this(idx);
    int ok = wait_loaded(old, 1, &pt, NULL);
    for (int b = 0; b < 300; b++) { memset(bl, 0, sizeof(bl)); fn(old, 0, bufs, 1, bufs, N, &flags, NULL); if (b % 20 == 0) usleep(1000); }
    printf("  rig descartado %d: carregou=%s\n", r + 1, ok ? "sim" : "NAO");
    usleep(300 * 1000);
  }
  uint8_t* this_ = new_this(idx);
  uint8_t* other = dual ? new_this(idx) : NULL;
  /* 1) espera carregar */
  int loaded = wait_loaded(this_, nch, &pt, other);
  printf("  antes de carregar: passthrough exato=%s | modelo carregou=%s\n", pt ? "sim" : "nao", loaded ? "sim" : "NAO");
  if (!loaded) return 3;
  /* 2) assenta: 1,5 s de silencio (fade-in de 100 ms + campo receptivo do modelo) */
  for (int b = 0; b < 1500; b++)
  {
    memset(bl, 0, sizeof(bl)); memset(br, 0, sizeof(br));
    fn(this_, 0, bufs, nch, bufs, N, &flags, NULL);
    if (other) { memset(ol, 0, sizeof(ol)); fn(other, 0, ob, 1, ob, N, &flags, NULL); }
    if (b % 50 == 0) usleep(1000);
  }
  /* 3) processa a entrada */
  struct timespec t0, t1; clock_gettime(CLOCK_MONOTONIC, &t0);
  int bad = 0;
  const int rt = getenv("H_RT") != NULL; /* compassa em tempo real: 1 bloco por ms */
  const long flip_at = getenv("H_FLIP_AT") ? atol(getenv("H_FLIP_AT")) : -1; /* bloco em que a chave Hi-Lo vira */
  for (long s = 0; s + N <= n; s += N)
  {
    if (s / N == flip_at) this_[0x554] ^= 1;
    if (rt)
    {
      struct timespec now; clock_gettime(CLOCK_MONOTONIC, &now);
      double el = (now.tv_sec - t0.tv_sec) * 1e6 + (now.tv_nsec - t0.tv_nsec) / 1e3, due = (double)(s / N) * 1000.0;
      if (due > el) usleep((useconds_t)(due - el));
    }
    memcpy(bl, x + s, sizeof(bl));
    for (int i = 0; i < N; i++) br[i] = same ? x[s + i] : -0.5f * x[s + i];
    fn(this_, 0, bufs, nch, bufs, N, &flags, NULL);
    if (other) { memcpy(ol, x + s, sizeof(ol)); fn(other, 0, ob, 1, ob, N, &flags, NULL); }
    memcpy(y + s, bl, sizeof(bl));
    memcpy(y + n + s, br, sizeof(br));
    for (int i = 0; i < N; i++) if (!isfinite(bl[i]) || fabsf(bl[i]) > 100.0f) bad = 1;
  }
  clock_gettime(CLOCK_MONOTONIC, &t1);
  const long done = n / N * N;
  double us = ((t1.tv_sec - t0.tv_sec) * 1e9 + (t1.tv_nsec - t0.tv_nsec)) / 1e3 / (double)(done / N);
  printf("  %ld amostras processadas, %.0f us/bloco no emulador, saida valida=%s\n", done, us, bad ? "NAO" : "sim");
  if (getenv("H_TAIL")) sleep(3); /* da tempo de a thread de estatisticas gravar */
  f = fopen(argv[4], "wb");
  fwrite(y, 4, (size_t)done, f);
  if (nch == 2) fwrite(y + n, 4, (size_t)done, f);
  fclose(f);
  return bad ? 4 : 0;
}
