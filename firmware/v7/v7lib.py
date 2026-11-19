import re, struct, zlib

def find_qml(b):
    found = {}
    for m in re.finditer(rb'import Qt', b):
        for back in range(0, 6000):
            p = m.start() - back - 4
            L = struct.unpack_from('>I', b, p)[0]
            if back < L < 400000 and p + 4 + L <= len(b):
                d = b[p + 4:p + 4 + L]
                if all(32 <= c < 127 or c in (9, 10, 13) for c in d[:back + 20]) and d.count(b'\x00') == 0:
                    found[p] = ('raw', d, L)
                    break
    for m in re.finditer(rb'\x78[\x9c\xda\x01]', b):
        p = m.start() - 8
        if p < 0:
            continue
        L = struct.unpack_from('>I', b, p)[0]; U = struct.unpack_from('>I', b, p + 4)[0]
        if 6 < L < 500000 and 0 < U < 4000000:
            try:
                d = zlib.decompress(bytes(b[p + 8:p + 4 + L]))
            except Exception:
                continue
            if len(d) == U and b'import Qt' in d[:3000]:
                found[p] = ('zlib', d, L)
    return found



def strip_tokens(s):
    s = re.sub(r'"(?:[^"\n\\]|\\.)*"', '""', s)
    s = re.sub(r"'(?:[^'\n\\]|\\.)*'", "''", s)
    return re.sub(r'\s+', '', s)

def sem_comentarios(s):
    """tira comentarios // (fora dos literais) e linhas vazias"""
    linhas = []
    for li in s.split('\n'):
        partes, last = [], 0
        for m in re.finditer(r'"(?:[^"\n\\]|\\.)*"|\'(?:[^\'\n\\]|\\.)*\'|//.*$', li):
            partes.append(li[last:m.start()])
            if not m.group().startswith('//'):
                partes.append(m.group())
            last = m.end()
        partes.append(li[last:])
        li = ''.join(partes).rstrip(' \t')
        if li.strip():
            linhas.append(li)
    return '\n'.join(linhas)


def squeeze(nb, comentarios=False):
    """Tira indentacao e junta espacos repetidos FORA dos literais de texto (nao muda o significado).
    comentarios=True: tira tambem os comentarios // e as linhas vazias."""
    s = nb.decode('utf-8')
    if comentarios:
        s0, s = s, sem_comentarios(s)
        assert '/*' not in s0 and strip_tokens(s) == strip_tokens(sem_comentarios(s0))
    linhas = []
    for li in s.split('\n'):
        partes, last = [], 0
        for m in re.finditer(r'"(?:[^"\n\\]|\\.)*"|\'(?:[^\'\n\\]|\\.)*\'|//.*$', li):
            partes.append(re.sub(r'[ \t]+', ' ', li[last:m.start()])); partes.append(m.group()); last = m.end()
        partes.append(re.sub(r'[ \t]+', ' ', li[last:]))
        linhas.append(''.join(partes).strip(' \t'))
    out = '\n'.join(linhas)
    assert strip_tokens(out) == strip_tokens(s)
    return out.encode('utf-8')


