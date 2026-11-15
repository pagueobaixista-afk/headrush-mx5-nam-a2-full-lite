"""Monta o firmware MX5 v3 = v2 (NAM A2 + Bridge 0.7 + arte) + sincronizacao automatica dos presets NAM.
uso: python -I build_v3.py <libdir> <Update.img da v2> <nam-sync.sh> <stock_updater_dir> <outdir>
Mudancas em relacao a v2: arquivo novo /usr/Evil/Scripts/nam-sync.sh e uma chamada a ele em /usr/Evil/Scripts/runevil."""
import sys, os, json, hashlib, lzma, shutil
lib, base_img, sync_sh, stockdir, outdir = sys.argv[1:6]
sys.path.insert(0, lib)
import fitpatch, ext4, xzblocks
OFFICIAL_SHA1 = '82b5639ceaba94d3c07b8880694d5de2e21b9f43'
V2_SHA1 = 'd1ba4eec26b71e0c7e2063e74938a95062fd47f6'
results = []
def test(name, ok, detail=''):
    results.append((name, bool(ok), detail))
    print('[%s] %s %s' % ('OK ' if ok else 'FALHA', name, detail))
    if not ok:
        raise SystemExit('ABORTADO: ' + name)
sha1 = lambda b: hashlib.sha1(b).hexdigest()
rd = lambda p: open(p, 'rb').read()
PS, PR = '/usr/Evil/Scripts/nam-sync.sh', '/usr/Evil/Scripts/runevil'
ANCHOR = b'# MX5 Bridge: USB-MIDI-Dienst und Datenbankdienst (nicht kritisch)\n'
CALL = (b'# NAM: numera modelos novos e sincroniza os presets do Anxiety OD (nao critico)\n'
        b'[ -x /usr/Evil/Scripts/nam-sync.sh ] && /usr/Evil/Scripts/nam-sync.sh >/tmp/nam_sync.log 2>&1 </dev/null\n\n')

raw = rd(base_img); raw_s = rd(os.path.join(stockdir, 'Update.img')); sync = rd(sync_sh)
test('B1 base = Update.img da v2 (SHA1 do pacote testado em show); original com SHA1 oficial',
     fitpatch.verify(raw) and sha1(raw) == V2_SHA1 and sha1(raw_s) == OFFICIAL_SHA1, sha1(raw))
test('B2 nam-sync.sh: script sh, sem CR, termina em nova linha', sync.startswith(b'#!/bin/sh\n') and b'\r' not in sync and sync.endswith(b'\n'),
     '%d bytes, sha1 %s' % (len(sync), sha1(sync)))
rootfs = lzma.decompress(fitpatch.extract(raw, 'rootfs'))
fs = ext4.Ext4(rootfs); fs.check()
run_old = fs.cat(PR); run_mode = fs.read(fs.lookup(PR))[0]
test('B3 runevil da base tem o ponto de insercao exatamente uma vez e ainda nao chama o nam-sync; nam-sync.sh ainda nao existe',
     run_old.count(ANCHOR) == 1 and b'nam-sync' not in run_old and not fs.exists(PS), oct(run_mode))
run_new = run_old.replace(ANCHOR, CALL + ANCHOR)
test('B4 runevil novo = antigo + so as linhas inseridas', run_new.replace(CALL, b'') == run_old and len(run_new) == len(run_old) + len(CALL))

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
fs.write_file(PS, sync, run_mode)
fs.write_file(PR, run_new, run_mode)
new_rootfs = fs.finish()
chk = ext4.Ext4(new_rootfs); chk.check()
m1, g1 = chk.read(chk.lookup(PS)); m2, g2 = chk.read(chk.lookup(PR))
test('B5 os dois arquivos relidos de um sistema de arquivos reaberto: conteudo e permissao (executavel) conferem',
     g1 == sync and g2 == run_new and m1 == run_mode and m2 == run_mode and run_mode & 0o111, oct(m1))
inew = index(new_rootfs)
dd = sorted(k for k in set(inew) | set(ibase) if inew.get(k) != ibase.get(k))
test('B6 entre %d arquivos, so mudaram: runevil (alterado) e nam-sync.sh (novo)' % len(inew), dd == sorted([PS, PR]) and PS not in ibase, str(dd))
test('B7 tamanho da particao inalterado', len(new_rootfs) == len(rootfs))
os.makedirs(outdir, exist_ok=True)
open(os.path.join(outdir, 'fontes', 'rootfs_v3.bin'), 'wb').write(new_rootfs)
open(os.path.join(outdir, 'fontes', 'runevil_v3'), 'wb').write(run_new)

xz = xzblocks.compress(new_rootfs)
test('B8 xz descomprime de volta para o rootfs exato', lzma.decompress(xz) == new_rootfs, '%d bytes' % len(xz))
img = fitpatch.replace_image(raw, 'rootfs', xz)
_, props = fitpatch.parse(img)
nodes = sorted({p[0] for p in props if p[0].startswith('/images/') and p[0].count('/') == 2})
test('B9 FIT final valido; so splash/recoverysplash/rootfs; splashes identicos aos originais',
     fitpatch.verify(img) and nodes == ['/images/recoverysplash', '/images/rootfs', '/images/splash'] and
     all(fitpatch.extract(img, im) == fitpatch.extract(raw_s, im) for im in ('splash', 'recoverysplash')))
test('B10 tamanho do Update.img dentro do que a v2 ja gravou com sucesso (+-1%%)', abs(len(img) - len(raw)) < len(raw) // 100, '%d x %d bytes' % (len(img), len(raw)))

inst = os.path.join(outdir, '1_INSTALAR_NAM_A2_v3')
rest = os.path.join(outdir, '2_RESTAURAR_ORIGINAL_2.7')
for d in (inst, rest):
    os.makedirs(d, exist_ok=True)
    for name in ('FirmwareUpdater.exe', 'libusb-1.0.dll', 'Background.png'):
        shutil.copyfile(os.path.join(stockdir, name), os.path.join(d, name))
shutil.copyfile(os.path.join(stockdir, 'Config.json'), os.path.join(rest, 'Config.json'))
shutil.copyfile(os.path.join(stockdir, 'Update.img'), os.path.join(rest, 'Update.img'))
cfg = json.loads(open(os.path.join(stockdir, 'Config.json'), encoding='utf-8-sig').read())
cfg['config']['appName'] = 'HeadRush MX5 v2.7 + NAM A2 v3 (presets automaticos) + MX5Bridge 0.7 + arte (nao oficial)'
cfg['config']['startButtonText'] = 'Instalar NAM A2 v3'
open(os.path.join(inst, 'Config.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(cfg, indent=4, ensure_ascii=False) + '\n')
open(os.path.join(inst, 'Update.img'), 'wb').write(img)
back = rd(os.path.join(inst, 'Update.img'))
bfs = ext4.Ext4(lzma.decompress(fitpatch.extract(back, 'rootfs')))
test('B11 Update.img gravado e relido do disco: identico; os dois arquivos dentro dele conferem',
     back == img and bfs.cat(PS) == sync and bfs.cat(PR) == run_new, sha1(back))
test('B12 pacote de restauracao com o SHA1 oficial', sha1(rd(os.path.join(rest, 'Update.img'))) == OFFICIAL_SHA1)
open(os.path.join(outdir, 'TESTES_FIRMWARE.txt'), 'w', encoding='utf-8').write(
    '\n'.join('[%s] %s %s' % ('OK' if ok else 'FALHA', n, dt) for n, ok, dt in results) + '\n\nSHA1 Update.img: %s\n' % sha1(img))
print('\n%d testes OK. SHA1 final: %s  %d bytes' % (len(results), sha1(img), len(img)))
