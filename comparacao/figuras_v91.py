"""figuras_v91.py : figuras didaticas da v9.1 para o README (pt, en, es) em docs/v91/.
Numeros medidos no aparelho (ver README): troca de modelo v8 = 150 ms de espera + 100 ms de fade + 883 ms mudo + 100 ms
de fade (1,23 s); v9.1 = ~18 ms sem mudo (321 trocas); ataque do drop 12 ms (fabrica) x 2,5 ms (Drop Starcz);
IR de fabrica usa so as primeiras 2048 amostras (43 ms a 48 kHz)."""
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'docs', 'v91')
os.makedirs(OUT, exist_ok=True)
SURF, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e4e3df'
BLUE, ORANGE, AQUA, YELLOW = '#2a78d6', '#eb6834', '#1baf7a', '#eda100'
BLUE_L = '#9ec5f4'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11, 'text.color': INK, 'axes.labelcolor': INK2,
                     'xtick.color': INK2, 'ytick.color': INK2, 'axes.edgecolor': GRID, 'figure.facecolor': SURF,
                     'axes.facecolor': SURF, 'savefig.facecolor': SURF})

T = {
 'pt': dict(
  troca_t='Trocar de modelo NAM no meio da música', troca_x='tempo depois de girar o botão (ms)',
  troca_rows=['v8', 'v9.1'], esp='espera o botão parar', fade='fade', mudo='SILÊNCIO (monta o modelo novo)',
  troca_v91='modelo novo já estava pronto: troca em ~18 ms, sem silêncio', troca_tot='som novo em 1,23 s',
  drop_t='Drop: quanto a nota demora para sair depois da palhetada', drop_x='atraso do ataque (ms, menor é melhor)',
  drop_rows=['Drop Tune de fábrica', 'Drop Starcz (v9.1)'],
  ir_t='Um IR longo (ex.: gabinete com sala / reverb) - ilustração', ir_x='tempo (segundos)', ir_y='nível (dB)',
  ir_a='o MX5 de fábrica toca só isto\n(2048 amostras = 43 ms)', ir_b='a v9.1 toca o arquivo inteiro (até 12 s)',
  cores_t='Como os 4 núcleos do processador trabalham na v9.1',
  cores=[('Núcleo 0', 'tela e sistema', 'igual à fábrica'),
         ('Núcleo 1', 'cadeia de efeitos do MX5', 'inclui o Drop Starcz'),
         ('Núcleo 2', 'NAM (só ele)', 'desde a v8'),
         ('Núcleo 3', 'modelos prontos + cauda do IR', 'NOVO na v9.1 (antes ficava parado)')],
  flow_t='Dentro do Drop Starcz', flow=['Baixo', 'DROP\ndesce 1 a 12\nsemitons', 'TIMBRE\ncorpo / médios', 'TCHUG\nataque mais\nforte', 'TIGHT\ncorta o grave\nsolto', 'LEVEL\nvolume', 'Saída'],
 ),
 'en': dict(
  troca_t='Changing the NAM model in the middle of a song', troca_x='time after turning the knob (ms)',
  troca_rows=['v8', 'v9.1'], esp='waits for the knob', fade='fade', mudo='SILENCE (building the new model)',
  troca_v91='new model was already ready: switch in ~18 ms, no silence', troca_tot='new sound at 1.23 s',
  drop_t='Drop: how long the note takes to come out after you pick', drop_x='attack delay (ms, lower is better)',
  drop_rows=['Stock Drop Tune', 'Drop Starcz (v9.1)'],
  ir_t='A long IR (e.g. cab with room / reverb) - illustration', ir_x='time (seconds)', ir_y='level (dB)',
  ir_a='the stock MX5 plays only this\n(2048 samples = 43 ms)', ir_b='v9.1 plays the whole file (up to 12 s)',
  cores_t='How the 4 processor cores work in v9.1',
  cores=[('Core 0', 'screen and system', 'same as stock'),
         ('Core 1', 'MX5 effects chain', 'includes Drop Starcz'),
         ('Core 2', 'NAM (only NAM)', 'since v8'),
         ('Core 3', 'ready models + IR tail', 'NEW in v9.1 (it used to sit idle)')],
  flow_t='Inside the Drop Starcz', flow=['Bass', 'DROP\n1 to 12\nsemitones down', 'TIMBRE\nbody / mids', 'TCHUG\nstronger\nattack', 'TIGHT\ncuts loose\nlow end', 'LEVEL\nvolume', 'Out'],
 ),
 'es': dict(
  troca_t='Cambiar el modelo NAM en medio de la canción', troca_x='tiempo después de girar el botón (ms)',
  troca_rows=['v8', 'v9.1'], esp='espera el botón', fade='fade', mudo='SILENCIO (arma el modelo nuevo)',
  troca_v91='el modelo nuevo ya estaba listo: cambio en ~18 ms, sin silencio', troca_tot='sonido nuevo en 1,23 s',
  drop_t='Drop: cuánto tarda la nota en salir después de la púa', drop_x='retraso del ataque (ms, menos es mejor)',
  drop_rows=['Drop Tune de fábrica', 'Drop Starcz (v9.1)'],
  ir_t='Un IR largo (ej.: gabinete con sala / reverb) - ilustración', ir_x='tiempo (segundos)', ir_y='nivel (dB)',
  ir_a='el MX5 de fábrica toca solo esto\n(2048 muestras = 43 ms)', ir_b='la v9.1 toca el archivo entero (hasta 12 s)',
  cores_t='Cómo trabajan los 4 núcleos del procesador en la v9.1',
  cores=[('Núcleo 0', 'pantalla y sistema', 'igual que de fábrica'),
         ('Núcleo 1', 'cadena de efectos del MX5', 'incluye el Drop Starcz'),
         ('Núcleo 2', 'NAM (solo él)', 'desde la v8'),
         ('Núcleo 3', 'modelos listos + cola del IR', 'NUEVO en la v9.1 (antes quedaba parado)')],
  flow_t='Dentro del Drop Starcz', flow=['Bajo', 'DROP\nbaja 1 a 12\nsemitonos', 'TIMBRE\ncuerpo / medios', 'TCHUG\nataque más\nfuerte', 'TIGHT\ncorta el grave\nsuelto', 'LEVEL\nvolumen', 'Salida'],
 ),
}


def limpa(ax):
    for s in ('top', 'right', 'left'):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)


def troca(L, t):
    fig, ax = plt.subplots(figsize=(10, 3.2))
    segs = [(0, 150, BLUE_L, t['esp']), (150, 100, BLUE, t['fade']), (250, 883, ORANGE, t['mudo']), (1133, 100, BLUE, t['fade'])]
    for x0, w, c, lab in segs:
        ax.barh(1, w, left=x0 + 1, height=0.5, color=c, edgecolor=SURF, linewidth=2)
    ax.text(250 + 883 / 2, 1, t['mudo'], ha='center', va='center', color='white', fontsize=10, fontweight='bold')
    ax.text(75, 1.42, t['esp'], ha='center', va='bottom', color=INK2, fontsize=9)
    for xc in (200, 1183):
        ax.text(xc, 1.42, t['fade'], ha='center', va='bottom', color=INK2, fontsize=9)
    ax.text(1240, 1, t['troca_tot'], ha='left', va='center', color=INK, fontsize=10)
    ax.barh(0, 18, left=1, height=0.5, color=AQUA, edgecolor=SURF, linewidth=2)
    ax.text(40, 0, t['troca_v91'], ha='left', va='center', color=INK, fontsize=10)
    ax.set_yticks([1, 0], t['troca_rows'], fontsize=12, fontweight='bold')
    ax.set_xlim(0, 1500); ax.set_ylim(-0.6, 1.8)
    ax.set_xlabel(t['troca_x']); ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True)
    ax.set_title(t['troca_t'], loc='left', fontsize=14, fontweight='bold', pad=12)
    limpa(ax); fig.tight_layout(); fig.savefig(os.path.join(OUT, 'troca_%s.png' % L), dpi=130); plt.close(fig)


def drop(L, t):
    fig, ax = plt.subplots(figsize=(10, 2.6))
    vals = [12.0, 2.5]
    ax.barh([1, 0], vals, height=0.5, color=[INK2, BLUE], edgecolor=SURF, linewidth=2)
    for y, v in zip([1, 0], vals):
        ax.text(v + 0.25, y, ('%.1f ms' % v).replace('.', ',' if L != 'en' else '.'), va='center', fontsize=12, fontweight='bold')
    ax.set_yticks([1, 0], t['drop_rows'], fontsize=11)
    ax.set_xlim(0, 15); ax.set_xlabel(t['drop_x']); ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True)
    ax.set_title(t['drop_t'], loc='left', fontsize=14, fontweight='bold', pad=12)
    limpa(ax); fig.tight_layout(); fig.savefig(os.path.join(OUT, 'drop_%s.png' % L), dpi=130); plt.close(fig)


def ir(L, t):
    fs = 2000; tt = np.arange(int(1.6 * fs)) / fs
    rng = np.random.default_rng(3)
    env = 20 * np.log10(np.exp(-tt / 0.22) * (0.75 + 0.25 * rng.random(len(tt))) + 1e-6)
    env[:20] = np.linspace(0, -6, 20) + 2 * rng.random(20)
    fig, ax = plt.subplots(figsize=(10, 3.6))
    ax.fill_between(tt, -70, env, color=BLUE_L, linewidth=0)
    m = tt <= 0.043
    ax.fill_between(tt[m], -70, env[m], color=ORANGE, linewidth=0)
    ax.annotate(t['ir_a'], xy=(0.02, -20), xytext=(0.12, -8), fontsize=10, color=INK,
                arrowprops=dict(arrowstyle='->', color=INK2))
    ax.text(0.55, -30, t['ir_b'], fontsize=11, color=INK, fontweight='bold')
    ax.set_xlim(0, 1.6); ax.set_ylim(-70, 5)
    ax.set_xlabel(t['ir_x']); ax.set_ylabel(t['ir_y']); ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True)
    ax.set_title(t['ir_t'], loc='left', fontsize=14, fontweight='bold', pad=12)
    limpa(ax); fig.tight_layout(); fig.savefig(os.path.join(OUT, 'ir_%s.png' % L), dpi=130); plt.close(fig)


def cores(L, t):
    fig, ax = plt.subplots(figsize=(10, 3.4)); ax.set_xlim(0, 100); ax.set_ylim(0, 40); ax.axis('off')
    cols = [GRID, BLUE_L, BLUE, AQUA]
    for i, (nome, oque, nota) in enumerate(t['cores']):
        x = 1 + i * 24.8
        ax.add_patch(FancyBboxPatch((x, 4), 23, 26, boxstyle='round,pad=0.4,rounding_size=1.5', fc=cols[i], ec='none'))
        dark = i >= 2
        ax.text(x + 11.5, 26, nome, ha='center', va='center', fontsize=12, fontweight='bold', color='white' if dark else INK)
        ax.text(x + 11.5, 17, oque, ha='center', va='center', fontsize=10, color='white' if dark else INK, wrap=True)
        ax.text(x + 11.5, 8.5, nota, ha='center', va='center', fontsize=8.5, color='white' if dark else INK2, style='italic')
    ax.text(0, 37, t['cores_t'], fontsize=14, fontweight='bold', va='center')
    fig.tight_layout(); fig.savefig(os.path.join(OUT, 'nucleos_%s.png' % L), dpi=130); plt.close(fig)


def fluxo(L, t):
    n = len(t['flow']); fig, ax = plt.subplots(figsize=(11, 2.7)); ax.set_xlim(0, 100); ax.set_ylim(0, 30); ax.axis('off')
    w = 100 / n
    for i, s in enumerate(t['flow']):
        x = i * w + 0.8; end = i in (0, n - 1)
        ax.add_patch(FancyBboxPatch((x, 5), w - 3.2, 16, boxstyle='round,pad=0.3,rounding_size=1.2',
                                    fc=GRID if end else ('#3a5a2a' if i == 1 else BLUE), ec='none'))
        ax.text(x + (w - 3.2) / 2, 13, s, ha='center', va='center', fontsize=9.5, color=INK if end else 'white',
                fontweight='bold' if end else 'normal')
        if i < n - 1:
            ax.add_patch(FancyArrowPatch((x + w - 3.0, 13), (x + w + 0.6, 13), arrowstyle='-|>', mutation_scale=12, color=INK2))
    ax.text(0, 27, t['flow_t'], fontsize=14, fontweight='bold', va='center')
    fig.tight_layout(); fig.savefig(os.path.join(OUT, 'drop_fluxo_%s.png' % L), dpi=130); plt.close(fig)


for L, t in T.items():
    troca(L, t); drop(L, t); ir(L, t); cores(L, t); fluxo(L, t)
print('ok', sorted(os.listdir(OUT)))
