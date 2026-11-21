// [mx5-v91] TCHUG: realce da palhetada abafada (djent). 0 = nada (som identico ao drop puro).
// 1) ataque: envelope rapido contra lento -> ate +9 dB nos primeiros ms da nota;
// 2) aperto: quando a nota esta caindo, puxa o volume para baixo (ate -6 dB) -> palm mute mais seco;
// 3) estalo: pico em 2 kHz (ate +3 dB).
// hard (chave MODE em TCHUG): ataque ate +12 dB e aperto ate -12 dB.
struct Tchug
{
  float ef = 0.f, es = 0.f, g = 1.f, amt = -1.f;
  bool hard = false;
  float b0 = 1.f, b1 = 0.f, b2 = 0.f, a1 = 0.f, a2 = 0.f, z1 = 0.f, z2 = 0.f;
  void reset() { ef = es = z1 = z2 = 0.f; g = 1.f; }
  void set(float t)
  {
    if (t == amt) return;
    amt = t;
    const float A = std::pow(10.f, 3.f * t / 40.f), w = 2.f * 3.14159265f * 2000.f / 48000.f;
    const float al = std::sin(w) / (2.f * 0.9f), c = std::cos(w), a0 = 1.f + al / A;
    b0 = (1.f + al * A) / a0; b1 = -2.f * c / a0; b2 = (1.f - al * A) / a0; a1 = -2.f * c / a0; a2 = (1.f - al / A) / a0;
  }
  void run(float* x, int n)
  {
    if (amt <= 0.001f) { ef = es = 0.f; g = 1.f; return; }
    const float fa = 0.0408f, fr = 0.00104f, sa = 0.00139f, sr = 0.000139f; // 0,5 / 20 ms e 15 / 150 ms
    for (int i = 0; i < n; ++i)
    {
      const float a = std::fabs(x[i]);
      ef += (a - ef) * (a > ef ? fa : fr);
      es += (a - es) * (a > es ? sa : sr);
      float r = (ef + 1e-5f) / (es + 1e-5f); // > 1 no ataque, < 1 na queda
      r = std::clamp(r, 0.25f, 4.f);
      const float db = (r >= 1.f ? (hard ? 1.f : 0.75f) : (hard ? 1.f : 0.5f)) * amt * 20.f * std::log10(r);
      const float gt = std::pow(10.f, std::clamp(db, hard ? -12.f : -6.f, hard ? 12.f : 9.f) / 20.f);
      g += (gt - g) * 0.02f;
      const float v = x[i] * g;
      const float y = b0 * v + z1;
      z1 = b1 * v - a1 * y + z2;
      z2 = b2 * v - a2 * y;
      x[i] = y;
    }
  }
};

// [mx5-v91] TIGHT: passa-altas ressonante (30 -> 100 Hz, Q 0,7 -> 1,4): tira o grave solto e marca o "tchug". 0 = desligado.
struct Tight
{
  float amt = -1.f, b0 = 1.f, b1 = 0.f, b2 = 0.f, a1 = 0.f, a2 = 0.f, z1 = 0.f, z2 = 0.f;
  void reset() { z1 = z2 = 0.f; }
  void set(float t)
  {
    if (std::fabs(t - amt) < 0.002f) return;
    amt = t;
    const float w = 2.f * 3.14159265f * (30.f + 70.f * t) / 48000.f, q = 0.7f + 0.7f * t;
    const float al = std::sin(w) / (2.f * q), c = std::cos(w), a0 = 1.f + al;
    b0 = (1.f + c) * 0.5f / a0; b1 = -(1.f + c) / a0; b2 = b0; a1 = -2.f * c / a0; a2 = (1.f - al) / a0;
  }
  void run(float* x, int n)
  {
    if (amt <= 0.01f) { z1 = z2 = 0.f; return; }
    for (int i = 0; i < n; ++i)
    {
      const float v = x[i], y = b0 * v + z1;
      z1 = b1 * v - a1 * y + z2;
      z2 = b2 * v - a2 * y;
      x[i] = y;
    }
  }
};
