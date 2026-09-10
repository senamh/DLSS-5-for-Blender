> Архив предыдущих экспериментов. Не инструкция для 0.2.0. Актуальные [установка](QUICK_START.md), [совместимость](COMPATIBILITY.md), [управление](SETTINGS.md).

# Stock Blender prototype

This experimental route requires ordinary Windows Blender 5.2+, the addon ZIP,
our bridge DLL and a separately obtained runtime. No patched Blender is required.
Native runtime testing on RTX 5070 passed for a synthetic 128x128 chart. This new
stock integration still needs actual render and interactive viewport validation.

1. Install the extension ZIP. Set runtime and bridge paths in Advanced.
2. Approve the trusted runtime, run Test Runtime, inspect its images, and allow
   experimental color processing.
3. Render with F12, then click Process Render in Render Properties > DLSS.
   The result is a separate float image named DLSS Render. Save it from Image Editor.
4. For preview, open an Image Editor beside a rendered 3D View. In the 3D View's
   sidebar, choose DLSS > Start Preview. Stop Preview or Esc ends processing.

The original render is preserved. Render postprocessing snapshots it through a
32-bit EXR and preserves alpha. It does not automatically replace render output,
process an animation, preserve multilayer passes, or install a compositor node.

Viewport processing captures the displayed framebuffer, including overlays, and
approximates inverse sRGB before processing. AgX/HDR cannot be reconstructed from
this capture. Updates are sequential and start a worker per frame, so this is not
a realtime performance claim. Runtime initialization overhead is expected.

Native processing is isolated from the artist's Blender process and times out
after 120 seconds. Temporary frame files are removed on stop. Image Editor results
remain available for saving. The patched Cycles integration remains a separate route.
