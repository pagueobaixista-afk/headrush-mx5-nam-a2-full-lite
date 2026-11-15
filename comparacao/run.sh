set -u
SP="$1"; W=/root/mx5/cmpref; mkdir -p $W; cd $W; cp "$SP/cmp2.py" .
which g++ >/dev/null || { apt-get install -y -qq g++ >/dev/null 2>&1; }
which g++ >/dev/null || { echo SEM_GXX; exit 1; }
NC=/root/mx5/namcore-main
cp "$SP/ref.cpp" .
[ -x $W/render ] || g++ -O2 -std=c++20 -I$NC -I/root/mx5/eigen -I$NC/Dependencies/nlohmann ref.cpp $NC/NAM/*.cpp $NC/NAM/wavenet/*.cpp -o render 2>build.log
[ -x $W/render ] || { echo BUILD_FALHOU; grep -m8 error build.log; exit 1; }
B="/mnt/c/Users/USUARIO/Downloads/Audio e Música/BASS 1_12.wav"
python3 cmp2.py mkin $W/in $NC/example_audio/input.wav "$B"
T=/root/mx5/test; LIB=/root/mx5/build/blobs/libnam_hook.so; M=/mnt/c/Users/USUARIO/Downloads/namma2
for m in "Tech 21 Sansamp Bass Driver 01" "Darkglass Fuzz - OMEGA" "PP-DI-Only" "B7K 6505+ Distorted Bass"; do
  echo "== $m"
  d=$W/m; rm -rf $d; mkdir -p $d; cp "$M/$m.nam" "$d/000 - m.nam"
  ./render "$d/000 - m.nam" in.raw ref_full.raw 2>/dev/null >/dev/null
  ./render "$d/000 - m.nam" in.raw ref_slim.raw 0.5 2>/dev/null >/dev/null
  for h in 1 0; do env NAM_MODEL_DIR=$d NAM_A2_ENGINE=mla H_HILO=$h qemu-arm -L $T/devroot $T/harness $LIB 0 in.raw mx$h.raw 2>/dev/null >/dev/null; done
  python3 cmp2.py ref_full.raw mx1.raw "MX5 High(Full) x oficial"
  python3 cmp2.py ref_slim.raw mx0.raw "MX5 Low(Lite) x oficial reduzido"
  python3 cmp2.py ref_full.raw mx0.raw "MX5 Low(Lite) x oficial completo"
done
