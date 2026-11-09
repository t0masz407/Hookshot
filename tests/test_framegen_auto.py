"""Frame generation's Auto: as many frames a game frame as fill the display's refresh, changed only when it settles.

The real auto_cap, multiplier and auto_multiplier of gpu/vk/vk_framegen.cpp, with the display's refresh and the game's
frame time set by the fixture: 45 fps on 60 Hz makes 2x and on 120 Hz 3x, 60 fps on 60 Hz none, the most is the
refresh over 30 fps (2x to 4x), a new multiplier waits for 30 game frames asking for it, and an unknown refresh counts
as 60 Hz.
python -I -B tests/test_framegen_auto.py [--cxx g++]
"""
import argparse
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def block(text, marker):
    start = text.index(marker)
    end = text.index("{", start) + 1
    depth = 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


PREFIX = r'''#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); std::exit(1); } } while (0)
constexpr int kMaxMult = 8;
struct { int framegen = 1; } opts;
struct { int64_t game_ns = 0; int auto_m = 0, auto_want = 0, auto_count = 0; } fg;
static int refresh_mhz = 60000;
int display_refresh_mhz() { return refresh_mhz; }
static int logged;
void logf(const char*, ...) { logged++; }
'''

MAIN = r'''
static void reset(int mhz, double game_fps) {
    refresh_mhz = mhz;
    fg = {};
    fg.game_ns = (int64_t)(1e9 / game_fps);
}
static int settle(int frames) {
    int m = 0;
    for (int i = 0; i < frames; i++) m = auto_multiplier(auto_cap());
    return m;
}
int main() {
    reset(60000, 45);
    CHECK(auto_cap() == 2 && multiplier() == 2);        /* 60 Hz: two images a set at most */
    CHECK(settle(1) == 2);                              /* 45 fps on 60 Hz: 2x */
    reset(120000, 45);
    CHECK(auto_cap() == 4);
    CHECK(settle(1) == 3);                              /* 45 fps on 120 Hz: 3x (135 shown, the display's 120 filled) */
    reset(60000, 60);
    CHECK(settle(1) == 1);                              /* 60 fps on 60 Hz: none made */
    reset(60000, 59);
    CHECK(settle(1) == 1);                              /* (just under: still none, the 0.15 margin) */
    reset(144000, 36);
    CHECK(auto_cap() == 4 && settle(1) == 4);           /* 144 Hz, 36 fps: 4x */
    reset(240000, 30);
    CHECK(auto_cap() == 4 && settle(1) == 4);           /* the most is 4x, whatever the refresh */
    reset(0, 45);
    CHECK(auto_cap() == 2 && settle(1) == 2);           /* unknown refresh: as 60 Hz */

    reset(120000, 45);
    CHECK(settle(1) == 3);
    fg.game_ns = (int64_t)(1e9 / 70);                   /* the game speeds up to 70 fps: 2x is enough */
    logged = 0;
    CHECK(settle(29) == 3);                             /* not before 30 frames ask for it */
    CHECK(settle(1) == 2 && logged == 1);
    fg.game_ns = (int64_t)(1e9 / 45);                   /* a single slow frame and back: no change */
    CHECK(auto_multiplier(auto_cap()) == 2);
    fg.game_ns = (int64_t)(1e9 / 70);
    CHECK(settle(40) == 2);

    opts.framegen = 3;
    CHECK(multiplier() == 3);                           /* a fixed setting is not Auto's */
    opts.framegen = 0;
    CHECK(multiplier() == 1);
    std::printf("PASS: Auto fills the display's refresh and changes only once it settles\n");
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    a = p.parse_args()
    source = (ROOT / "gpu" / "vk" / "vk_framegen.cpp").read_text(encoding="utf-8")
    fixture = PREFIX + "\n".join(block(source, m) for m in ("int auto_cap()", "int multiplier()", "int auto_multiplier(")) + MAIN
    with tempfile.TemporaryDirectory(prefix="framegen-auto-") as tmp:
        cpp = Path(tmp) / "fixture.cpp"
        exe = Path(tmp) / "fixture"
        cpp.write_text(fixture, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
