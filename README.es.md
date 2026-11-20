# HeadRush MX5 NAM A2 Pro (Full/Lite)

[English](README.md) | [Português](README.pt-BR.md) | **Español**

Firmware personalizado para la **HeadRush MX5 (2.7)** que ejecuta modelos **NAM (Neural Amp Modeler)**, incluidos los modelos **A2** de tamaño completo, con una lista de modelos que se mantiene sola.

Es un trabajo derivado de [lolgab/headrush-nam-mod](https://github.com/lolgab/headrush-nam-mod) (v0.1.6), con los motores A2 de [tone-3000/embedded](https://github.com/tone-3000/embedded) portados a ARMv7 NEON y la [MX5 Bridge](#fuentes-y-créditos) para acceder al equipo desde el PC.

Proyecto desarrollado y compilado con **Claude Fable 5.2** (Anthropic).

![MX-Edit en el PC](docs/mx-edit.png)

<img src="docs/mx5-v7-nam-a2.jpg" alt="Pantalla del MX5 con NAM A2 v7" width="620">

*El mismo rig en MX-Edit, en el PC, con la imagen de cada pedal, y en la pantalla del MX5 (con el pedal NAM A2).*

**Editor de PC:** [HeadRush MX5 PC Editor (fork de MX-Edit)](https://github.com/pagueobaixista-afk/MX-Edit) – se conecta al MX5 al instante en Windows 11 y muestra la imagen de cada pedal. El instalador de este proyecto ya lo incluye.

> **Aviso.** Firmware no oficial, sin vínculo con HeadRush/inMusic. Instalar firmware modificado es bajo tu propio riesgo y puede anular la garantía; los autores no se responsabilizan por daños. El repositorio y el instalador **no** contienen el firmware ni el actualizador de HeadRush: el instalador parte del actualizador oficial, descargado del sitio de inMusic en el momento. Recuperación de la MX5: mantener los footswitches 1+2 al encender e instalar el actualizador oficial 2.7 (2+3 borra los rigs).

## 🎬 Videos

- **Demo (v7):** [NAM A2 Full/Lite sonando en la HeadRush MX5](https://youtu.be/nuovUCALZjI): pantalla de inicio, menú NAM A2 y el interruptor Lite/Full.
- **Cómo instalar:** [video paso a paso](https://youtu.be/1Bj1k44fe2Y) (grabado con la v6; la v7 se instala igual y solo agrega la pregunta del arte).

## Novedades de la v8: NAM A2 Pro

**Hecho por un bajista.** La v8 saca el NAM del Anxiety OD y lo pone en un pedal con suficientes controles: el **8-Bit Crush** se convierte en el **NAM A2 Pro**. Los controles se eligieron pensando en el bajo: un blend que mantiene el grave limpio y firme debajo de la distorsión, un EQ con bandas útiles para bajo y una puerta de ruido para los modelos con más ganancia.

<img src="docs/abertura-v8.png" alt="Pantalla de inicio de la v8" width="520">

**Los controles del NAM A2 Pro, en palabras simples:**

| En la pantalla | Qué hace |
|---|---|
| **NAM LITE / FULL / AUTO** | Tamaño del modelo. **FULL** suena idéntico al NAM oficial; **LITE** pesa menos en el procesador; **AUTO** elige solo. |
| **MODEL NAM** | Elige el modelo. **1 clic de la perilla = 1 modelo.** También se puede elegir por nombre en la lista de presets. |
| **INPUT** | Cuánta señal entra al modelo: más = más saturación, como la ganancia de un amplificador. 50% = 0 dB. |
| **OUTPUT** | Volumen de salida, sin cambiar el tono. 50% = 0 dB. |
| **BLEND** | Mezcla del bajo limpio con el NAM. 100% = solo NAM. Por debajo, el grave limpio queda debajo de la distorsión, como en los pedales de drive para bajo. |
| **BASS / TREBLE** | Graves y agudos después del NAM. 50% = sin cambio. |
| **MID / MID FREQ / MID Q** | Un medio ajustable. MID en 0 dB = sin cambio. |
| **GATE** | Corta el ruido cuando no está tocando. En el mínimo queda apagada. |

**Para apagar el EQ:** se apaga solo en la posición neutra (BASS y TREBLE en 50%, MID en 0 dB), y **MID Q en 0% muestra EQ OFF** y quita todo el EQ de una vez.

**También en la v8**

- **NAM en un núcleo propio del procesador.** El MX5 tiene 4 núcleos y el audio corre en uno; ahora el NAM corre en un núcleo libre (+1 ms de latencia), dejando espacio para los demás efectos. La carga de modelos también salió del núcleo del audio: el cambio de rig es más rápido y limpio.
- **Presets por nombre, neutros.** Cada `.nam` se vuelve un preset del NAM A2 Pro con todo neutro (sin nivelado automático de volumen; usted ajusta). Los presets de fábrica del 8-Bit Crush se quitan, porque no tienen sentido para el NAM.
- **Nueva pantalla de inicio** y arte nueva para varios pedales.
- **Instalador en portugués, inglés y español**, y el editor **MX-Edit** viene **portátil**, con el arte.
- **El Anxiety OD vuelve a ser el pedal original.** Los rigs de la v7 con NAM dentro del Anxiety OD deben rehacerse con el NAM A2 Pro.

**Cómo funciona el Sync:** copie sus `.nam` a la carpeta `NAM` del MX5 y toque **Sync**. El MX5 numera solo los archivos nuevos (`NNN - nombre`) y, de 10 a 60 segundos después, la **aplicación se reinicia sola una vez** para crear los presets y corregir los rigs guardados. No es un bloqueo: no apague. Si solo copia los archivos y enciende el MX5, todo ocurre durante el arranque. El número mantiene el orden fijo: los modelos nuevos van al final y nada de lo que ya tiene cambia de lugar.

## Cómo instalar (paso a paso)

1. Vaya a **[Releases](../../releases/latest)** y descargue **`MX5_NAM_A2_v8.zip`**. Extráigalo.
2. Doble clic en **`Instalar_MX5_NAM_A2_v8.exe`** (deje la carpeta `_instalador_arquivos` al lado). Elija el idioma y el arte (1 = Starcz, 2 = de fábrica). Descarga el actualizador oficial de HeadRush 2.7 y arma el firmware (unos 2 minutos). Si Windows o el antivirus avisa, haga clic en **Más información > Ejecutar de todas formas** (no hay certificado de firma pagado; el código está aquí).
3. Conecte el MX5 a la corriente y por USB. En el MX5: **Global Settings > … > Firmware Update**.
4. Abra **`FirmwareUpdater.exe`** en la carpeta `MX5_NAM_A2_v8_ARTE_…_PRONTO_PARA_GRAVAR` y haga clic en **Instalar NAM A2 v8**. No desconecte hasta que termine.
5. Copie sus `.nam` a la carpeta **`NAM`** y toque **Sync** (vea arriba). En el MX5: **Model Selector > NAM A2**.
6. Editor en el PC: **`MX-Edit\MX-Edit.exe`** (portátil, con el arte).

**Para volver al original:** grabe el actualizador oficial de HeadRush 2.7. **Si el MX5 no arranca:** mantenga los footswitches 1+2 al encender y grabe el actualizador oficial.

## Qué tan fiel es al NAM oficial

![NAM A2 en el MX5 y en el GP-5: diferencia con el NAM oficial y tiempo de proceso](docs/nam-a2-v8.png)

**Izquierda:** cuánto difiere el sonido del NAM oficial, con el mismo modelo A2 de bajo (AGONY DG1) y el mismo DI para todos. El MX5 Full es idéntico; el Lite es una red más pequeña y difiere un poco. Como referencia, el **Valeton GP-5** con el [NAM-Loader de OpenGP5](https://github.com/OpenGP5) (firmware abierto de terceros) solo admite el A2 Lite (el Full no cabe en su procesador): 6,5% con el loader original, 1,4% con un modelo reentrenado para su frecuencia de 44,1 kHz. **Derecha:** parte de cada bloque de audio de 1 ms que ocupa el NAM en el MX5. Con los motores NEON el Full ocupa 45% y corre en vivo (en la v8, en un núcleo propio); con el motor estándar de NAM ocuparía 72% y bajaría a Lite.

Comparación directa: el mismo audio (2 s de la señal de prueba de NeuralAmpModelerCore + 10 s de bajo grabado en línea, 48 kHz) pasó por el [NeuralAmpModelerCore](https://github.com/sdatkinson/NeuralAmpModelerCore) oficial compilado en el PC y por el `libnam_hook.so` idéntico al del equipo (mismo SHA1), ejecutándose en `qemu-arm` con las bibliotecas del firmware, motor `t3k-mla`, Tone y Level en 0 dB.

| Modelo (A2) | High (Full) vs oficial | Low (Lite) vs oficial |
|---|---|---|
| Tech 21 Sansamp Bass Driver 01 | residuo -130,5 dB | -24,6 dB |
| Darkglass Fuzz - OMEGA | -134,1 dB | -26,5 dB |
| PP-DI-Only | -135,3 dB | -22,7 dB |
| B7K 6505+ Distorted Bass | -125,8 dB | -16,1 dB |

El residuo es la energía de la diferencia respecto a la señal oficial. En **Full** no hay retardo ni diferencia de nivel, y el residuo queda en el redondeo de punto flotante de 32 bits: es el mismo sonido. En **Lite** se ejecuta el submodelo reducido que viene dentro del propio `.nam`, una red más pequeña, y la diferencia es audible en los modelos de más ganancia.

Lo que esta medición no cubre: los conversores y la etapa de entrada de la MX5, y lo que va antes y después del NAM en el rig. Para repetirla: `comparacao/run.sh`.

## Camino hasta aquí

1. **Base.** NAM de lolgab (2 instancias) y MX5 Bridge 0.7 para usar MX-Edit en el PC. El build de lolgab se reprodujo byte a byte antes de cualquier cambio.
2. **v1, motores A2.** Port de los motores A2 Lite/Full de tone-3000/embedded a ARMv7 NEON (variantes `fma` y `mla`), con selección automática en el equipo e informe en `/tmp/nam_a2_report.txt`. Probado en qemu-arm y luego medido en la MX5.
3. **v2, usada en vivo.** Selector Hi-Lo como Lite/Full (byte encontrado por diferencia de memoria, `memscan.c` y `hilo_probe.py`), colapso mono, conteo de instancias, hilos de carga fuera del audio, medidor `/tmp/nam_a2_stats.txt`. Un show entero sin ningún desborde de bloque.
4. **Presets por modelo.** Presets del Anxiety OD escritos en la base SQLite del equipo vía Bridge (`ferramentas/nam_presets.py`).
5. **v3.** Sincronización al arrancar (`nam-sync.sh`, llamado desde `runevil`).
6. **v4.** Sincronización también al salir de la transferencia USB (`mount_usb_img`) y reinicio automático de la aplicación.
7. **v5.** Rigs que se corrigen solos, nivelación por loudness, descarte de `.nam` defectuosos, informe.
8. **v6.** Corrección: la aplicación reescribía la base desde la memoria al terminar su propio Sync y borraba los presets recién creados. Ahora la base solo se modifica después de que la aplicación termina (modo `deferred`), y luego se reinicia.

Descartado en el camino: releer la carpeta sin reiniciar la aplicación (riesgo para el audio) y reemplazar el Anxiety OD por otro pedal.

## Estructura

| Carpeta | Contenido |
|---|---|
| `motor/` | Parches sobre lolgab (`nam_hook.diff`, `model_cpp.diff`), motores (`t3k_a2.cpp`, `nam_armv7_neon.h`), scripts de build y prueba numerados, `harness.c`, cliente de la Bridge (`brq.py`) |
| `firmware/v3` a `v6` | `nam-sync.sh` de cada versión, scripts que arman la imagen (`build_vN.py`) y la verificación del sistema de archivos |
| `ferramentas/` | Sincronización de presets desde el PC, vía Bridge |
| `comparacao/` | Comparación con el NeuralAmpModelerCore oficial |
| `editor/` | Parche sobre [MX-Edit](https://github.com/TicT4x/MX-Edit) 0.9.5 (TicT4x, MIT): arte real de los bloques (PNG de `arte/`, misma regla de nombres del QML de la MX5) y conexión confiable (pausa de 0,3 s después de abrir el puerto MIDI: sin ella el 1.er ping se perdía 8 de 8 veces; reintentos; busca la MX5 sola hasta encontrarla) |
| `instalador/` | Instalador para principiantes: `instalar.py` aplica `payload/` (archivos nuevos, solo las líneas modificadas de los scripts de HeadRush y 38 bytes de `/usr/Evil/Evil`) al firmware oficial; `dev/make_payload.py` genera `payload/` a partir de la v6; `bridge/` son las bibliotecas de MX5 Bridge 0.7 (MIT) |

## Cómo compilar

Entorno usado: WSL Ubuntu 24.04, toolchain Bootlin `arm-buildroot-linux-gnueabihf` (glibc 2.31) en `/opt/toolchain`, `qemu-arm`, Python 3.12.

1. `motor/01_setup.sh` a `06_build.sh` descargan las fuentes, reproducen el build de lolgab, aplican los parches y generan `libnam_hook.so`. De `07_test.sh` en adelante son las pruebas.
2. `motor/build_a2.py` inserta el motor en una imagen base que ya tiene la Bridge. `firmware/vN/build_vN.py` aplica cada versión sobre la anterior y ejecuta las pruebas de armado.
3. Debes conseguir por tu cuenta el `Update.img` 2.7 original y el patcher de MX5 Bridge 0.7. Los scripts tienen rutas de mi máquina; ajústalas.

## Fuentes y créditos

- [lolgab/headrush-nam-mod](https://github.com/lolgab/headrush-nam-mod): el mod de NAM para HeadRush que sirve de base (GPLv3).
- [tone-3000/embedded](https://github.com/tone-3000/embedded) 2.0.0: motores A2 Lite/Full (MIT).
- [sdatkinson/NeuralAmpModelerCore](https://github.com/sdatkinson/NeuralAmpModelerCore): implementación de referencia de NAM (MIT).
- MX5 Bridge 0.7 y MX-Edit 0.9.5, de TicT4x: acceso al equipo por USB-MIDI y editor de PC (MIT).
- [SiulGalvan/Forge-Patch](https://github.com/SiulGalvan/Forge-Patch) ("HEADRUSH MX5 Compatibility Layer"): paquete que integra NAM, Bridge y arte; fue la base de la imagen con Bridge (GPLv3).
- [iosumurillo/GIGBOARD_NAM_AMP_PNG](https://github.com/iosumurillo/GIGBOARD_NAM_AMP_PNG): parche de arte de los pedales en pantalla (GPLv3).
- [Eigen](https://eigen.tuxfamily.org) y [nlohmann/json](https://github.com/nlohmann/json), dependencias de NAM.
- Toolchains de [Bootlin](https://toolchains.bootlin.com).

**Arte de los pedales:** las imágenes de los pedales son material de HeadRush (inMusic), integradas por iosumurillo y Forge-Patch. No forman parte de este repositorio: van aparte, en el archivo `arte_pedais.bin` del zip del Release, solo para uso en la MX5 del propio usuario. Sin ese archivo, el instalador arma el firmware sin el arte. Los titulares de derechos que quieran su retirada pueden abrir un issue; el archivo se retira inmediatamente.

HeadRush y MX5 son marcas de inMusic; este proyecto no tiene vínculo con el fabricante.

## Licencia

GPLv3, por derivar de headrush-nam-mod. Ver `LICENSE`.
