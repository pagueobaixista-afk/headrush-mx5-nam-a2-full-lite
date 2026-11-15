"""Monta o firmware MX5 = NAM A2 (motor novo) + MX5 Bridge 0.7 + arte.

uso: python -I build_a2.py <libdir> <base Update.img (pacote 1B)> <libnam_hook.so novo> <libnam_hook.so do lolgab>
                           <stock_updater_dir> <outdir> <workdir>

Base: o Update.img do pacote 1B (ja validado). Unica mudanca: /usr/Evil/libnam_hook.so."""
import sys, os, json, hashlib, lzma, shutil
lib, base_img, new_so, old_so, stockdir, outdir, work = sys.argv[1:8]
sys.path.insert(0, lib)
import fitpatch, ext4, xzblocks
OFFICIAL_SHA1 = '82b5639ceaba94d3c07b8880694d5de2e21b9f43'
results = []
def test(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print('[%s] %s %s' % ('OK ' if ok else 'FALHA', name, detail))
    if not ok:
        raise SystemExit('ABORTADO: ' + name)
sha1 = lambda b: hashlib.sha1(b).hexdigest()
rd = lambda p: open(p, 'rb').read()
P = '/usr/Evil/libnam_hook.so'

raw = rd(base_img); raw_s = rd(os.path.join(stockdir, 'Update.img'))
new, old = rd(new_so), rd(old_so)
test('A1 base = pacote 1B (FIT valido); original com SHA1 oficial', fitpatch.verify(raw) and sha1(raw_s) == OFFICIAL_SHA1, sha1(raw))
rootfs = lzma.decompress(fitpatch.extract(raw, 'rootfs'))
fs = ext4.Ext4(rootfs); fs.check()
test('A2 o libnam_hook.so da base e o do lolgab (que meu ambiente reproduz byte a byte)', fs.cat(P) == old, sha1(old))
test('A3 binario novo: ELF ARM 32 bits, biblioteca compartilhada', new[:4] == b'\x7fELF' and new[4] == 1 and new[18] == 40 and new[16] == 3,
     '%d bytes, sha1 %s' % (len(new), sha1(new)))
mode_before = fs.read(fs.lookup(P))[0]

def index(img):
    f = ext4.Ext4(img); f.check(); out = {}
    def walk(n, path):
        for name, i, ft in f.listdir(n):
            if name in ('.', '..', 'lost+found'):
                continue
            mode, data = f.read(i)
            if mode & 0xF000 == 0x4000:
                out[path + '/' + name + '/'] = (mode, 0, ''); walk(i, path + '/' + name)
            else:
                out[path + '/' + name] = (mode, len(data), sha1(data))
    walk(2, ''); return out
ibase = index(rootfs)
fs.write_file(P, new, mode_before)
new_rootfs = fs.finish()
chk = ext4.Ext4(new_rootfs); chk.check()
m, got = chk.read(chk.lookup(P))
test('A4 arquivo gravado e relido de um sistema de arquivos reaberto: conteudo e permissao conferem', got == new and m == mode_before, oct(m))
inew = index(new_rootfs)
dd = sorted(k for k in set(inew) | set(ibase) if inew.get(k) != ibase.get(k))
test('A5 entre %d arquivos, so o libnam_hook.so mudou em relacao ao pacote 1B' % len(inew), dd == [P], str(dd))
test('A6 tamanho da particao inalterado', len(new_rootfs) == len(rootfs))
os.makedirs(work, exist_ok=True)
open(os.path.join(work, 'rootfs_a2.bin'), 'wb').write(new_rootfs)
open(os.path.join(work, 'rootfs_1b.bin'), 'wb').write(rootfs)

xz = xzblocks.compress(new_rootfs)
test('A7 xz descomprime de volta para o rootfs exato', lzma.decompress(xz) == new_rootfs, '%d bytes' % len(xz))
img = fitpatch.replace_image(raw, 'rootfs', xz)
_, props = fitpatch.parse(img)
nodes = sorted({p[0] for p in props if p[0].startswith('/images/') and p[0].count('/') == 2})
test('A8 FIT final valido; so splash/recoverysplash/rootfs; splashes identicos aos originais',
     fitpatch.verify(img) and nodes == ['/images/recoverysplash', '/images/rootfs', '/images/splash'] and
     all(fitpatch.extract(img, im) == fitpatch.extract(raw_s, im) for im in ('splash', 'recoverysplash')))

inst = os.path.join(outdir, '1_INSTALAR_NAM_A2')
rest = os.path.join(outdir, '2_RESTAURAR_ORIGINAL_2.7')
for d in (inst, rest):
    os.makedirs(d, exist_ok=True)
    for name in ('FirmwareUpdater.exe', 'libusb-1.0.dll', 'Background.png'):
        shutil.copyfile(os.path.join(stockdir, name), os.path.join(d, name))
shutil.copyfile(os.path.join(stockdir, 'Config.json'), os.path.join(rest, 'Config.json'))
shutil.copyfile(os.path.join(stockdir, 'Update.img'), os.path.join(rest, 'Update.img'))
cfg = json.loads(open(os.path.join(stockdir, 'Config.json'), encoding='utf-8-sig').read())
cfg['config']['appName'] = 'HeadRush MX5 v2.7 + NAM A2 + MX5Bridge 0.7 + arte (nao oficial)'
cfg['config']['startButtonText'] = 'Instalar NAM A2 + Bridge + arte'
open(os.path.join(inst, 'Config.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(cfg, indent=4, ensure_ascii=False) + '\n')
open(os.path.join(inst, 'Update.img'), 'wb').write(img)
back = rd(os.path.join(inst, 'Update.img'))
bfs = ext4.Ext4(lzma.decompress(fitpatch.extract(back, 'rootfs')))
test('A9 Update.img gravado e relido do disco: identico; libnam_hook.so dentro dele = binario novo', back == img and bfs.cat(P) == new, sha1(back))
test('A10 pacote de restauracao com o SHA1 oficial', sha1(rd(os.path.join(rest, 'Update.img'))) == OFFICIAL_SHA1)
open(os.path.join(outdir, 'TESTES_FIRMWARE.txt'), 'w', encoding='utf-8').write(
    '\n'.join('[%s] %s %s' % ('OK' if ok else 'FALHA', n, dt) for n, ok, dt in results) + '\n\nSHA1 Update.img: %s\n' % sha1(img))
print('\n%d testes OK. SHA1 final: %s  %d bytes' % (len(results), sha1(img), len(img)))
