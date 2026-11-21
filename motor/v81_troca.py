"""v8.1: troca de modelo NAM sem o buraco de ~0,9 s.
uso (WSL): python3 v81_troca.py <build>/patch/nam_hook.cpp   (aplica depois de v8_nucleos.py e v8_pro.py)

Antes (v8): knob parado 150 ms -> fade-out 100 ms -> MUDO enquanto monta/aquece o modelo novo (~880 ms) -> fade-in 100 ms.
Agora: knob parado 150 ms -> monta/aquece o modelo novo EM SEGUNDO PLANO (nucleo 3) com o antigo tocando ->
fade-out 30 ms -> troca -> fade-in 30 ms. Vale tambem para LITE/FULL/AUTO e recalibracoes.
Se o knob sair do modelo preparado durante o fade, o antigo volta (sem ficar mudo).
Aquecimento sem usleep(500) por bloco; canal 2 so e aquecido se ja houve audio estereo.
Calibracao do AUTO pela mediana dos blocos (o modelo antigo toca ao lado)."""
import re
import sys

p = sys.argv[1]
s = open(p, encoding='utf-8').read()


def troca(a, b, n=1):
    global s
    c = s.count(a)
    if c != n:
        sys.exit('v81: trecho encontrado %d vezes (esperado %d): %r' % (c, n, a[:90]))
    s = s.replace(a, b)


# 1) fades curtos (continuam ajustaveis por variavel de ambiente)
troca('  return 4800; // 100ms at 48kHz\n}\n\nint32_t fade_in_len_samples()',
      '  return 1440; // [mx5-v81] 30 ms: o modelo novo ja chega pronto\n}\n\nint32_t fade_in_len_samples()')
troca('    return std::max(1, std::atoi(env));\n  return 4800; // 100ms at 48kHz\n}\n\n// ',
      '    return std::max(1, std::atoi(env));\n  return 1440; // [mx5-v81] 30 ms\n}\n\n// ')

# 2) estado: ja viu estereo?
troca('  std::atomic<int> fade_state{0};',
      '  std::atomic<int> fade_state{0};\n  std::atomic<bool> saw_stereo{false}; // [mx5-v81] so aquece o canal 2 se ja houve estereo')

# 3) aquecimento: sem usleep e canal 2 so com estereo
troca('''          for (int32_t done = 0; done < kPrewarmSamples; done += kPrewarmBlockSize)
          {
            d->process(in_arr, out_arr, kPrewarmBlockSize);
            usleep(500);
          }''',
      '''          // [mx5-v81] sem usleep: o carregamento roda fora do nucleo do audio; canal 2 so com estereo
          const int32_t warm = (i == 0 || s.saw_stereo.load(std::memory_order_relaxed)) ? kPrewarmSamples : 0;
          for (int32_t done = 0; done < warm; done += kPrewarmBlockSize)
            d->process(in_arr, out_arr, kPrewarmBlockSize);''')

# 3b) carregamento/calibracao so no nucleo 3 (o modelo antigo continua tocando no nucleo 2)
troca('''    flush_denormals_to_zero(); // brand-new thread -- see its own comment
    lower_background_thread_priority(); // ditto -- see its own comment
    try
    {
      struct Reset''',
      '''    flush_denormals_to_zero(); // brand-new thread -- see its own comment
    lower_background_thread_priority(); // ditto -- see its own comment
    { cpu_set_t c3; CPU_ZERO(&c3); CPU_SET(3, &c3); sched_setaffinity(0, sizeof(c3), &c3); } // [mx5-v81]
    try
    {
      struct Reset''')

# 4) knob parado: em vez de comecar o fade-out, prepara o modelo novo com o antigo tocando
troca('''      if (s.fade_state.load(std::memory_order_relaxed) == 0)
      {
        s.fade_state.store(1, std::memory_order_relaxed);
        s.fade_progress = 0;
      }
    }

    // Retroactive quality recalibration''',
      '''      // [mx5-v81] prepara em segundo plano; o fade-out so comeca quando o modelo novo estiver pronto
      if (s.fade_state.load(std::memory_order_relaxed) == 0 && !s.pending_ready.load(std::memory_order_acquire))
        switch_model_in_background(s, drive_raw, false);
    }

    // Retroactive quality recalibration''')

# 5) recalibracoes (LITE/FULL/AUTO, sobrecarga, nova instancia): so marcam; o refazer e em segundo plano
s, n = re.subn(r's\.force_recalibrate = true;\n\s*s\.fade_state\.store\(1, std::memory_order_relaxed\);\n\s*s\.fade_progress = 0;',
               's.force_recalibrate = true; // [mx5-v81] refeito em segundo plano, com o modelo atual tocando', s)
if n != 3:
    sys.exit('v81: recalibracoes encontradas %d (esperado 3)' % n)
troca('''    }
  }

  // Safety net against a permanent-mute trap''',
      '''    }
    if (s.force_recalibrate && s.fade_state.load(std::memory_order_relaxed) == 0
        && !s.pending_ready.load(std::memory_order_acquire) && s.active_index.load(std::memory_order_acquire) >= 0)
      switch_model_in_background(s, drive_raw, true); // [mx5-v81]
  }

  // Safety net against a permanent-mute trap''')

# 6) pickup com o antigo tocando: inicia o fade-out curto; a troca acontece no fim dele
troca('''    else if (!ready)
    {
      // First-ever load for this instance''',
      '''    else if (ready && fs_for_pickup == 0)
    {
      // [mx5-v81] modelo novo pronto e o antigo ainda tocando: fade-out curto
      s.fade_state.store(1, std::memory_order_relaxed);
      s.fade_progress = 0;
    }
    else if (!ready)
    {
      // First-ever load for this instance''')

# 7) fim do fade-out: troca direta; se o knob saiu do preparado, devolve o antigo (nunca fica mudo)
troca('''      if (current_idx == s.active_index.load(std::memory_order_acquire) && !s.force_recalibrate)
      {''',
      '''      if (s.pending_ready.load(std::memory_order_acquire) && current_idx == s.pending_index)
      {
        // [mx5-v81] troca direta: o modelo novo foi montado e aquecido enquanto o antigo tocava
        for (int i = 0; i < kMaxChannels; ++i)
          s.dsp[i] = std::move(s.pending_dsp[i]);
        s.active_index.store(s.pending_index, std::memory_order_release);
        s.pending_ready.store(false, std::memory_order_release);
        s.fade_state.store(s.pending_index < 0 ? 0 : 2, std::memory_order_relaxed);
        s.calibrated_epoch.store(g_topology_epoch.load(std::memory_order_acquire), std::memory_order_release);
        s.force_recalibrate = false;
      }
      else if (current_idx == s.active_index.load(std::memory_order_acquire) && !s.force_recalibrate)
      {
        for (int i = 0; i < kMaxChannels; ++i) // [mx5-v81] descarta um modelo preparado que nao sera usado
          s.pending_dsp[i].reset();
        s.pending_ready.store(false, std::memory_order_release);''')
troca('''        s.fade_state.store(3, std::memory_order_relaxed);
        switch_model_in_background(s, drive_raw, s.force_recalibrate);''',
      '''        // [mx5-v81] o knob saiu do modelo preparado durante o fade: descarta e devolve o antigo;
        // o pedido do alvo novo sai sozinho quando o knob parar
        for (int i = 0; i < kMaxChannels; ++i)
          s.pending_dsp[i].reset();
        s.pending_ready.store(false, std::memory_order_release);
        s.fade_state.store(s.active_index.load(std::memory_order_relaxed) < 0 ? 0 : 2, std::memory_order_relaxed);''')

# 8) marca estereo quando o audio chega com 2 canais
troca('''  const int fade_state = s.fade_state.load(std::memory_order_relaxed);
  const bool silent_active''',
      '''  if (numChannels >= 2 && input[1] && output[1] && !s.saw_stereo.load(std::memory_order_relaxed))
    s.saw_stereo.store(true, std::memory_order_relaxed); // [mx5-v81]
  const int fade_state = s.fade_state.load(std::memory_order_relaxed);
  const bool silent_active''')

# 9) calibracao do AUTO pela mediana (o modelo antigo toca ao lado; a media pegava picos de disputa)
troca('''    const auto t0 = std::chrono::steady_clock::now();
    for (int iter = 0; iter < kCalibrationIters; ++iter)
      dsp.process(in_arr, out_arr, kCalibrationBlockSize);
    const auto t1 = std::chrono::steady_clock::now();
    const double avg_us = static_cast<double>(
                             std::chrono::duration_cast<std::chrono::microseconds>(t1 - t0).count())
                           / static_cast<double>(kCalibrationIters);''',
      '''    double it_us[kCalibrationIters];
    for (int iter = 0; iter < kCalibrationIters; ++iter)
    {
      const auto t0 = std::chrono::steady_clock::now();
      dsp.process(in_arr, out_arr, kCalibrationBlockSize);
      it_us[iter] = std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - t0).count();
    }
    std::sort(it_us, it_us + kCalibrationIters); // [mx5-v81] mediana
    const double avg_us = 0.5 * (it_us[kCalibrationIters / 2 - 1] + it_us[kCalibrationIters / 2]);''')

open(p, 'w', encoding='utf-8').write(s)
print('ok v81_troca')
