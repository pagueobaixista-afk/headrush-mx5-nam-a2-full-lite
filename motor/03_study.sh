#!/bin/bash
cd /root/mx5
E=t3k-embedded/engines/cortex-a76
echo "=== intrinsics NEON usados (a2full / a2lite)"
for f in a2full/nam_a2full.c a2lite/nam_a2lite.c; do
  grep -oE '\bv[a-z0-9_]+_(f32|u32|s32)\b' $E/$f | sort | uniq -c | sort -rn | tr '\n' ';'; echo
done
echo "=== guardas de pre-processador"
grep -nE '^\s*#\s*(if|ifdef|ifndef|elif|else|endif|define NAM_|include)' $E/a2full/nam_a2full.c | head -60
echo "=== header a2full"
cat $E/a2full/nam_a2full.h
echo "=== example/a2_engine.h"
cat t3k-embedded/example/a2_engine.h
echo "=== namb_reader.h"
cat t3k-embedded/namb/namb_reader.h
echo "=== MANIFEST"
cat t3k-embedded/MANIFEST.json | head -60
