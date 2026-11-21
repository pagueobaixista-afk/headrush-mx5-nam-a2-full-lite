"""prepara_v9.py : arte_v9 (arte_v8 + icones novos de IR), DropStarcz.png, splash_v9.xz e nam-sync.sh da v9."""
import os, io, lzma, shutil
from PIL import Image
A = r"C:\Users\Starcz\Documents\arsenal\mx5\arte_MX5"
FW = r"C:\Users\Starcz\Documents\arsenal\mx5\github\mx5-nam-a2\firmware"
def reduz(src, size, dst):
    im = Image.open(src).convert('RGBA').resize(size, Image.LANCZOS)
    q = im.quantize(colors=255, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    b = io.BytesIO(); q.save(b, 'PNG', optimize=True); open(dst, 'wb').write(b.getvalue())
    print('%-28s %s -> %s, %d bytes' % (os.path.basename(dst), Image.open(src).size, size, len(b.getvalue())))
if os.path.isdir('arte_v9'): shutil.rmtree('arte_v9')
shutil.copytree(os.path.join(A, 'arte_v8'), 'arte_v9')
for n in ('IR (1024).png', 'IR (1024)2.png'):
    reduz(os.path.join(A, n), Image.open(os.path.join(A, 'arte_v8', n)).size, os.path.join('arte_v9', n))
reduz(os.path.join(A, 'drop starcz.png'), (154, 249), 'DropStarcz.png')
print('arte_v9:', sum(len(f) for _, _, f in os.walk('arte_v9')), 'arquivos')
# abertura: 800x480 (corte central) -> tela fisica 480x800 girada, BGRA, alfa 255
im = Image.open(os.path.join(A, 'abertura', 'v9.jpg')).convert('RGB'); w, h = im.size
tw = int(round(h * 800 / 480)); x0 = (w - tw) // 2
land = im.crop((x0, 0, x0 + tw, h)).resize((800, 480), Image.LANCZOS)
land.save(os.path.join(A, 'abertura', 'splash_v9_800x480.png'))
raw = land.rotate(270, expand=True).convert('RGBA').tobytes('raw', 'BGRA')
assert len(raw) == 480 * 800 * 4
sx = lzma.compress(raw, format=lzma.FORMAT_XZ, check=lzma.CHECK_CRC64, filters=[{'id': lzma.FILTER_LZMA2, 'preset': 9 | lzma.PRESET_EXTREME, 'dict_size': 4 << 20}])
assert lzma.LZMADecompressor(memlimit=8 << 20).decompress(sx) == raw and sx[7] == 4
open('splash_v9.xz', 'wb').write(sx); shutil.copy('splash_v9.xz', os.path.join(A, 'abertura', 'splash_v9.xz')); print('splash_v9.xz', len(sx), 'bytes')
# nam-sync v9: presets novos com gate em -40 dB (valor guardado -30) e NAM em FULL (Bit Mode Off)
s = open(os.path.join(FW, 'v8', 'nam-sync.sh'), encoding='utf-8', newline='').read()
def tr(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)
tr('(v8: NAM A2 Pro no 8-Bit Crush)', '(v9: NAM A2 Pro no 8-Bit Crush)')
tr('gate desligado, NAM A2 em AUTO.', 'gate em -40 dB (valor guardado -30; a v9 aplica 10 dB abaixo), NAM A2 em FULL (Bit Mode A).')
tr('"ThresholdExp":{"type":0,"value":-60}', '"ThresholdExp":{"type":0,"value":-30}')
tr('"Mode":{"string":"Off","type":4}', '"Mode":{"string":"A","type":4}')
open(os.path.join(FW, 'v9', 'nam-sync.sh'), 'w', encoding='utf-8', newline='').write(s); print('nam-sync v9 ok', len(s))
