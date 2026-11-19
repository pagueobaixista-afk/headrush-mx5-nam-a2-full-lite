"""Recorta os pedais da arte nova (fundo fora, so o pedal) e encaixa na area visivel do MX5.

uso: python recorta_pedais.py <pasta origem (arte_limpa)> <pasta referencia (arte_usada_leve)> <saida> <lista.txt>

Area visivel (ActiveStomp.qml da v6): imagem com ate 230 px de altura e escalada para caber em
153x226 (127x226 nos pedais de expressao). Entao cada pedal sai exatamente do tamanho que ocupa
essa area inteira, sem margem. IR / IR2 / Other mantem as medidas atuais (a tela ajusta sozinha).
"""
import sys, os, io
try:
    import truststore; truststore.inject_into_ssl()   # certificados do Windows (antivirus inspeciona HTTPS)
except ImportError:
    pass
import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageEnhance
from rembg import remove, new_session

src, ref, out, lista = sys.argv[1:5]
nomes = [l.strip() for l in open(lista, encoding='utf-8') if l.strip()]
sess = new_session('isnet-general-use')


def fecho(pts):
    """fecho convexo (monotone chain)"""
    pts = sorted(set(map(tuple, pts)))
    if len(pts) < 3:
        return pts
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for q in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], q) <= 0: lo.pop()
        lo.append(q)
    for q in reversed(pts):
        while len(hi) >= 2 and cross(hi[-2], hi[-1], q) <= 0: hi.pop()
        hi.append(q)
    return lo[:-1] + hi[:-1]


RETANGULO = {'FX-Loop.png', 'K Drive.png', 'Tri Fuzz.png'}   # recorte automatico corta as laterais
MANTEM = {'IR.png', 'IR2.png', 'Other.png'}
os.makedirs(out, exist_ok=True)

for n in nomes:
    im = Image.open(os.path.join(src, n)).convert('RGB')
    r = Image.open(os.path.join(ref, n))
    # recorte em resolucao de trabalho (lado maior 1024) para ficar rapido e com borda limpa
    w0 = im.copy(); w0.thumbnail((1024, 1024), Image.LANCZOS)
    cut = remove(w0, session=sess, post_process_mask=True)
    a = np.asarray(cut.getchannel('A'))
    # corpo do pedal parecido com o fundo sai "comido": se a mascara cobre pouco do contorno
    # externo (fecho convexo), o contorno inteiro vira opaco (pedais sao retangulos/formas convexas)
    hull = fecho(np.argwhere(a > 40)[:, ::-1])
    hm = Image.new('L', cut.size, 0); ImageDraw.Draw(hm).polygon([tuple(map(float, q)) for q in hull], fill=255)
    hm_a = np.asarray(hm) > 0
    cobre = (a > 128)[hm_a].mean()
    if n in RETANGULO:
        ys, xs = np.where(a > 40)
        bx = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
        cut = w0.convert('RGBA').crop(bx)
        rm = Image.new('L', cut.size, 0)
        ImageDraw.Draw(rm).rounded_rectangle([0, 0, cut.size[0] - 1, cut.size[1] - 1], radius=int(min(cut.size) * 0.05), fill=255)
        cut.putalpha(rm)
        a = np.asarray(cut.getchannel('A'))
        print('   retangulo inteiro do pedal')
    elif cobre < 0.92:
        hm = hm.filter(ImageFilter.GaussianBlur(1.2))
        cut = w0.convert('RGBA'); cut.putalpha(Image.fromarray(np.maximum(a, np.asarray(hm))))   # cor original
        a = np.asarray(cut.getchannel('A'))
        print('   contorno preenchido (mascara cobria %.0f%%)' % (100 * cobre))
    ys, xs = np.where(a > 40)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    cut = cut.crop((x0, y0, x1, y1))
    pw, ph = cut.size
    if n in MANTEM:
        bw, bh = r.size
        k = min(bw / pw, bh / ph)
        fw, fh = max(1, round(pw * k)), max(1, round(ph * k))
        peca = cut.resize((fw, fh), Image.LANCZOS)
        final = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
        final.alpha_composite(peca, ((bw - fw) // 2, (bh - fh) // 2))
    else:
        bw = 127 if r.size[0] == 128 else 153     # pedais de expressao (Wham, Harm, Time Warp)
        bh = 226
        k = min(bw / pw, bh / ph)
        fw, fh = max(1, round(pw * k)), max(1, round(ph * k))
        final = cut.resize((fw, fh), Image.LANCZOS)
    # mais claro para o display (brilho +8%, contraste +5%) e leve (paleta 256 cores com transparencia)
    al = final.getchannel('A')
    rgb = ImageEnhance.Contrast(ImageEnhance.Brightness(final.convert('RGB')).enhance(1.08)).enhance(1.05)
    final = rgb.convert('RGBA'); final.putalpha(al)
    final = final.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
    b = io.BytesIO(); final.save(b, 'PNG', optimize=True)
    open(os.path.join(out, n), 'wb').write(b.getvalue())
    print('%-20s %s -> %s  (%d KB)' % (n, im.size, final.size, len(b.getvalue()) // 1024))
