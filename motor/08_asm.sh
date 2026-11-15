#!/bin/bash
# Evidencia estatica: o caminho A2 do lolgab (A2FastModel, GCC 9.3, ARMv7) e vetorizado?
export PATH="$PATH:/opt/toolchain/bin"
TC=arm-buildroot-linux-gnueabihf
U=/root/mx5/build/blobs/libnam_hook.unstripped.so
cd /root/mx5/build
$TC-objdump -d -C --no-show-raw-insn $U > all.S
python3 - <<'EOF'
import re, collections
funcs = {}; cur = None
for line in open('all.S', errors='replace'):
    m = re.match(r'^[0-9a-f]+ <(.+)>:$', line)
    if m:
        cur = m.group(1); funcs[cur] = []; continue
    if cur and '\t' in line:
        parts = line.split('\t')
        if len(parts) >= 2:
            funcs[cur].append((parts[1].strip(), parts[2].strip() if len(parts) > 2 else ''))
def stats(pred, title):
    ins = [i for f, l in funcs.items() if pred(f) for i in l]
    fp = [(op, args) for op, args in ins if re.match(r'^v(fma|fms|mla|mls|mul|add|sub|max|min|fnma|fnms)', op)]
    vec = sum(1 for op, a in fp if re.search(r'\bq\d+', a))
    dvec = sum(1 for op, a in fp if re.search(r'\bd\d+', a) and not re.search(r'\bq\d+', a) and '.f32' in op)
    sca = sum(1 for op, a in fp if re.search(r'\bs\d+', a))
    c = collections.Counter(op for op, a in fp)
    print('%s\n   funcoes: %d, instrucoes: %d, aritmetica FP: %d  -> vetorial(q, 4 floats): %d | vetorial(d, 2 floats): %d | escalar(s): %d'
          % (title, sum(1 for f in funcs if pred(f)), len(ins), len(fp), vec, dvec, sca))
    print('   mais comuns:', ', '.join('%s x%d' % kv for kv in c.most_common(8)))
    return ins
stats(lambda f: 'A2FastModel<8>' in f, 'core A2 Full  (A2FastModel<8>)')
stats(lambda f: 'A2FastModel<3>' in f, 'core A2 Lite  (A2FastModel<3>)')
stats(lambda f: f.startswith('fma_nam_a2full') or (f.startswith('nam_') and False), 't3k Full (fma) -- funcoes publicas')
big = sorted(((len(l), f) for f, l in funcs.items() if 'A2FastModel' in f), reverse=True)[:6]
print('maiores funcoes A2FastModel:', [(n, f[:70]) for n, f in big])
EOF
# os motores t3k tem os kernels como funcoes static: contar no objeto
for v in fma mla; do
  $TC-objdump -d --no-show-raw-insn t3k/${v}_a2full.o | awk -F'\t' 'NF>=2{print $2" "$3}' > t3k_$v.S
  tot=$(grep -cE '^v(fma|fms|mla|mls|mul|add|sub|max)' t3k_$v.S)
  q=$(grep -E '^v(fma|fms|mla|mls|mul|add|sub|max)' t3k_$v.S | grep -cE '\bq[0-9]+')
  s=$(grep -E '^v(fma|fms|mla|mls|mul|add|sub|max)' t3k_$v.S | grep -cE '\bs[0-9]+')
  echo "t3k Full ($v): aritmetica FP: $tot -> vetorial(q): $q | escalar(s): $s | vldr/vstr (spill em pilha): $(grep -cE '^v(ldr|str) ' t3k_$v.S)"
done
