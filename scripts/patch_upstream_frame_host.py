"""Add a file-frame adapter to a pinned upstream host; preserve its NGX implementation."""
import sys
from pathlib import Path
p=Path(sys.argv[1]);s=p.read_text()
changes={
 'static int RunTest()':'#include "frame_mode.h"\n\nstatic int RunTest()',
 'bool  test = false, hide = false, behind = false;':'bool  test = false, hide = false, behind = false;',
 'if      (strcmp(argv[i], "--test") == 0) test = true;':'''if ((strcmp(argv[i], "--frame") == 0 || strcmp(argv[i], "--validate-frame") == 0) && i+3<argc)
        {
            g_validate_frame = strcmp(argv[i], "--validate-frame") == 0;
            g_frame_w = static_cast<UINT>(strtoul(argv[++i], nullptr, 10));
            g_frame_h = static_cast<UINT>(strtoul(argv[++i], nullptr, 10));
            g_frame_dir = argv[++i]; test = true;
        }
        else if (strcmp(argv[i], "--test") == 0) test = true;''',
 '    DetectRenodxAddon();   // must run BEFORE':'    if (g_validate_frame) return RunFrame();\n\n    DetectRenodxAddon();   // must run BEFORE',
 'const int rc = test ? RunTest() : Serve(pid);':'const int rc = g_frame_dir ? RunFrame() : (test ? RunTest() : Serve(pid));',
}
for old,new in changes.items():
    if s.count(old)!=1:raise ValueError('Pinned host changed: '+old[:60])
    s=s.replace(old,new)
p.write_text(s)

