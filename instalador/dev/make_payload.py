"""Gera o pacote do instalador a partir do firmware oficial 2.7 e das duas v7 de referencia.

uso: python -I make_payload.py <libdir da Bridge> <Update.img oficial> <Update.img v7 arte Starcz> <Update.img v7 arte de fabrica> <saida> <v7_ferramentas>

Saida:
  <saida>/payload/manifest.json       o que muda, arquivo por arquivo, com SHA1 de antes e depois
  <saida>/payload/files/...           arquivos novos (NAM, Bridge, nam-sync)
  <saida>/payload/evil_core.bin       trechos do /usr/Evil/Evil da v7 (NAM, menu NAM A2, textos), arte de fabrica
  <saida>/payload/arte_starcz.bin     trechos do /usr/Evil/Evil com a arte Starcz (feita pelo autor do mod)
Dos scripts da HeadRush que mudam, so as linhas novas sao guardadas (nunca o arquivo inteiro)."""
import sys, os, json, lzma, hashlib, struct, difflib
lib, stock_p, v6_p, namonly_p, out, FERR = sys.argv[1:7]
sys.path.insert(0, lib)
import fitpatch, ext4

sha1 = lambda b: hashlib.sha1(b).hexdigest()
PNGSIG = bytes.fromhex('89504e470d0a1a0a')
MAGIC_CORE, MAGIC_ART = b'MX5NAMCORE1\0', b'MX5NAMARTE1\0'


def load(p):
    raw = open(p, 'rb').read()
    return ext4.Ext4(lzma.decompress(fitpatch.extract(raw, 'rootfs'))) if p.endswith('.img') else ext4.Ext4(raw)


def walk(f):
    res = {}
    def rec(n, path):
        for name, i, ft in f.listdir(n):
            if name in ('.', '..'):
                continue
            p = path + '/' + name
            mode, data = f.read(i)
            ino = f.inode(i)
            if mode & 0xF000 == 0x4000:   # pasta: o conteudo (lista de nomes) muda sozinho quando um arquivo entra
                res[p] = (mode, struct.unpack_from('<H', ino, 2)[0], struct.unpack_from('<H', ino, 0x18)[0], b'')
                rec(i, p)
            else:
                res[p] = (mode, struct.unpack_from('<H', ino, 2)[0], struct.unpack_from('<H', ino, 0x18)[0], data)
    rec(f.lookup('/'), '')
    return res


def ranges(a, b):
    """trechos [ini, fim) onde a e b diferem (mesmo tamanho), unindo vizinhos a menos de 16 bytes"""
    assert len(a) == len(b)
    r, i, n = [], 0, len(a)
    step = 1 << 16
    while i < n:
        if a[i:i + step] == b[i:i + step]:
            i += step
            continue
        end = min(n, i + step)
        j = i
        while j < end:
            if a[j] != b[j]:
                k = j
                while k < end and a[k] != b[k]:
                    k += 1
                if r and j - r[-1][1] < 16:
                    r[-1][1] = k
                else:
                    r.append([j, k])
                j = k
            else:
                j += 1
        i = end
    return r


def pack(magic, base_sha, result_sha, rs, src):
    body = b''.join(struct.pack('<II', s, e - s) + src[s:e] for s, e in rs)
    return magic + bytes.fromhex(base_sha) + bytes.fromhex(result_sha) + struct.pack('<I', len(rs)) + body


stock, v6, namonly = walk(load(stock_p)), walk(load(v6_p)), walk(load(namonly_p))
assert {p for p in v6 if v6[p] != namonly.get(p)} == {'/usr/Evil/Evil'}
os.makedirs(os.path.join(out, 'payload', 'files'), exist_ok=True)
man = {'formato': 1, 'descricao': 'MX5 NAM A2 v7 sobre o firmware oficial HeadRush MX5 2.7',
       'firmware_oficial_sha1': sha1(open(stock_p, 'rb').read()), 'arquivos': []}
for p in sorted(set(stock) | set(v6)):
    a, b = stock.get(p), v6.get(p)
    if a == b:
        continue
    assert b is not None, 'v7 removeu %s' % p
    mode, uid, gid, data = b
    assert mode & 0xF000 == 0x8000, p
    e = {'caminho': p, 'modo': mode, 'uid': uid, 'gid': gid, 'sha1': sha1(data)}
    if a is None:
        rel = 'files' + p
        os.makedirs(os.path.dirname(os.path.join(out, 'payload', rel)), exist_ok=True)
        open(os.path.join(out, 'payload', rel), 'wb').write(data)
        e.update(tipo='novo', fonte=rel)
    elif p == '/usr/Evil/Evil':
        s, n6, nn = a[3], data, namonly[p][3]
        rs = ranges(s, n6)
        # nas regioes das imagens dos pedais fica o conteudo do proprio firmware oficial (a arte de fabrica
        # nao vai no pacote): a versao "arte de fabrica" = oficial + so o codigo/textos da v7
        sys.path.insert(0, FERR)
        import qrc, v7lib, re
        known = list(v7lib.find_qml(s).keys()) + [m.start() - 4 for m in re.finditer(re.escape(PNGSIG), s)]
        reg = []
        for k, v in qrc.find_all(s, known).items():
            if k.startswith('/Pages/ModuleEditors/img/') and k.endswith('.png'):
                o = v[0]
                reg.append((o, o + 4 + max(struct.unpack_from('>I', s, o)[0], struct.unpack_from('>I', nn, o)[0])))
        nb = bytearray(nn)
        for x, y in reg:
            nb[x:y] = s[x:y]
        nn = bytes(nb)
        core, art, mid = ranges(s, nn), ranges(nn, n6), nn
        open(os.path.join(out, 'payload', 'evil_core.bin'), 'wb').write(pack(MAGIC_CORE, sha1(s), sha1(mid), core, nn))
        open(os.path.join(out, 'payload', 'arte_starcz.bin'), 'wb').write(pack(MAGIC_ART, sha1(mid), sha1(n6), art, n6))
        e.update(tipo='binario', base_sha1=sha1(s), sha1_sem_arte=sha1(mid), fonte='evil_core.bin', arte='arte_starcz.bin')
        print('Evil: %d trechos do NAM (%d bytes), %d trechos de arte (%d bytes)' % (
            len(core), sum(y - x for x, y in core), len(art), sum(y - x for x, y in art)))
    else:
        al, bl = a[3].splitlines(keepends=True), data.splitlines(keepends=True)
        ops = []
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, al, bl, autojunk=False).get_opcodes():
            if tag == 'equal':
                ops.append(['=', i2 - i1])
            else:
                if i2 > i1:
                    ops.append(['-', i2 - i1])
                if j2 > j1:
                    ops.append(['+', b''.join(bl[j1:j2]).decode('utf-8')])
        e.update(tipo='edicao', base_sha1=sha1(a[3]), base_modo=a[0], linhas=ops)
    man['arquivos'].append(e)
json.dump(man, open(os.path.join(out, 'payload', 'manifest.json'), 'w', encoding='utf-8', newline='\n'), indent=1, ensure_ascii=False)
print('%d arquivos no manifesto' % len(man['arquivos']))
