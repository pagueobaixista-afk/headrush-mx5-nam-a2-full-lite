/* Camada ARMv7 para os motores A2 da tone-3000 (gerados para AArch64).
   O unico intrinsic usado que nao existe em ARMv7 e vfmaq_laneq_f32 (FMA por escalar de uma lane).
   NAM_V7_MLA=0: VFMA (fused, VFPv4) com a lane duplicada num registrador.
   NAM_V7_MLA=1: VMLA por escalar (nao fused), uma instrucao a menos por tap. */
#ifndef NAM_ARMV7_NEON_H
#define NAM_ARMV7_NEON_H
#include <arm_neon.h>
#if !defined(__aarch64__)
  #ifndef NAM_V7_MLA
    #define NAM_V7_MLA 0
  #endif
  #if NAM_V7_MLA
    #define vfmaq_laneq_f32(acc, x, w, lane) \
      vmlaq_lane_f32((acc), (x), ((lane) < 2 ? vget_low_f32(w) : vget_high_f32(w)), ((lane) & 1))
  #else
    #define vfmaq_laneq_f32(acc, x, w, lane) \
      vfmaq_f32((acc), (x), vdupq_lane_f32(((lane) < 2 ? vget_low_f32(w) : vget_high_f32(w)), ((lane) & 1)))
  #endif
#endif
#endif
