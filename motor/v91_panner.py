"""v9.1: o Drop Starcz sai do "Drop Tune" e passa a morar no pedal "Panner" (pedido do usuario: dois pedais separados
no menu; o Drop Tune volta a ser 100% o original).  uso (WSL): python3 v91_panner.py <build>/patch/nam_hook.cpp [mapa]
(aplica por ultimo, depois de v9_ajustes.py)

Classe EvilDSPs::Panner: vtable 0x17e07f4, process no slot 8 (original 0x2c2c28), mesma assinatura dos pedais.
Parametros do Panner reaproveitados (campos escritos pelo ajuste do parametro, medidos com o desvio ativo):
  DEPTH +0x370 (0..1) -> intervalo (Down 1..12), SHAPE +0x384 (0..1) -> TIMBRE, DELAY +0x358 (-0.03..0.03) -> LEVEL (centro = 0 dB,
  +-12 dB), bypass +0x26b. PAN +0x344 (-1..1) -> TCHUG 0..100 % (v91_tchug.inc). RATE +0x364 (0,1..12 Hz, log) -> TIGHT 0..100 % (so vale com SYNC em OFF: com SYNC ligado o Rate segue o andamento).
  SYNC byte +0x618: a chave fica escondida na tela; se vier ligada num rig, o TIGHT fica desligado.
Com o argumento "mapa" gera a versao provisoria (parametros fixos) usada so para medir os campos."""
import sys

p = sys.argv[1]
MAPA = len(sys.argv) > 2 and sys.argv[2] == 'mapa'
s = open(p, encoding='utf-8').read()


def troca(a, b, n=1):
    global s
    if s.count(a) != n:
        sys.exit('v91: trecho %d vezes (esperado %d): %r' % (s.count(a), n, a[:80]))
    s = s.replace(a, b)


troca('constexpr uintptr_t kVtable = 0x17e0af0;\nconstexpr uint32_t kOrigProcess = 0x2bba00;',
      'constexpr uintptr_t kVtable = 0x17e07f4;   // [mx5-v91] EvilDSPs::Panner\nconstexpr uint32_t kOrigProcess = 0x2c2c28;')
troca('    I->kind = kind_of(this_);', '    I->kind = 1; // [mx5-v91] todo Panner e Drop Starcz')
troca('I->kind == 1 ? "Drop Starcz (Drop Tune)" : "Drop original (Drop Tune 2)"', '"Drop Starcz (Panner)"')
troca('nam_a2_log("drop: tabela do Drop Tune diferente do esperado (%x), fica o original", w[8]);',
      'nam_a2_log("drop: tabela do Panner diferente do esperado (%x), fica o original", w[8]);')
troca('nam_a2_log("drop: Drop Tune proprio instalado");', 'nam_a2_log("drop: Drop Starcz instalado no Panner");')
VELHO = '''  const int mode = std::min<int>(m[0x650], 11);
  const float semis = -static_cast<float>(mode + 1);
  float mix_t, lvl;
  std::memcpy(&mix_t, m + 0x654, 4);
  std::memcpy(&lvl, m + 0x668, 4);
  mix_t = std::clamp(mix_t, 0.f, 1.f);
  const float gain_t = lvl <= 0.001f ? 0.f : std::pow(10.f, (std::clamp(lvl, 0.f, 1.f) * 66.f - 60.f) / 20.f);'''
if MAPA:
    NOVO = '''  const float semis = -4.f; // [mx5-v91] provisorio, so para medir os campos do Panner
  float mix_t = 0.5f;
  const float gain_t = 1.f;'''
else:
    NOVO = '''  // [mx5-v91] parametros do Panner: Depth -> intervalo, Shape -> TIMBRE, Delay -> LEVEL
  float depth, shape, pan;
  std::memcpy(&depth, m + 0x370, 4);
  std::memcpy(&shape, m + 0x384, 4);
  std::memcpy(&pan, m + 0x358, 4);
  const float semis = -static_cast<float>(1 + static_cast<int>(std::clamp(depth, 0.f, 1.f) * 11.f + 0.5f)); // 0..100% = Down 1..12
  float mix_t = std::clamp(shape, 0.f, 1.f);
  float panv;
  std::memcpy(&panv, m + 0x344, 4);
  const float tchug = std::clamp((panv + 1.f) * 0.5f, 0.f, 1.f); // PAN: -100..100 = TCHUG 0..100 %
  float ratev;
  std::memcpy(&ratev, m + 0x364, 4);
  const bool mode_tchug = m[0x618] != 0; // chave SYNC (escondida na tela): ligada, o Rate vira andamento -> TIGHT desligado
  const float tight = mode_tchug ? 0.f : std::clamp(std::log(std::max(ratev, 0.1f) * 10.f) / 4.7875f, 0.f, 1.f); // RATE 0,1..12 Hz (log) = TIGHT 0..100 %
  const float gain_t = std::pow(10.f, std::clamp(pan / 0.03f, -1.f, 1.f) * 12.f / 20.f); // -12 .. +12 dB'''
troca(VELHO, NOVO)
if not MAPA:
    import os
    TCH = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'v91_tchug.inc'), encoding='utf-8').read()
    troca('struct Inst\n{', TCH + '\nstruct Inst\n{\n  Tchug fx[2];\n  Tight tg[2];')
    # caminho normal e autoteste: TCHUG depois do drop, antes do nivel
    troca('    I->ch[c].process(in[c], wet, nf);\n', '    I->ch[c].process(in[c], wet, nf);\n    I->fx[c].hard = false;\n    I->fx[c].set(tchug);\n    I->fx[c].run(wet, nf);\n    I->tg[c].set(tight);\n    I->tg[c].run(wet, nf);\n')
    troca('      I->ch[0].process(&g_tin[g_tpos], wet, nf);\n', '      I->ch[0].process(&g_tin[g_tpos], wet, nf);\n      I->fx[0].hard = false;\n      I->fx[0].set(tchug);\n      I->fx[0].run(wet, nf);\n      I->tg[0].set(tight);\n      I->tg[0].run(wet, nf);\n')
    troca('    I->ch[0].reset();\n    I->ch[1].reset();\n', '    I->ch[0].reset();\n    I->ch[1].reset();\n    I->fx[0].reset();\n    I->fx[1].reset();\n    I->tg[0].reset();\n    I->tg[1].reset();\n')
open(p, 'w', encoding='utf-8').write(s)
print('ok v91_panner' + (' (mapa)' if MAPA else ''))
