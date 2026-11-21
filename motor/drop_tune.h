// Drop Tune para baixo (monofonico/acordes simples), dominio do tempo, sincrono ao periodo.
// Ideia: tocar a entrada mais devagar (reamostragem pura = timbre de corda afrouxada) e, para nao
// acumular atraso, pular exatamente um periodo da nota quando o atraso passa de um periodo.
// Em cada ataque o leitor volta para junto da entrada: o ataque sai quase sem atraso e sem emenda.
#pragma once
#include <cmath>
#include <cstdint>
#include <cstring>
#include <algorithm>

class DropTune
{
public:
  struct Bq
  {
    float b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0, z1 = 0, z2 = 0;
    inline float run(float x) { const float y = b0 * x + z1; z1 = b1 * x - a1 * y + z2; z2 = b2 * x - a2 * y; return y; }
    void set(double B0, double B1, double B2, double A0, double A1, double A2)
    { b0 = float(B0 / A0); b1 = float(B1 / A0); b2 = float(B2 / A0); a1 = float(A1 / A0); a2 = float(A2 / A0); }
    void peak(float fc, float q, float db)
    {
      const double A = std::pow(10.0, db / 40.0), w = 2 * M_PI * fc / 48000.0, al = std::sin(w) / (2 * q), c = std::cos(w);
      set(1 + al * A, -2 * c, 1 - al * A, 1 + al / A, -2 * c, 1 - al / A);
    }
    void shelf(float fc, float db, bool high)
    {
      const double A = std::pow(10.0, db / 40.0), w = 2 * M_PI * fc / 48000.0, c = std::cos(w), al = std::sin(w) / 2 * std::sqrt(2.0), sq = 2 * std::sqrt(A) * al;
      if (high) set(A * ((A + 1) + (A - 1) * c + sq), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - sq), (A + 1) - (A - 1) * c + sq, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - sq);
      else set(A * ((A + 1) - (A - 1) * c + sq), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - sq), (A + 1) + (A - 1) * c + sq, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - sq);
    }
  };
  static constexpr int kBuf = 16384, kMask = kBuf - 1;
  static constexpr int kTaps = 8, kPhases = 256;

  struct Stats { uint32_t splices = 0, onsets = 0, forced = 0, valleys = 0, aligned = 0; float last_c = 0; int last_L = 0; bool last_forced = false; };
  Stats st;
  // ajustes (amostras a 48 kHz)
  int pre = 96;        // quanto antes do ataque o leitor reposiciona (2 ms)
  int margin = 16;     // atraso minimo
  int W = 576;         // janela de comparacao (12 ms) sobre o sinal filtrado em graves
  int Lmin = 110;      // 436 Hz
  int Dmax = 2400;     // 50 ms: atraso maximo antes de forcar uma emenda
  float thr = 0.80f;
  float thr_lo = 0.85f;
  float match_lp = 0.145f;
  float valley_ratio = 0.22f; // vale = nivel abaixo de 30% (-10 dB) do nivel da frase, com os pulsos parados
  float onset_ratio = 1.8f; // ataque = pico 5 dB acima do pico recente
  float align_min = 0.5f;   // abaixo disso o salto por estalo de agudos vai direto para a entrada
  float hf_energy = 3.0f;   // energia rapida dos agudos 5x a lenta (7 dB)
  float hf_ratio = 2.5f;    // ou estalo de palhetada: agudos (>1,5 kHz) 8 dB acima do pico recente de agudos
  int pk_hold = 2160;       // pico recente fica retido 45 ms (cobre um periodo de 27 Hz)
  int onset_hold = 1920; // 40 ms
  // PUNCH: em cada palhetada soma o estalo original (agudos > 1,5 kHz, sem deslocar e sem atraso) por ~10 ms.
  // O drop toca tudo 26% mais devagar, inclusive o estalo; isto devolve o ataque seco. 0 = desligado, 1 = estalo natural.
  float punch = 0.f;
  // TIMBRE: o drop desloca tambem o "corpo" do som (medido: +3 dB em 80 Hz, -3 a -5 dB em 500-1250 Hz contra o seco).
  // Esta correcao devolve os medios e segura o subgrave. 0 = sem correcao, 1 = corpo do som seco, 2 = dobro.
  void set_tone(float k)
  {
    if (k == tone_k) return;
    tone_k = k;
    eq[0].shelf(120.f, -2.0f * k, false);
    eq[1].peak(650.f, 0.6f, 3.2f * k);
    eq[2].shelf(2500.f, 0.5f * k, true);
  }

  void set_semitones(float s) { ratio = std::pow(2.0, static_cast<double>(s) / 12.0); }
  DropTune() { tab = table(); reset(); set_semitones(-4.f); }
  void reset()
  {
    std::memset(x, 0, sizeof x); std::memset(lp, 0, sizeof lp);
    w = kBuf; rp = w - margin; xf_n = 0; lp1 = lp2 = 0; sub = 0; lo1 = lo2 = sublo = 0; std::memset(lo, 0, sizeof lo); envf = envs = 0; hold = 0; pk = 0; pk_t = 0; pk_lag1 = pk_lag2 = 0; h1 = h2 = hx1 = hx2 = 0; hpk = hpk_lag1 = hpk_lag2 = 0; hpk_t = 0; ck = ck_t = 0; ref = 0; ef = es = 0; efm = efm_lag1 = efm_lag2 = 0; efm_t = 0; since_sig = 0; sp1 = sp2 = hold_len = pk_hold; nl = 0; valley_armed = false; since_on = 0; since_strong = 0; vs1 = vs2 = vs3 = valley_wait = 1920;
    lag_next = Lmin; c_prev = c_prev2 = -1; best_c = -1; best_L = 0; top_c = -1; top_L = 0;
  }

  void process(const float* in, float* out, int n)
  {
    for (int i = 0; i < n; ++i)
    {
      const float s = in[i];
      x[w & kMask] = s;
      // passa-baixas de 2 polos (~300 Hz) para a comparacao
      // faixa de 40 Hz a ~1,2 kHz: com baixo real o sinal so em graves (300 Hz) casava mal (0,5-0,7) por causa
      // do ronco abaixo da nota; nesta faixa o periodo aparece com 0,8-0,9
      lp1 += match_lp * (s - lp1); lp2 += match_lp * (lp1 - lp2);
      sub += 0.0052f * (lp2 - sub);
      lp[w & kMask] = lp2 - sub;
      // segunda opiniao so nos graves (40-300 Hz): num acorde, o periodo de uma das notas casa bem na faixa larga
      // mas mal aqui; so vale a emenda que casa nas duas
      lo1 += 0.0385f * (s - lo1); lo2 += 0.0385f * (lo1 - lo2); sublo += 0.0052f * (lo2 - sublo);
      lo[w & kMask] = lo2 - sublo;
      ++w;
      // envelopes para detectar ataque
      const float a = std::fabs(s);
      envf = a > envf ? a : envf * 0.9931f; // ~3 ms (so para detectar silencio)
      // compara com o pico de 2-4 ms atras (o pico atual sobe junto com o proprio ataque)
      if ((w & 95) == 0) { pk_lag2 = pk_lag1; pk_lag1 = pk; }
      // agudos (2 passa-altas de 1 polo em 1,5 kHz): a palhetada numa corda que ja esta soando quase nao
      // muda o volume, mas da um estalo nos agudos
      const float h1n = 0.822f * (h1 + s - hx1); hx1 = s; h1 = h1n;
      const float h2n = 0.822f * (h2 + h1n - hx2); hx2 = h1n; h2 = h2n;
      const float ah = std::fabs(h2n);
      if ((w & 95) == 0) { hpk_lag2 = hpk_lag1; hpk_lag1 = hpk; }
      // os pisos acompanham o nivel de quem toca (pico dos ultimos segundos), para valer com sinal fraco ou forte
      ref = a > ref ? a : ref * 0.99999f;
      const float lv = ref > 0.003f ? ref : 0.003f;
      const bool amp_on = hold == 0 && a > onset_ratio * pk_lag2 + 0.02f * lv; // subida de volume: ataque certo
      const bool onset = hold == 0 && (a > onset_ratio * pk_lag2 + 0.02f * lv
                                       || ah > hf_ratio * hpk_lag2 + 0.04f * pk + 0.006f * lv
                                       || (ef > hf_energy * efm_lag2 && ef > hf_energy * es && ef > 4e-6f * lv * lv));
      // energia dos agudos: rapida (1,5 ms) contra lenta (60 ms). A palhetada numa corda que ja soa nao muda o
      // volume nem da um pico isolado: e um chiado de ~20 ms, 3x acima do fundo. A lenta sobe junto e evita repetir.
      ef += 0.0138f * (ah * ah - ef);
      es += 0.00035f * (ah * ah - es);
      // Corda grave soando = trem de pulsos, cada pulso com o seu chiado: isso nao e ataque. O chiado novo tem de
      // passar tambem do MAIOR chiado recente (retido pelo intervalo entre pulsos), e nao so da media.
      if ((w & 95) == 0) { efm_lag2 = efm_lag1; efm_lag1 = efm; }
      if (ef >= efm) { efm = ef; efm_t = hold_len + hold_len / 2; }
      else if (efm_t > 0) --efm_t;
      else efm *= 0.9990f;
      if (ah >= hpk) { hpk = ah; hpk_t = hold_len; }
      else if (hpk_t > 0) --hpk_t;
      else hpk *= 0.9990f;
      // O pico recente fica retido so pelo tempo entre dois pulsos da nota (medido), e nao 45 ms fixos:
      // no djent as rajadas abafadas vem a cada 80-100 ms, com 30 ms de pausa, e a retencao longa escondia o ataque seguinte.
      ++since_sig;
      if (a >= 0.6f * pk && since_sig > 144)
      { // novo pulso forte (pelo menos 3 ms depois do anterior)
        sp2 = sp1; sp1 = since_sig < pk_hold ? since_sig : pk_hold; since_sig = 0;
        hold_len = static_cast<int>(1.3f * (sp1 > sp2 ? sp1 : sp2));
        if (hold_len < 288) hold_len = 288;
        if (hold_len > pk_hold) hold_len = pk_hold;
      }
      if (a >= pk) { pk = a; pk_t = hold_len; }
      else if (a >= 0.6f * pk) { if (pk_t < hold_len) pk_t = hold_len; }
      else if (pk_t > 0) --pk_t;
      else pk *= 0.9990f; // solta com ~20 ms
      if (hold > 0) --hold;
      if (since_on < 1000000) ++since_on;
      nl = a > nl ? a : nl * 0.99986f;            // nivel da frase (~150 ms)
      ++since_strong;
      if (a >= 0.5f * nl)
      { // pulso forte da nota: mede o intervalo entre pulsos; "vale" = ficar 1,3x o maior intervalo recente sem pulso
        if (since_strong > 144)
        {
          vs3 = vs2; vs2 = vs1; vs1 = since_strong < 2400 ? since_strong : 2400;
          const int mx = vs1 > vs2 ? (vs1 > vs3 ? vs1 : vs3) : (vs2 > vs3 ? vs2 : vs3);
          valley_wait = static_cast<int>(1.6f * mx);
          if (valley_wait < 384) valley_wait = 384;
          if (valley_wait > 3800) valley_wait = 3800;
        }
        since_strong = 0;
        valley_armed = true;
      }

      double d = static_cast<double>(w) - rp;
      if (xf_n == 0)
      {
        if (onset)
        { // ataque: leitor volta para junto da entrada
          hold = onset_hold; ++st.onsets; ck_t = 1.f; since_on = 0;
          if (d > pre + 48)
          {
            // Ataque so pelos agudos (sem subida de volume) pode ser alarme falso no meio da nota: pular fora de
            // fase da um estalo ("pipoca"). Procura, entre o leitor e a entrada, o ponto onde a onda continua igual;
            // se achar, pula para ele (emenda limpa); se nao achar, a nota mudou mesmo: vai direto para a entrada.
            float cq = 0;
            int back = amp_on ? -1 : continues_at(static_cast<int64_t>(rp), w - pre, &cq);
            if (back >= 0) { start_xfade(static_cast<double>(w - pre - back), cq >= 0.85f ? 96 : 192); ++st.aligned; }
            else start_xfade(static_cast<double>(w) - pre, 72);
          }
          restart_search();
        }
        else if (valley_armed && since_strong > valley_wait && envf < valley_ratio * nl
                 && (since_on < 12000 || pk < 0.4f * nl) // nota longa: so quando os pulsos param de vez
                 && d > margin + 96)
        { // vale: a nota/rajada acabou (os pulsos pararam e o nivel caiu). Reposiciona aqui, onde a emenda
          // fica escondida, para a proxima palhetada ja encontrar o leitor junto da entrada.
          valley_armed = false; ++st.valleys;
          start_xfade(static_cast<double>(w) - margin - 32, 192);
          restart_search();
        }
        else if (envf < 0.001f * lv && d > margin + 64)
        { // silencio: reposiciona sem custo audivel
          start_xfade(static_cast<double>(w) - margin, 48);
          restart_search();
        }
        else if ((w & 15) == 0)
          search_step(d);
      }
      // saida
      float y = interp(rp);
      rp += ratio;
      if (xf_n > 0)
      {
        const float g = static_cast<float>(xf_i) / static_cast<float>(xf_n);
        const float gs = g * g * (3.f - 2.f * g);
        y = y * (1.f - gs) + interp(rp2) * gs;
        rp2 += ratio;
        if (++xf_i >= xf_n) { rp = rp2; xf_n = 0; }
      }
      ck += (ck_t - ck) * 0.12f;  // sobe em ~0,3 ms
      ck_t *= 0.9979f;            // cai com ~10 ms
      y += punch * ck * h2n;
      if (tone_k != 0.f) y = eq[2].run(eq[1].run(eq[0].run(y)));
      out[i] = y;
    }
  }
  double delay_samples() const { return static_cast<double>(w) - rp; }

private:
  float x[kBuf], lp[kBuf];
  typedef float Tab[kTaps];
  const Tab* tab;
  int64_t w; double rp, rp2, ratio; int xf_n, xf_i;
  float lo[kBuf]; float lo1, lo2, sublo;
  float sub; float lp1, lp2, envf, envs, pk, pk_lag1, pk_lag2, h1, h2, hx1, hx2, hpk, hpk_lag1, hpk_lag2, ck, ck_t, ref, ef, es, efm, efm_lag1, efm_lag2; int efm_t; int hold, pk_t, hpk_t, since_sig, sp1, sp2, hold_len;
  float nl; bool valley_armed; int since_on; int since_strong, vs1, vs2, vs3, valley_wait;
  Bq eq[3]; float tone_k = 0.f;
  int lag_next; float c_prev, c_prev2, best_c; int best_L; float top_c; int top_L;

  static const Tab* table()
  {
    static Tab tab[kPhases + 1];
    static bool done = false;
    if (done) return tab;
    for (int p = 0; p <= kPhases; ++p)
    {
      const double frac = static_cast<double>(p) / kPhases; double sum = 0;
      for (int k = 0; k < kTaps; ++k)
      {
        const double t = (k - (kTaps / 2 - 1)) - frac;
        const double sinc = std::fabs(t) < 1e-9 ? 1.0 : std::sin(M_PI * t) / (M_PI * t);
        const double u = (t + frac + (kTaps / 2 - 1)) / (kTaps - 1);  // 0..1 ao longo do nucleo
        const double wn = 0.42 - 0.5 * std::cos(2 * M_PI * (k + 1 - frac) / (kTaps + 1)) + 0.08 * std::cos(4 * M_PI * (k + 1 - frac) / (kTaps + 1));
        (void)u; tab[p][k] = static_cast<float>(sinc * wn); sum += tab[p][k];
      }
      for (int k = 0; k < kTaps; ++k) tab[p][k] = static_cast<float>(tab[p][k] / sum);
    }
    done = true;
    return tab;
  }
  inline float interp(double pos) const
  {
    const int64_t ip = static_cast<int64_t>(pos); const float fr = static_cast<float>(pos - ip);
    const float fp = fr * kPhases; const int p = static_cast<int>(fp); const float a = fp - p;
    const float* t0 = tab[p]; const float* t1 = tab[p + 1]; float acc = 0;
    for (int k = 0; k < kTaps; ++k)
      acc += x[(ip + k - (kTaps / 2 - 1)) & kMask] * (t0[k] + a * (t1[k] - t0[k]));
    return acc;
  }
  // devolve quantas amostras ANTES de `tgt` a onda casa com o que o leitor acabou de tocar (-1 = nao casa)
  int continues_at(int64_t r, int64_t tgt, float* cq) const
  {
    const int maxd = static_cast<int>(std::min<int64_t>(tgt - r - 32, 1400));
    if (maxd < 8) return -1;
    float bc = -2; int bd = -1;
    for (int dl = 0; dl <= maxd; dl += 6)
    {
      float ab = 0, aa = 1e-9f, bb = 1e-9f;
      for (int k = 4; k <= 384; k += 4)
      {
        const float a = lp[(r - k) & kMask], b = lp[(tgt - dl - k) & kMask];
        ab += a * b; aa += a * a; bb += b * b;
      }
      const float c = ab / std::sqrt(aa * bb);
      if (c > bc) { bc = c; bd = dl; }
    }
    *cq = bc;
    if (bc < align_min) return -1; // nada parecido: a nota mudou de verdade
    float fc = -2; int fd = bd; // refino no sinal completo
    for (int dl = std::max(0, bd - 6); dl <= std::min(maxd, bd + 6); ++dl)
    {
      float ab = 0, aa = 1e-9f, bb = 1e-9f;
      for (int k = 1; k <= 192; k += 1)
      {
        const float a = x[(r - k) & kMask], b = x[(tgt - dl - k) & kMask];
        ab += a * b; aa += a * a; bb += b * b;
      }
      const float c = ab / std::sqrt(aa * bb);
      if (c > fc) { fc = c; fd = dl; }
    }
    return fd;
  }
  void start_xfade(double target, int n) { rp2 = target; xf_n = n; xf_i = 0; }
  void restart_search() { lag_next = Lmin; c_prev = c_prev2 = -1; best_c = -1; best_L = 0; top_c = -1; top_L = 0; }

  // correlacao normalizada entre o que acabou de tocar e o trecho L amostras a frente (sinal em graves)
  float corr(int64_t r, int L, const float* sig) const
  {
    float ab = 0, aa = 1e-9f, bb = 1e-9f;
    const int Wl = std::max(W, L);
    for (int k = 4; k <= Wl; k += 4)
    {
      const float a = sig[(r - k) & kMask], b = sig[(r + L - k) & kMask];
      ab += a * b; aa += a * a; bb += b * b;
    }
    return ab / std::sqrt(aa * bb);
  }
  void do_splice(int64_t r, int L, float c, bool forced)
  {
    // refino fino em torno de L: primeiro nos graves (alinha a fundamental e as primeiras parciais, que carregam
    // a energia), depois +-1 amostra no sinal completo
    int bestL = L; float bc = -2;
    const int Wr = std::max(W, L);
    for (int dl = -6; dl <= 6; ++dl)
    {
      float ab = 0, aa = 1e-9f, bb = 1e-9f;
      for (int k = 2; k <= Wr; k += 2)
      {
        const float a = lo[(r - k) & kMask], b = lo[(r + L + dl - k) & kMask];
        ab += a * b; aa += a * a; bb += b * b;
      }
      const float cc = ab / std::sqrt(aa * bb);
      if (cc > bc) { bc = cc; bestL = L + dl; }
    }
    if (forced) bestL = L;
    const int nx = (forced || c < 0.8f) ? 480 : std::clamp(bestL / 2, 96, 400); // emenda sem periodo claro: fusao mais longa
    start_xfade(rp + bestL, nx);
    ++st.splices; if (forced) ++st.forced; st.last_c = c; st.last_L = bestL; st.last_forced = forced;
    restart_search();
  }
  void search_step(double d)
  {
    const int64_t r = static_cast<int64_t>(rp);
    const int Lhi = static_cast<int>(d) - margin - 8; // maior salto possivel agora
    int budget = 10; // no maximo 10 atrasos por chamada (a cada 16 amostras)
    while (lag_next <= Lhi && budget-- > 0)
    {
      const float c = corr(r, lag_next, lp);
      if (c > best_c) { best_c = c; best_L = lag_next; }
      // maximo local acima do limiar: e o periodo -> emenda ja
      // pico acima do limiar: so vale depois que a curva cai 0,05 abaixo dele (cada atraso e medido num instante
      // diferente, entao a curva tem ondulacoes; um maximo local simples disparava na subida)
      if (c >= thr && c > top_c) { top_c = c; top_L = lag_next; }
      if (top_c >= thr && c < top_c - 0.05f)
      {
        // Corda grave: a onda e um pulso forte por periodo e, entre os pulsos, um harmonico que se repete 3-4 vezes.
        // Esse harmonico casa bem (0,85-0,95) num quarto do periodo, e emendar ali da estalo. Se os pulsos fortes vem
        // em intervalos regulares, o periodo nao pode ser bem menor que esse intervalo.
        const bool pulsos = vs1 > 300 && vs2 > 300 && std::abs(vs1 - vs2) * 12 < vs1 && vs1 < 2400;
        const bool sub = pulsos && top_L * 10 < vs1 * 6;
        // Nota soando ha mais de 250 ms: sem pressa. Um casamento so "bom" (abaixo de 0,96) pode ser um harmonico;
        // segue procurando ate o periodo de verdade (casa com 0,96-1,00) ou ate o limite de atraso, e ai vale o melhor.
        const bool espera = since_on > 12000 && top_c < 0.96f;
        if (!sub && !espera && (top_c >= 0.97f || corr(r, top_L, lo) >= thr_lo))
        { do_splice(r, top_L, top_c, false); return; }
        top_c = -1; // rejeitado pela faixa de graves (acorde): segue procurando
      }
      c_prev2 = c_prev; c_prev = c; lag_next += 2;
    }
    if (d > Dmax && best_L > 0 && (lag_next > Lhi || d > Dmax + 480))
      do_splice(r, best_L, best_c, best_c < thr);
  }
};
