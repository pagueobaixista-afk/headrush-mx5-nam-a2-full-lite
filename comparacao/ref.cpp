// ref <model.nam> <in.raw f32> <out.raw f32> [slim]  -- NeuralAmpModelerCore oficial, mesmo laco do tools/render.cpp
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <vector>
#include "NAM/dsp.h"
#include "NAM/get_dsp.h"
#include "NAM/slimmable.h"
int main(int argc, char** argv)
{
  auto model = nam::get_dsp(std::filesystem::path(argv[1]));
  if (argc > 4) { auto* s = dynamic_cast<nam::SlimmableModel*>(model.get()); if (!s) return 3; s->SetSlimmableSize(atof(argv[4])); }
  FILE* f = fopen(argv[2], "rb"); fseek(f, 0, SEEK_END); size_t n = ftell(f) / 4; fseek(f, 0, SEEK_SET);
  std::vector<float> in(72000 + n, 0.0f), out; if (fread(in.data() + 72000, 4, n, f) != n) return 4; fclose(f);
  const int B = 64; model->Reset(48000.0, B);
  std::vector<NAM_SAMPLE> ib(B), ob(B); NAM_SAMPLE* ip = ib.data(); NAM_SAMPLE* op = ob.data();
  for (size_t p = 0; p < in.size(); p += B) {
    size_t k = std::min((size_t)B, in.size() - p);
    for (size_t i = 0; i < (size_t)B; i++) ib[i] = i < k ? in[p + i] : 0;
    model->process(&ip, &op, (int)k);
    for (size_t i = 0; i < k; i++) out.push_back((float)ob[i]);
  }
  f = fopen(argv[3], "wb"); fwrite(out.data() + 72000, 4, n, f); fclose(f);
  return 0;
}
