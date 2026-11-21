"""Le as tabelas de recursos Qt (rcc) embutidas num binario: devolve {caminho: (offset_abs, flags)}.
offset_abs aponta para o prefixo de tamanho (4 bytes BE) do recurso; flags & 1 = comprimido (zlib)."""
import re, struct


def qt_hash(name):
    h = 0
    for ch in name:
        h = ((h << 4) + ord(ch)) & 0xFFFFFFFF
        h ^= (h & 0xF0000000) >> 23
        h &= 0x0FFFFFFF
    return h


def _name(b, N, off):
    ln, hs = struct.unpack_from('>HI', b, N + off)
    s = b[N + off + 6:N + off + 6 + 2 * ln].decode('utf-16-be', 'replace')
    return s, hs


def parse_tree(b, S, esz):
    """le a arvore a partir de S; devolve lista de entradas brutas ou None"""
    def ent(i):
        o = S + i * esz
        name_off, flags = struct.unpack_from('>IH', b, o)
        if flags & 2:
            cnt, first = struct.unpack_from('>II', b, o + 6)
            return (name_off, flags, cnt, first)
        cl, dof = struct.unpack_from('>II', b, o + 6)
        return (name_off, flags, None, dof)
    root = ent(0)
    if root[0] != 0 or not root[1] & 2 or root[3] != 1 or not (0 < root[2] < 5000):
        return None
    ents, todo, n = {}, [0], 0
    while todo:
        i = todo.pop()
        e = ent(i)
        ents[i] = e
        n += 1
        if n > 20000:
            return None
        if e[1] & 2:
            if not (0 <= e[2] < 5000) or e[3] < 1:
                return None
            todo += list(range(e[3], e[3] + e[2]))
    return ents


def find_all(b, known):
    known = sorted(set(known))
    out = {}
    for esz in (22, 14):
        pat = re.compile(rb'\x00\x00\x00\x00\x00\x02(....)\x00\x00\x00\x01', re.S)
        for m in pat.finditer(b):
            S = m.start()
            if S % 4:
                continue
            ents = parse_tree(b, S, esz)
            if not ents or len(ents) < 3:
                continue
            files = [e for e in ents.values() if not e[1] & 2]
            if not files:
                continue
            # tabela de nomes: termina perto do inicio da arvore; acha N testando o hash dos nomes
            maxn = max(e[0] for e in ents.values())
            N = None
            # busca N: o nome de maior offset tem de ser valido com hash certo
            for N0 in range(S - maxn - 6, max(0, S - maxn - 6 - 512 * 1024), -2):
                if N0 < 0:
                    continue
                try:
                    s, hs = _name(b, N0, maxn)
                except Exception:
                    continue
                if s and qt_hash(s) == hs and N0 + maxn + 6 + 2 * len(s) <= S:
                    try:
                        ok = all(qt_hash(_name(b, N0, e[0])[0]) == _name(b, N0, e[0])[1] for e in list(ents.values())[1:50])
                    except Exception:
                        ok = False
                    if ok:
                        N = N0
                        break
            if N is None:
                continue
            # dados: terminam antes de N; acha D pelo arquivo de maior offset
            from collections import Counter
            votes = Counter(pk - e[3] for e in files for pk in known if pk - e[3] >= 0)
            D = None
            offs = sorted(set(e[3] for e in files))

            def chain_score(D0):
                # o rcc grava os dados em sequencia: [tamanho][dados][tamanho][dados]...
                ok = 0
                for a, b2 in zip(offs, offs[1:]):
                    if D0 + a + 4 > len(b):
                        return -1
                    L = struct.unpack_from('>I', b, D0 + a)[0]
                    ok += (a + 4 + L == b2)
                return ok / max(1, len(offs) - 1)
            best = None
            cands = votes.most_common(30) if len(offs) > 20 else votes.most_common()
            for D0, nv in cands:
                sc = chain_score(D0)
                if best is None or sc > best[1]:
                    best = (D0, sc)
            if best and best[1] >= 0.95 and len(offs) > 1:
                D = best[0]
            if D is None:
                continue
            # caminhos
            par = {}
            for i, e in ents.items():
                if e[1] & 2:
                    for c in range(e[3], e[3] + e[2]):
                        par[c] = i
            def path(i):
                parts = []
                while i != 0:
                    parts.append(_name(b, N, ents[i][0])[0])
                    i = par[i]
                return '/' + '/'.join(reversed(parts))
            for i, e in ents.items():
                if not e[1] & 2:
                    out[path(i)] = (D + e[3], e[1], S)
    return out
