"""Gera o pacote do instalador a partir do firmware oficial 2.7 e do firmware de referencia (v6).

uso: python -I make_payload.py <libdir da Bridge> <Update.img oficial> <Update.img v6> <rootfs so com NAM do lolgab> <saida>

Saida:
  <saida>/payload/manifest.json       o que muda, arquivo por arquivo, com SHA1 de antes e depois
  <saida>/payload/files/...           arquivos novos (NAM, Bridge, nam-sync)
  <saida>/payload/evil_core.bin       trechos do /usr/Evil/Evil que o NAM precisa
  <saida>/arte_pedais.bin             trechos do /usr/Evil/Evil com a arte dos pedais (vai em separado)
Dos scripts da HeadRush que mudam, so as linhas novas sao guardadas (nunca o arquivo inteiro)."""
import sys, os, json, lzma, hashlib, struct, difflib
lib, stock_p, v6_p, namonly_p, out = sys.argv[1:6]
sys.path.insert(0, lib)
import fitpatch, ext4

sha1 = lambda b: hashlib.sha1(b).hexdigest()
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
os.makedirs(os.path.join(out, 'payload', 'files'), exist_ok=True)
man = {'formato': 1, 'descricao': 'MX5 NAM A2 v6 sobre o firmware oficial HeadRush MX5 2.7',
       'firmware_oficial_sha1': sha1(open(stock_p, 'rb').read()), 'arquivos': []}
for p in sorted(set(stock) | set(v6)):
    a, b = stock.get(p), v6.get(p)
    if a == b:
        continue
    assert b is not None, 'v6 removeu %s' % p
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
        core = [r for r in rs if s[r[0]:r[1]] != nn[r[0]:r[1]]]
        art = [r for r in rs if r not in core]
        mid = bytearray(s)
        for x, y in core:
            mid[x:y] = n6[x:y]
        mid = bytes(mid)
        open(os.path.join(out, 'payload', 'evil_core.bin'), 'wb').write(pack(MAGIC_CORE, sha1(s), sha1(mid), core, n6))
        open(os.path.join(out, 'arte_pedais.bin'), 'wb').write(pack(MAGIC_ART, sha1(mid), sha1(n6), art, n6))
        e.update(tipo='binario', base_sha1=sha1(s), sha1_sem_arte=sha1(mid), fonte='evil_core.bin', arte='arte_pedais.bin')
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
