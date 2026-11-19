"""MX5 NAM A2 - instalador.

Monta, no seu computador, o firmware MX5 NAM A2 v7 a partir do atualizador OFICIAL da HeadRush 2.7.
Uso: de dois cliques no instalador (baixa o atualizador oficial do site da inMusic) ou arraste o
atualizador oficial (.exe/.zip) que voce ja tem para cima dele.

Duas opcoes: arte Starcz (pedais e tela de abertura desenhados para o mod) ou arte original de fabrica
(as imagens ficam as do proprio firmware oficial). Opcoes de linha de comando: --starcz / --fabrica."""
import hashlib, json, lzma, os, shutil, struct, sys, tempfile

FROZEN = getattr(sys, 'frozen', False)
HERE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.dirname(os.path.abspath(sys.executable)) if FROZEN else os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'bridge'))
import patcher, ext4, fitpatch, xzblocks, bridgepatch   # do MX5 Bridge 0.7 (TicT4x, licenca MIT)

VERSAO = 'v7'
PAYLOAD = os.path.join(HERE, 'payload')
SAIDA = 'MX5_NAM_A2_%s_%s_PRONTO_PARA_GRAVAR'
MAGIC_CORE, MAGIC_ART = b'MX5NAMCORE1\0', b'MX5NAMARTE1\0'
sha1 = lambda b: hashlib.sha1(b).hexdigest()


class Falha(Exception):
    pass


def diga(*a):
    print(' '.join(str(x) for x in a), flush=True)


def aplica_trechos(dados, blob, magic):
    if blob[:12] != magic:
        raise Falha('arquivo de trechos invalido')
    base, res, n = blob[12:32].hex(), blob[32:52].hex(), struct.unpack_from('<I', blob, 52)[0]
    if sha1(dados) != base:
        raise Falha('o programa do MX5 nao e o esperado para este pacote')
    out, i = bytearray(dados), 56
    for _ in range(n):
        off, ln = struct.unpack_from('<II', blob, i)
        out[off:off + ln] = blob[i + 8:i + 8 + ln]
        i += 8 + ln
    out = bytes(out)
    if sha1(out) != res:
        raise Falha('conferencia do programa do MX5 falhou')
    return out


def aplica_edicao(texto, linhas):
    src, out, i = texto.splitlines(keepends=True), [], 0
    for op in linhas:
        if op[0] == '=':
            out += src[i:i + op[1]]
            i += op[1]
        elif op[0] == '-':
            i += op[1]
        else:
            out.append(op[1].encode('utf-8'))
    if i != len(src):
        raise Falha('edicao nao bate com o script original')
    return b''.join(out)


def grava_no_lugar(fs, path, new):
    """arquivo do mesmo tamanho: sobrescreve os blocos que ele ja ocupa (o /usr/Evil/Evil e grande
    demais para o write_file da Bridge)"""
    ino = fs.inode(fs.lookup(path))
    if fs._size(ino) != len(new):
        raise Falha('tamanho inesperado de %s' % path)
    if not struct.unpack_from('<I', ino, 0x20)[0] & 0x80000:   # EXTENTS_FL
        raise Falha('formato inesperado de %s' % path)
    runs = fs._extents(ino[0x28:0x28 + 60])   # le arvores de qualquer profundidade (so leitura)
    coberto = bytearray(len(new))
    for lblk, pblk, ln in sorted(runs):
        chunk = new[lblk * fs.bs:(lblk + ln) * fs.bs]
        fs.d[pblk * fs.bs:pblk * fs.bs + len(chunk)] = chunk
        coberto[lblk * fs.bs:lblk * fs.bs + len(chunk)] = b'\1' * len(chunk)
    # trechos sem bloco (arquivo esparso) leem como zeros: o conteudo novo tambem tem de ser zero ali
    i = coberto.find(0)
    while i >= 0:
        j = coberto.find(1, i)
        j = len(new) if j < 0 else j
        if new[i:j].strip(b'\0'):
            raise Falha('mudanca em trecho esparso de %s' % path)
        i = coberto.find(0, j)


def plano(fs, arte):
    man = json.load(open(os.path.join(PAYLOAD, 'manifest.json'), encoding='utf-8'))
    files = {}
    for e in man['arquivos']:
        p = e['caminho']
        if e['tipo'] == 'novo':
            data = open(os.path.join(PAYLOAD, e['fonte']), 'rb').read()
        else:
            atual = fs.cat(p)
            if sha1(atual) != e['base_sha1']:
                raise Falha('%s nao e o do firmware oficial 2.7' % p)
            if e['tipo'] == 'edicao':
                data = aplica_edicao(atual, e['linhas'])
            else:
                data = aplica_trechos(atual, open(os.path.join(PAYLOAD, e['fonte']), 'rb').read(), MAGIC_CORE)
                if arte:
                    data = aplica_trechos(data, arte, MAGIC_ART)
        esperado = e['sha1'] if (e['tipo'] != 'binario' or arte) else e['sha1_sem_arte']
        if sha1(data) != esperado:
            raise Falha('conferencia de %s falhou' % p)
        files[p] = (data, e['modo'], e['uid'], e['gid'])
    return man, files


# Recursos Qt do /usr/Evil/Evil (mesmo lugar no oficial, v6 e v7) (SHA1 conferido antes): (tabela de nomes, arvore, dados)
_RCC = ((44006720, 44035336, 25610928), (44021288, 44044000, 30005624), (44024240, 44046096, 36734176))


def exporta_arte_editor(evil, pasta):
    """Copia as imagens 'Pages/ModuleEditors/img/*.png' (pedais, Amp/, Cab/) do programa do MX5
    para a pasta de arte do MX-Edit, com o nome do bloco/modelo."""
    import zlib
    n = 0
    for ns, tree, data in _RCC:
        rec = lambda i: evil[tree + 22 * i:tree + 22 * i + 22]
        def nome(i):
            off = ns + struct.unpack_from('>I', rec(i), 0)[0]
            ln = struct.unpack_from('>H', evil, off)[0]
            return evil[off + 6:off + 6 + 2 * ln].decode('utf-16-be')
        def anda(i, caminho):
            nonlocal n
            fl = struct.unpack_from('>H', rec(i), 4)[0]
            nm = nome(i) if i else ''
            p = caminho + '/' + nm if i else ''
            if fl & 2:
                c, f = struct.unpack_from('>II', rec(i), 6)
                for k in range(c):
                    anda(f + k, p)
            elif '/ModuleEditors/img/' in p and p.endswith('.png'):
                off = data + struct.unpack_from('>I', rec(i), 10)[0]
                d = evil[off + 4:off + 4 + struct.unpack_from('>I', evil, off)[0]]
                if fl & 1:
                    d = zlib.decompress(d[4:])
                if d[:8] != b'\x89PNG\r\n\x1a\n':
                    raise Falha('imagem invalida: %s' % p)
                rel = p.split('/ModuleEditors/img/')[1]
                dest = os.path.join(pasta, *rel.split('/'))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                open(dest, 'wb').write(d)
                n += 1
        anda(0, '')
    return n


def monta(raw, arte):
    if not fitpatch.verify(raw):
        raise Falha('o Update.img oficial esta danificado')
    diga('Abrindo o sistema de arquivos do firmware oficial ...')
    fs = ext4.Ext4(lzma.decompress(fitpatch.extract(raw, 'rootfs')))
    fs.check()
    man, files = plano(fs, arte)
    if sha1(raw) != man['firmware_oficial_sha1']:
        raise Falha('este nao e o firmware oficial HeadRush MX5 2.7 (use o atualizador baixado do site da HeadRush)')
    diga('Gravando %d arquivos ...' % len(files))
    for p, (data, mode, uid, gid) in files.items():
        if p == '/usr/Evil/Evil':
            grava_no_lugar(fs, p, data)
        else:
            fs.write_file(p, data, mode, uid, gid)
    img = fs.finish()
    chk = ext4.Ext4(img)
    chk.check()
    for p, (data, mode, uid, gid) in files.items():
        m, got = chk.read(chk.lookup(p))
        if got != data or m != mode:
            raise Falha('conferencia final de %s falhou' % p)
    diga('Tudo conferido. Comprimindo (leva um ou dois minutos) ...')
    xz = xzblocks.compress(img)
    if lzma.decompress(xz) != img:
        raise Falha('conferencia da compressao falhou')
    new = fitpatch.replace_image(raw, 'rootfs', xz)
    if arte:
        new = fitpatch.replace_image(new, 'splash', open(os.path.join(PAYLOAD, 'splash_starcz.xz'), 'rb').read())
    if not fitpatch.verify(new):
        raise Falha('conferencia da imagem final falhou')
    return new, files


def main():
    diga('MX5 NAM A2 %s - instalador (nao oficial; use por sua conta e risco)\n' % VERSAO)
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    src = args[0] if args else None
    if '--fabrica' in sys.argv:
        esc = '2'
    elif '--starcz' in sys.argv:
        esc = '1'
    else:
        diga('Qual arte voce quer?\n'
             '  1 = arte Starcz: pedais e tela de abertura novos, desenhados para o mod (recomendado)\n'
             '  2 = arte original de fabrica da HeadRush (so o NAM A2 e os menus novos)')
        try:
            esc = input('Digite 1 ou 2 e aperte Enter [1]: ').strip() or '1'
        except EOFError:
            esc = '1'
    arte = open(os.path.join(PAYLOAD, 'arte_starcz.bin'), 'rb').read() if esc != '2' else None
    nome_arte = 'ARTE_STARCZ' if arte else 'ARTE_ORIGINAL'
    diga('Arte: %s\n' % ('Starcz' if arte else 'original de fabrica'))
    work = tempfile.mkdtemp(prefix='mx5nam_')
    try:
        if not src:
            m = bridgepatch.model('mx5')
            src = os.path.join(BASE, patcher.updater_name(m))
            if os.path.exists(src):
                diga('Usando o atualizador oficial ja baixado: %s' % os.path.basename(src))
            else:
                patcher.say = diga
                patcher.download(src, m)
        if not os.path.exists(src):
            raise Falha('arquivo nao encontrado: %s' % src)
        diga('Abrindo o atualizador oficial ...')
        folder = patcher.unpack(os.path.abspath(src), work)
        new, files = monta(open(os.path.join(folder, 'Update.img'), 'rb').read(), arte)
        if True:
            pasta_arte = os.path.join(BASE, 'MX-Edit', 'arte')
            n = exporta_arte_editor(files['/usr/Evil/Evil'][0], pasta_arte)
            diga('Arte do editor: %d imagens em %s' % (n, pasta_arte))
        out = os.path.join(BASE, SAIDA % (VERSAO, nome_arte))
        os.makedirs(out, exist_ok=True)
        open(os.path.join(out, 'Update.img'), 'wb').write(new)
        cfg_p = os.path.join(folder, 'Config.json')
        cfg = json.loads(open(cfg_p, encoding='utf-8-sig').read())
        cfg['config']['appName'] = 'HeadRush MX5 v2.7 + NAM A2 %s (nao oficial)' % VERSAO
        cfg['config']['startButtonText'] = 'Instalar NAM A2 %s' % VERSAO
        open(os.path.join(out, 'Config.json'), 'w', encoding='utf-8', newline='\n').write(
            json.dumps(cfg, indent=4, ensure_ascii=False) + '\n')
        for name in patcher.UPDATER_FILES:
            shutil.copy(os.path.join(folder, name), os.path.join(out, name))
    except (Falha, patcher.Fail, ext4.Ext4Error, OSError) as e:
        diga('\nERRO: %s' % e)
        return 1
    finally:
        shutil.rmtree(work, ignore_errors=True)
    diga('\nPRONTO: %s\n' % out)
    diga('Para gravar:\n'
         '  1. Ligue o MX5 na tomada e no computador pelo USB.\n'
         '  2. No MX5: Global Settings > ... > Firmware Update.\n'
         '  3. Abra FirmwareUpdater.exe nessa pasta e clique em "Instalar NAM A2 %s".\n'
         '     Nao desconecte ate terminar.\n'
         'Para voltar ao original: grave o atualizador oficial da HeadRush 2.7.\n'
         'Para ter a outra arte: rode o instalador de novo e escolha a outra opcao.\n'
         'Se o MX5 nao ligar: segure os footswitches 1 e 2 ao ligar e grave o atualizador oficial.' % VERSAO)
    return 0


if __name__ == '__main__':
    rc = main()
    if FROZEN:
        try:
            input('\nAperte Enter para fechar.')
        except EOFError:
            pass
    sys.exit(rc)
