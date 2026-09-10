> Архив предыдущих экспериментов. Не инструкция для 0.2.0. Актуальные [установка](QUICK_START.md), [совместимость](COMPATIBILITY.md), [управление](SETTINGS.md).

# Controlled runtime comparison — 2026-09-08

GPU: RTX 5070. Evidence: Actions run 34202085424. Input: one actual Cycles
viewport capture from run 34201377466, SHA256
`92145d79285679b66cb7b42ec444ca846e92d6ee2e9d8d2869d5e988a2258a72`.

Each case ran in a new stock Blender process through the same native bridge
and DISPLAY_LINEAR codec. Preset 0, local tone/structure 1, skin default,
automask 0, zero guides, independent frames. These are our test settings,
not verified settings from the video's RenoDX UI.

| Runtime | SHA256 | Source |
| --- | --- | --- |
| Current SF-v2 | `6eb209e764f39872625debd6abaf45e2bb6322f6f270f781f70c059ae30b3927` | RankFTW/rhi-repo release dlssnr-310.8.SF-v2 |
| Video archive | `4b8d19bc3eff58a084f5eca7489c921501c203450169fb82ff4f649a4482ba05` | The pinned archive documented in VIDEO_REFERENCE_AUDIT.md |

Unlike the earlier static audit, both DLLs were now executed in isolated
processes. Neither replaced an installed runtime. No installer or RenoDX addon
from the video archive was executed.

| Style | Intensity | Mean RGB absolute change | Best-fit brightness gain | Residual after gain |
| --- | --- | --- | --- | --- |
| 0 | 1 | 0.00582435 | 1.002817 | 0.00538843 |
| 1 | 1 | 0.05810362 | 0.773547 | 0.01646645 |
| 0 | 0 | 0.00020935 | 0.999230 | 0.00009885 |

All six cases executed successfully. Corresponding output float arrays from
the two runtimes were exactly equal, verified with numpy.array_equal, for all
three setting pairs. This supports equivalence on these tested inputs through
our bridge, not universal binary or model equivalence.

The previous hardcoded style 1 visibly darkens this scene; changing runtime
alone cannot solve that. Style 0 largely preserves overall brightness. The
intensity-zero control is near identity, with small encoding/FP16 errors.
Residual changes cannot by themselves establish improved detail or relighting.

## Limits

This is a noisy material test with small objects, not a character/skin/hair
quality benchmark. The complete reference RenoDX pipeline was not executed.
There is no evidence here for equivalence to the video, interactive frame
rates, or temporal quality. No new runtime should be advertised as solving
those gaps based on this comparison.

The screenshot capture implementation briefly exposes the original during
each capture. Manual snapshot refresh is therefore the default; continuous
capture is explicitly experimental and may flicker. True seamless integration
still needs a source-frame path that does not toggle visible output.
