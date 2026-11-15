#!/bin/bash
set -uo pipefail
W=/root/mx5; cd $W
NAM_CORE_REF=3cde95c354d5ba6da01316cad90b05cfc4855053
EIGEN_REF=bc3b39870ecb690a623a3f49149a358b95c5781d
if [ ! -d namcore-main/.git ]; then git clone -q https://github.com/sdatkinson/NeuralAmpModelerCore namcore-main || echo "FALHA clone namcore"; fi
if [ ! -f hr/nam_core/NAM/dsp.h ]; then
  rm -rf hr/nam_core; mkdir -p hr/nam_core
  git -C namcore-main archive $NAM_CORE_REF | tar -x -C hr/nam_core && echo "nam_core @ $NAM_CORE_REF extraido do clone"
fi
if [ ! -f hr/nam_core/Dependencies/eigen/Eigen/Core ]; then
  if [ ! -d eigen/.git ]; then
    git clone -q https://gitlab.com/libeigen/eigen.git eigen || echo "FALHA clone eigen (gitlab)"
  fi
  if [ -d eigen/.git ]; then
    mkdir -p hr/nam_core/Dependencies/eigen
    git -C eigen archive $EIGEN_REF | tar -x -C hr/nam_core/Dependencies/eigen && echo "eigen @ $EIGEN_REF extraido"
  fi
fi
ls hr/nam_core/NAM | tr '\n' ' '; echo; ls hr/nam_core/NAM/wavenet 2>/dev/null | tr '\n' ' '; echo
ls hr/nam_core/Dependencies/eigen/Eigen/Core hr/nam_core/Dependencies/nlohmann 2>&1 | head -4
for r in embedded nam-binary-loader; do
  [ -d t3k-$r/.git ] || git clone -q --depth 1 https://github.com/tone-3000/$r t3k-$r || echo "FALHA clone $r"
  echo "=== t3k-$r @ $(git -C t3k-$r log -1 --format='%h %ad %s' --date=short)"
done
echo "=== namcore main @ $(git -C namcore-main log -1 --format='%h %ad %s' --date=short)"
echo "commits depois do commit fixado pelo lolgab: $(git -C namcore-main rev-list --count $NAM_CORE_REF..HEAD)"
git -C namcore-main log --format='%h %ad %s' --date=short $NAM_CORE_REF..HEAD | head -30
echo "=== fixado: $(git -C namcore-main log -1 --format='%h %ad %s' --date=short $NAM_CORE_REF)"
find t3k-embedded -maxdepth 3 -not -path '*/.git*' | sort | head -80
wc -c t3k-embedded/engines/*/*/*.c t3k-embedded/engines/*/*/*.h 2>/dev/null
