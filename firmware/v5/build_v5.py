"""Monta o firmware MX5 v5 = v4 + nam-sync.sh novo (valida .nam, corrige rigs, nivela volume).
uso: python -I build_v5.py <libdir> <Update.img da v4> <nam-sync.sh> <stock_updater_dir> <outdir>
Unica mudanca em relacao a v4: /usr/Evil/Scripts/nam-sync.sh."""
import sys, os, json, hashlib, lzma, shutil
lib, base_img, sync_sh, stockdir, outdir = sys.argv[1:6]
sys.path.insert(0, lib)
import fitpatch, ext4, xzblocks
OFFICIAL_SHA1 = '82b5639ceaba94d3c07b8880694d5de2e21b9f43'
V4_SHA1 = '3782ea2eb1872a292341c4e8c12554a79b49b0f7'
results = []
def test(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print('[%s] %s %s' % ('OK ' if ok else 'FALHA', name, detail))
    if not ok:
        raise SystemExit('ABORTADO: ' + name)
sha1 = lambda b: hashlib.sha1(b).hexdigest()
rd = lambda p: open(p, 'rb').read()
PS = '/usr/Evil/Scripts/nam-sync.sh'
raw = rd(base_img); raw_s = rd(os.path.join(stockdir, 'Update.img')); sync = rd(sync_sh)
test('D1 base = Update.img da v4; original com SHA1 oficial',
     fitpatch.verify(raw) and sha1(raw) == V4_SHA1 and sha1(raw_s) == OFFICIAL_SHA1, sha1(raw))
test('D2 nam-sync.sh: script sh, sem CR, termina em nova linha', sync.startswith(b'#!/bin/sh' + bytes([10])) and bytes([13]) not in sync and sync.endswith(bytes([10])),
     '%d bytes, sha1 %s' % (len(sync), sha1(sync)))
rootfs = lzma.decompress(fitpatch.extract(raw, 'rootfs'))
fs = ext4.Ext4(rootfs); fs.check()
sync_old = fs.cat(PS); sync_mode = fs.read(fs.lookup(PS))[0]
test('D3 base: nam-sync.sh existe (v4), executavel, e runevil/mount_usb_img ja o chamam',
     sync_mode & 0o111 and b'nam-sync.sh boot' in fs.cat('/usr/Evil/Scripts/runevil') and b'nam-sync.sh transfer' in fs.cat('/usr/Evil/Scripts/mount_usb_img'), oct(sync_mode))
test('D4 script novo aceita os mesmos modos que os chamadores usam', all(t in sync for t in (b'restart-wait', b'MODE=${1:-boot}', b'nam_sync_off.txt')))

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
fs.write_file(PS, sync, sync_mode)
new_rootfs = fs.finish()
chk = ext4.Ext4(new_rootfs); chk.check()
m1, g1 = chk.read(chk.lookup(PS))
test('D5 arquivo relido de um sistema de arquivos reaberto: conteudo e permissao conferem', g1 == sync and m1 == sync_mode, oct(m1))
inew = index(new_rootfs)
dd = sorted(k for k in set(inew) | set(ibase) if inew.get(k) != ibase.get(k))
test('D6 entre %d arquivos, so mudou o nam-sync.sh' % len(inew), dd == [PS] and len(inew) == len(ibase), str(dd))
test('D7 tamanho da particao inalterado', len(new_rootfs) == len(rootfs))
os.makedirs(outdir, exist_ok=True)
open(os.path.join(outdir, 'fontes', 'rootfs_v5.bin'), 'wb').write(new_rootfs)

xz = xzblocks.compress(new_rootfs)
test('D8 xz descomprime de volta para o rootfs exato', lzma.decompress(xz) == new_rootfs, '%d bytes' % len(xz))
img = fitpatch.replace_image(raw, 'rootfs', xz)
_, props = fitpatch.parse(img)
nodes = sorted({p[0] for p in props if p[0].startswith('/images/') and p[0].count('/') == 2})
test('D9 FIT final valido; so splash/recoverysplash/rootfs; splashes identicos aos originais',
     fitpatch.verify(img) and nodes == ['/images/recoverysplash', '/images/rootfs', '/images/splash'] and
     all(fitpatch.extract(img, im) == fitpatch.extract(raw_s, im) for im in ('splash', 'recoverysplash')))
test('D10 tamanho do Update.img dentro do que a v3 ja gravou com sucesso (+-1%%)', abs(len(img) - len(raw)) < len(raw) // 100, '%d x %d bytes' % (len(img), len(raw)))

inst = os.path.join(outdir, '1_INSTALAR_NAM_A2_v5')
rest = os.path.join(outdir, '2_RESTAURAR_ORIGINAL_2.7')
for d in (inst, rest):
    os.makedirs(d, exist_ok=True)
    for name in ('FirmwareUpdater.exe', 'libusb-1.0.dll', 'Background.png'):
        shutil.copyfile(os.path.join(stockdir, name), os.path.join(d, name))
shutil.copyfile(os.path.join(stockdir, 'Config.json'), os.path.join(rest, 'Config.json'))
shutil.copyfile(os.path.join(stockdir, 'Update.img'), os.path.join(rest, 'Update.img'))
cfg = json.loads(open(os.path.join(stockdir, 'Config.json'), encoding='utf-8-sig').read())
cfg['config']['appName'] = 'HeadRush MX5 v2.7 + NAM A2 v5 (presets, rigs e volume automaticos) + MX5Bridge 0.7 + arte (nao oficial)'
cfg['config']['startButtonText'] = 'Instalar NAM A2 v5'
open(os.path.join(inst, 'Config.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(cfg, indent=4, ensure_ascii=False) + '\n')
open(os.path.join(inst, 'Update.img'), 'wb').write(img)
back = rd(os.path.join(inst, 'Update.img'))
bfs = ext4.Ext4(lzma.decompress(fitpatch.extract(back, 'rootfs')))
test('D11 Update.img gravado e relido do disco: identico; o nam-sync.sh dentro dele confere',
     back == img and bfs.cat(PS) == sync, sha1(back))
test('D12 pacote de restauracao com o SHA1 oficial', sha1(rd(os.path.join(rest, 'Update.img'))) == OFFICIAL_SHA1)
open(os.path.join(outdir, 'TESTES_FIRMWARE.txt'), 'w', encoding='utf-8').write(
    '\n'.join('[%s] %s %s' % ('OK' if ok else 'FALHA', n, dt) for n, ok, dt in results) + '\n\nSHA1 Update.img: %s\n' % sha1(img))
print('\n%d testes OK. SHA1 final: %s  %d bytes' % (len(results), sha1(img), len(img)))
