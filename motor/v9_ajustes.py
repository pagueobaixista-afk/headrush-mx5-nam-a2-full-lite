"""v9: ajustes de padrao no NAM A2 Pro.  uso (WSL): python3 v9_ajustes.py <build>/patch/nam_hook.cpp  (aplica por ultimo)
 - FULL por padrao: o valor de fabrica do Bit Mode e "A" (medido: pedal recem-adicionado entra em A), que era LITE.
   Agora A = FULL, B = FULL (rigs antigos salvos em FULL continuam FULL), C = LITE (novo), Off/outros = AUTO.
   Rigs antigos salvos em LITE passam a FULL. Padrao de bytes do C: +0x5d7=1, +0x5e0=3, +0x5e3=3.
 - Gate: o limiar aplicado fica 10 dB abaixo do valor guardado; o padrao de fabrica (-30 dB) passa a valer -40 dB
   ("o som morria rapido"). A tela mostra o valor ja com os 10 dB. Abaixo de -59 dB guardado o gate continua desligado."""
import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()


def troca(a, b, n=1):
    global s
    if s.count(a) != n:
        sys.exit('v9: trecho %d vezes (esperado %d): %r' % (s.count(a), n, a[:80]))
    s = s.replace(a, b)


troca('''  if (m[0x5d7] == 3 && m[0x5e0] == 2 && m[0x5e3] == 2 && m[0x5e6] == 2) return 1; // B = FULL
  if (m[0x5dd] == 2 && m[0x5e6] == 2 && m[0x5d7] == 0 && m[0x5e0] == 0 && m[0x5e3] == 0) return 0; // A = LITE
  return 2; // resto = AUTO''',
      '''  if (m[0x5d7] == 3 && m[0x5e0] == 2 && m[0x5e3] == 2 && m[0x5e6] == 2) return 1; // B = FULL
  if (m[0x5dd] == 2 && m[0x5e6] == 2 && m[0x5d7] == 0 && m[0x5e0] == 0 && m[0x5e3] == 0) return 1; // [mx5-v9] A (padrao de fabrica) = FULL
  if (m[0x5d7] == 1 && m[0x5e0] == 3 && m[0x5e3] == 3) return 0; // [mx5-v9] C = LITE
  return 2; // resto (Off) = AUTO''')
troca('''    const float thr = pro::f(this_, 0x5b0);
    const bool gate_on = thr > 0.0011f;''',
      '''    const float thr0 = pro::f(this_, 0x5b0);
    const bool gate_on = thr0 > 0.0011f;
    const float thr = thr0 * 0.316228f; // [mx5-v9] 10 dB abaixo do valor guardado (padrao -30 -> -40 dB)''')
open(p, 'w', encoding='utf-8').write(s)
print('ok v9_ajustes')
