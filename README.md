# HeadRush MX5 NAM A2 Pro (Full/Lite)

**English** | [Português](README.pt-BR.md) | [Español](README.es.md)

Custom firmware for the **HeadRush MX5 (2.7)** that runs **NAM (Neural Amp Modeler)** models, including full-size **A2** models, with a model list that maintains itself.

It is a derivative of [lolgab/headrush-nam-mod](https://github.com/lolgab/headrush-nam-mod) (v0.1.6), with the A2 engines from [tone-3000/embedded](https://github.com/tone-3000/embedded) ported to ARMv7 NEON, plus the [MX5 Bridge](#sources-and-credits) for accessing the unit from a PC.

Project developed and built with **Claude Fable 5.2** (Anthropic).

![MX-Edit on the PC](docs/mx-edit.png)

<img src="docs/mx5-v7-nam-a2.jpg" alt="MX5 screen with NAM A2 v7" width="620">

*The same rig in MX-Edit on the PC, with the picture of each pedal, and on the MX5 screen (with the NAM A2 pedal).*

**PC editor:** [HeadRush MX5 PC Editor (MX-Edit fork)](https://github.com/pagueobaixista-afk/MX-Edit) – connects to the MX5 right away on Windows 11 and shows the picture of each pedal. The installer of this project already includes it.

> **Disclaimer.** Unofficial firmware, not affiliated with HeadRush/inMusic. Flashing modified firmware is at your own risk and may void your warranty; the authors are not responsible for any damage. This repository and the installer do **not** contain HeadRush firmware or the HeadRush updater: the installer starts from the official updater, downloaded from the inMusic website at install time. MX5 recovery: hold footswitches 1+2 while powering on and flash the official 2.7 updater (2+3 erases your rigs).

## 🎬 Videos

- **Demo (v7):** [NAM A2 Full/Lite playing on the HeadRush MX5](https://youtu.be/nuovUCALZjI): boot screen, NAM A2 menu and the Lite/Full switch.
- **How to install:** [step-by-step video](https://youtu.be/1Bj1k44fe2Y) (recorded with v6; v7 installs the same way and only adds the art question).

## What's new in v8: NAM A2 Pro

**Made by a bass player.** v8 moves NAM out of the Anxiety OD and into a pedal with enough knobs: the **8-Bit Crush** becomes **NAM A2 Pro**. The controls were picked for bass: a blend that keeps the clean low end tight under the distortion, an EQ with useful bass bands, and a gate for high-gain models.

<img src="docs/abertura-v8.png" alt="v8 boot screen" width="520">

**NAM A2 Pro controls, in plain words:**

| On the screen | What it does |
|---|---|
| **NAM LITE / FULL / AUTO** | Model size. **FULL** sounds identical to official NAM; **LITE** is lighter on the processor; **AUTO** picks by itself. |
| **MODEL NAM** | Picks the model. **1 knob click = 1 model.** You can also pick by name in the presets list. |
| **INPUT** | How much signal goes into the model: more = more saturation, like an amp's gain. 50% = 0 dB. |
| **OUTPUT** | Output volume, without changing the tone. 50% = 0 dB. |
| **BLEND** | Mix of clean bass and NAM. 100% = only NAM. Below that, the clean low end stays under the distortion, like bass drive pedals. |
| **BASS / TREBLE** | Low and high EQ after NAM. 50% = no change. |
| **MID / MID FREQ / MID Q** | An adjustable mid band. MID at 0 dB = no change. |
| **GATE** | Cuts noise when you are not playing. At minimum it is off. |

**Turning the EQ off:** the EQ switches itself off at the neutral position (BASS and TREBLE at 50%, MID at 0 dB), and **MID Q at 0% shows EQ OFF** and bypasses the whole EQ at once.

**Also in v8**

- **NAM on its own processor core.** The MX5 has 4 cores and the audio runs on one; NAM now runs on a free core (+1 ms of latency), leaving room for the other effects. Model loading also moved off the audio core: rig changes are faster and cleaner.
- **Presets by name, neutral.** Each `.nam` becomes a NAM A2 Pro preset with everything neutral (no automatic volume leveling; you set it). The 8-Bit Crush factory presets are removed, since they make no sense for NAM.
- **New boot screen**, and new art for several pedals.
- **Installer in Portuguese, English and Spanish**, and the **MX-Edit** PC editor ships **portable** with the art.
- **The Anxiety OD is the stock pedal again.** v7 rigs that had NAM inside the Anxiety OD must be rebuilt with NAM A2 Pro.

**How Sync works:** copy your `.nam` files to the `NAM` folder on the MX5 drive and tap **Sync**. The MX5 numbers new files by itself (`NNN - name`), and 10 to 60 seconds later the **app restarts by itself once** to create the presets and fix saved rigs. It is not a freeze: do not power off. If you just copy files and power on, it all happens during boot. Numbers keep the order fixed: new models go to the end and nothing you already have moves.

## How to install (step by step)

1. Go to **[Releases](../../releases/latest)** and download **`MX5_NAM_A2_v8.zip`**. Extract it.
2. Double-click **`Instalar_MX5_NAM_A2_v8.exe`** (keep the `_instalador_arquivos` folder next to it). Pick the language and the art (1 = Starcz, 2 = factory). It downloads the official HeadRush 2.7 updater and builds the firmware (about 2 minutes). If Windows or your antivirus warns, click **More info > Run anyway** (no paid code-signing certificate; the source is here).
3. Plug the MX5 into power and USB. On the MX5: **Global Settings > … > Firmware Update**.
4. Open **`FirmwareUpdater.exe`** in the `MX5_NAM_A2_v8_ARTE_…_PRONTO_PARA_GRAVAR` folder ("ready to flash") and click **Instalar NAM A2 v8**. Do not disconnect until it finishes.
5. Copy your `.nam` files to the **`NAM`** folder and tap **Sync** (see above). On the MX5: **Model Selector > NAM A2**.
6. PC editor: **`MX-Edit\MX-Edit.exe`** (portable, art included).

**To go back to stock:** flash the official HeadRush 2.7 updater. **If the MX5 does not boot:** hold footswitches 1+2 while powering on and flash the official updater.

## How faithful it is to official NAM

Direct comparison: the same audio (2 s of the NeuralAmpModelerCore test signal + 10 s of DI bass, 48 kHz) was run through the official [NeuralAmpModelerCore](https://github.com/sdatkinson/NeuralAmpModelerCore) built on a PC and through the `libnam_hook.so` identical to the one on the unit (same SHA1), running under `qemu-arm` with the firmware's libraries, `t3k-mla` engine, Tone and Level at 0 dB.

![NAM A2 on the MX5: sound difference from official NAM, and processing time used](docs/nam-a2-v8.png)

**Left:** how much of the sound differs from official NAM, with the same A2 bass model (AGONY DG1) and the same DI for everyone. MX5 Full is identical; Lite is a smaller network and differs a little. For reference, the **Valeton GP-5** running the open third-party [OpenGP5 NAM-Loader](https://github.com/OpenGP5) only fits A2 Lite (Full does not fit its processor): 6.5% with the stock loader, 1.4% with a model retrained for its 44.1 kHz rate. **Right:** share of each 1 ms audio block that NAM takes on the MX5. With the NEON engines Full takes 45% and runs live (in v8 on its own core). The grey bars are the standard NAM engine (the unmodified [NeuralAmpModelerCore](https://github.com/sdatkinson/NeuralAmpModelerCore), as used by earlier MX5 NAM mods): Full would take 72%, too much to run safely, so A2 models fall back to Lite with it.

Exact numbers:

| Model (A2) | High (Full) vs official | Low (Lite) vs official |
|---|---|---|
| Tech 21 Sansamp Bass Driver 01 | residual -130.5 dB | -24.6 dB |
| Darkglass Fuzz - OMEGA | -134.1 dB | -26.5 dB |
| PP-DI-Only | -135.3 dB | -22.7 dB |
| B7K 6505+ Distorted Bass | -125.8 dB | -16.1 dB |

Residual is the energy of the difference from the official output. In **Full** there is no delay or level difference, and the residual is at 32-bit floating-point rounding: it is the same sound. **Lite** runs the reduced submodel shipped inside the `.nam` itself, a smaller network, and the difference is audible on higher-gain models.

What this measurement does not cover: the MX5's converters and input stage, and whatever comes before and after NAM in the rig. To reproduce: `comparacao/run.sh`.

## How we got here

1. **Base.** lolgab's NAM (2 instances) and MX5 Bridge 0.7 to use MX-Edit on the PC. lolgab's build was reproduced byte for byte before any change.
2. **v1, A2 engines.** Port of the A2 Lite/Full engines from tone-3000/embedded to ARMv7 NEON (`fma` and `mla` variants), with automatic selection on the unit and a report at `/tmp/nam_a2_report.txt`. Tested in qemu-arm and then measured on the MX5.
3. **v2, used live.** Hi-Lo switch as the Lite/Full selector (byte found by memory diffing, `memscan.c` and `hilo_probe.py`), mono collapse, instance count, loading threads off the audio path, `/tmp/nam_a2_stats.txt` meter. A whole show without a single block overrun.
4. **Per-model presets.** Anxiety OD presets written to the unit's SQLite database via the Bridge (`ferramentas/nam_presets.py`).
5. **v3.** Sync at boot (`nam-sync.sh`, called from `runevil`).
6. **v4.** Sync also when leaving USB transfer (`mount_usb_img`) and automatic app restart.
7. **v5.** Self-fixing rigs, loudness leveling, discarding broken `.nam` files, report.
8. **v6.** Fix: when finishing its own Sync, the app rewrote the database from memory and wiped the freshly created presets. Now the database is only changed after the app finishes (`deferred` mode), and then the app is restarted.

Dropped along the way: rescanning the folder without restarting the app (risk to audio) and replacing the Anxiety OD with another pedal.

## Layout

| Folder | Contents |
|---|---|
| `motor/` | Patches on top of lolgab (`nam_hook.diff`, `model_cpp.diff`), engines (`t3k_a2.cpp`, `nam_armv7_neon.h`), numbered build and test scripts, `harness.c`, Bridge client (`brq.py`) |
| `firmware/v3` to `v6` | `nam-sync.sh` for each version, scripts that build the image (`build_vN.py`) and the filesystem check |
| `ferramentas/` | Preset sync from the PC, via Bridge |
| `comparacao/` | Comparison against the official NeuralAmpModelerCore |
| `editor/` | Patch on [MX-Edit](https://github.com/TicT4x/MX-Edit) 0.9.5 (TicT4x, MIT): real block artwork (PNGs from `arte/`, same naming rule as the MX5 QML) and reliable connection (0.3 s pause after opening the MIDI port: without it the first ping was lost 8 out of 8 times; retries; keeps searching for the MX5 until found) |
| `instalador/` | Beginner-friendly installer: `instalar.py` applies `payload/` (new files, only the changed lines of HeadRush scripts, and 38 bytes of `/usr/Evil/Evil`) to the official firmware; `dev/make_payload.py` generates `payload/` from v6; `bridge/` holds the MX5 Bridge 0.7 libraries (MIT) |

## How to build

Environment used: WSL Ubuntu 24.04, Bootlin toolchain `arm-buildroot-linux-gnueabihf` (glibc 2.31) in `/opt/toolchain`, `qemu-arm`, Python 3.12.

1. `motor/01_setup.sh` through `06_build.sh` fetch the sources, reproduce lolgab's build, apply the patches and produce `libnam_hook.so`. `07_test.sh` onward are the tests.
2. `motor/build_a2.py` inserts the engine into a base image that already has the Bridge. `firmware/vN/build_vN.py` applies each version on top of the previous one and runs the build tests.
3. You must supply the original 2.7 `Update.img` and the MX5 Bridge 0.7 patcher yourself. The scripts contain paths from my machine; adjust them.

## Sources and credits

- [lolgab/headrush-nam-mod](https://github.com/lolgab/headrush-nam-mod): the HeadRush NAM mod this is based on (GPLv3).
- [tone-3000/embedded](https://github.com/tone-3000/embedded) 2.0.0: A2 Lite/Full engines (MIT).
- [sdatkinson/NeuralAmpModelerCore](https://github.com/sdatkinson/NeuralAmpModelerCore): NAM reference implementation (MIT).
- MX5 Bridge 0.7 and MX-Edit 0.9.5, by TicT4x: USB-MIDI access to the unit and PC editor (MIT).
- [SiulGalvan/Forge-Patch](https://github.com/SiulGalvan/Forge-Patch) ("HEADRUSH MX5 Compatibility Layer"): package integrating NAM, Bridge and artwork; it was the basis of the image with the Bridge (GPLv3).
- [iosumurillo/GIGBOARD_NAM_AMP_PNG](https://github.com/iosumurillo/GIGBOARD_NAM_AMP_PNG): on-screen pedal artwork patch (GPLv3).
- [Eigen](https://eigen.tuxfamily.org) and [nlohmann/json](https://github.com/nlohmann/json), NAM dependencies.
- Toolchains from [Bootlin](https://toolchains.bootlin.com).

**Pedal artwork:** the pedal images are HeadRush (inMusic) material, integrated by iosumurillo and Forge-Patch. They are not part of this repository: they ship separately, as `arte_pedais.bin` in the Release zip, only for use on the user's own MX5. Without that file, the installer builds the firmware without the artwork. Rights holders who want it removed can open an issue; the file will be taken down immediately.

HeadRush and MX5 are trademarks of inMusic; this project is not affiliated with the manufacturer.

## License

GPLv3, as a derivative of headrush-nam-mod. See `LICENSE`.
