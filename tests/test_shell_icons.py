"""Host render fixtures for the launcher icon resolver; no board claim.

Run with the task's named --case flags, or without flags for all cases.
"""
import argparse
import os
from pathlib import Path
import shlex
import struct
import subprocess
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
CASES = ["theme", "theme-switch", "missing", "cache-bound", "notification-icon", "private-no-identity", "absolute", "svg"]

PROBE = r'''
#include "icon.h"
#include <gio/gdesktopappinfo.h>
#include <stdio.h>
#include <string.h>

static cairo_surface_t *target(int size, cairo_t **cr) {
  cairo_surface_t *surface=cairo_image_surface_create(CAIRO_FORMAT_ARGB32,size,size);
  *cr=cairo_create(surface);
  return surface;
}
static int painted(cairo_surface_t *surface) {
  cairo_surface_flush(surface);
  unsigned char *data=cairo_image_surface_get_data(surface);
  int stride=cairo_image_surface_get_stride(surface);
  for (int y=0;y<cairo_image_surface_get_height(surface);y++)
    for (int x=0;x<cairo_image_surface_get_width(surface);x++)
      if (data[y*stride+x*4+3]) return 1;
  return 0;
}
static int draw(GIcon *icon, enum k230_icon_use use, const char *output) {
  cairo_t *cr;
  cairo_surface_t *surface=target(64,&cr);
  int resolved=k230_icon_draw(cr,icon,use,8,8);
  if (output) cairo_surface_write_to_png(surface,output);
  int visible=painted(surface);
  cairo_destroy(cr); cairo_surface_destroy(surface);
  return resolved && visible;
}
int main(int argc,char **argv) {
  if (argc<4) return 2;
  const char *which=argv[1], *entry_path=argv[2], *output=argv[3];
  GDesktopAppInfo *app=g_desktop_app_info_new_from_filename(entry_path);
  if (!app) return 3;
  GIcon *icon=g_app_info_get_icon(G_APP_INFO(app));
  int ok=0;
  if (!strcmp(which,"theme")) ok=draw(icon,K230_ICON_DRAWER,output)
    && k230_icon_cache_count()==1 && k230_icon_decode_count()==1;
  else if (!strcmp(which,"theme-switch")) {
    ok=draw(icon,K230_ICON_DRAWER,NULL) && k230_icon_cache_count()==1;
    k230_icon_set_theme("hicolor");
    ok=ok && k230_icon_cache_count()==0 && draw(icon,K230_ICON_DRAWER,output)
      && k230_icon_decode_count()==2 && k230_icon_cache_count()==1;
    k230_icon_set_theme("../invalid");
    ok=ok && k230_icon_cache_count()==0 && draw(icon,K230_ICON_DRAWER,NULL)
      && k230_icon_decode_count()==3;
  }
  else if (!strcmp(which,"missing")) ok=!draw(icon,K230_ICON_DRAWER,output)
    && k230_icon_cache_count()==1 && !strcmp(g_app_info_get_display_name(G_APP_INFO(app)),"Missing App");
  else if (!strcmp(which,"notification-icon")) ok=draw(icon,K230_ICON_NOTIFICATION,output)
    && k230_icon_cache_count()==1;
  else if (!strcmp(which,"private-no-identity")) {
    cairo_t *a,*b;
    cairo_surface_t *first=target(64,&a),*second=target(64,&b);
    int result=k230_icon_draw(a,icon,K230_ICON_PRIVATE_CARD,8,8);
    k230_icon_draw(b,NULL,K230_ICON_PRIVATE_CARD,8,8);
    cairo_surface_flush(first); cairo_surface_flush(second);
    ok=!result && k230_icon_cache_count()==0 && k230_icon_decode_count()==0 &&
      !memcmp(cairo_image_surface_get_data(first),cairo_image_surface_get_data(second),
        cairo_image_surface_get_stride(first)*64);
    cairo_surface_write_to_png(first,output);
    cairo_destroy(a); cairo_destroy(b);
    cairo_surface_destroy(first); cairo_surface_destroy(second);
  } else if (!strcmp(which,"absolute") || !strcmp(which,"svg"))
    ok=draw(icon,K230_ICON_DRAWER,output);
  else if (!strcmp(which,"cache-bound")) {
    ok=draw(icon,K230_ICON_DRAWER,output) && draw(icon,K230_ICON_DRAWER,NULL)
      && k230_icon_decode_count()==1;
    for (int i=0;i<20;i++) {
      char name[40]; snprintf(name,sizeof name,"many-%02d",i);
      GIcon *next=g_themed_icon_new(name);
      ok=ok && draw(next,K230_ICON_DRAWER,NULL);
      g_object_unref(next);
    }
    ok=ok && k230_icon_cache_count()<=12 && k230_icon_decode_count()==21;
    k230_icon_cache_invalidate();
    ok=ok && k230_icon_cache_count()==0 && draw(icon,K230_ICON_DRAWER,NULL)
      && k230_icon_decode_count()==22;
  }
  g_object_unref(app);
  if (!ok) { fprintf(stderr,"icon case failed: %s\n",which); return 1; }
  return 0;
}
'''


def png_bytes(r, g, b):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    scan = (b"\0" + bytes([r, g, b, 255]) * 48) * 48
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 48, 48, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(scan)) + chunk(b"IEND", b""))


class IconCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.build.cleanup)
        source = Path(cls.build.name) / "probe.c"
        source.write_text(PROBE)
        cls.binary = Path(cls.build.name) / "probe"
        flags = shlex.split(subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "gio-unix-2.0", "cairo", "librsvg-2.0"], text=True))
        subprocess.run(["cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-I", str(ROOT / "nix/touch-launcher"),
                        str(source), str(ROOT / "nix/touch-launcher/icon.c"), "-o", str(cls.binary),
                        *flags, "-lm"], check=True)

    def fixture(self, root, icon_name):
        data = root / "data"
        for theme in ("cedar", "hicolor"):
            directory = data / "icons" / theme
            (directory / "48x48/apps").mkdir(parents=True)
            (directory / "scalable/apps").mkdir(parents=True)
            (directory / "index.theme").write_text(
                "[Icon Theme]\nName=" + theme + "\nDirectories=48x48/apps,scalable/apps\n"
                + ("Inherits=hicolor\n" if theme == "cedar" else "")
                + "[48x48/apps]\nSize=48\nType=Fixed\n"
                + "[scalable/apps]\nSize=48\nType=Scalable\nMinSize=16\nMaxSize=128\n")
        (data / "icons/cedar/48x48/apps/brand.png").write_bytes(png_bytes(210, 68, 58))
        (data / "icons/hicolor/48x48/apps/brand.png").write_bytes(png_bytes(35, 140, 90))
        (data / "icons/hicolor/48x48/apps/inherited.png").write_bytes(png_bytes(35, 140, 90))
        for i in range(20):
            (data / f"icons/cedar/48x48/apps/many-{i:02d}.png").write_bytes(png_bytes(i * 10, 40, 90))
        (data / "icons/cedar/scalable/apps/vector.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="#5dbfa1"/></svg>')
        entry = root / "fixture.desktop"
        entry.write_text(f"[Desktop Entry]\nType=Application\nName={'Missing App' if icon_name == 'absent' else 'Fixture'}\nExec=true\nIcon={icon_name}\n")
        env = os.environ | {"XDG_DATA_HOME": str(data), "XDG_DATA_DIRS": str(root / "empty"),
                            "K230_ICON_THEME": "cedar"}
        return entry, env

    def run_case(self, case, icon_name, copied_icon=None, themed_source=None):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            entry, env = self.fixture(root, icon_name)
            if themed_source:
                (root / "data/icons/hicolor/scalable/apps" / (icon_name + ".svg")).symlink_to(themed_source)
            if copied_icon:
                entry.write_text(entry.read_text().replace(f"Icon={icon_name}", f"Icon={copied_icon}"))
            output = root / "render.png"
            subprocess.run([self.binary, case, entry, output], env=env, check=True)
            self.assertGreater(output.stat().st_size, 80)

    def test_theme(self):
        self.run_case("theme", "brand")
        self.run_case("theme", "inherited")
        installed = {
            "foot": "/nix/store/spn1xzg7rfnffadkf4r3giv8vawgx2y3-foot-riscv64-unknown-linux-gnu-1.28.0/share/icons/hicolor/scalable/apps/foot.svg",
            "htop": "/nix/store/nyy80gvhfcalcm8g9x3fcx3bgilllj3g-htop-riscv64-unknown-linux-gnu-3.5.3/share/icons/hicolor/scalable/apps/htop.svg",
            "mpv": "/nix/store/4sx1s01fbcsjdsqs7c7smyi4ldhxqxm9-mpv-riscv64-unknown-linux-gnu-0.41.0/share/icons/hicolor/scalable/apps/mpv.svg",
        }
        for name, path in installed.items():
            if Path(path).exists():
                self.run_case("theme", name, themed_source=path)

    def test_missing(self):
        self.run_case("missing", "absent")

    def test_theme_switch(self):
        self.run_case("theme-switch", "brand")

    def test_cache_bound(self):
        self.run_case("cache-bound", "brand")

    def test_notification_icon(self):
        self.run_case("notification-icon", "brand")

    def test_private_no_identity(self):
        self.run_case("private-no-identity", "brand")

    def test_absolute(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "absolute.png"
            path.write_bytes(png_bytes(30, 100, 210))
            self.run_case("absolute", "unused", copied_icon=str(path))

    def test_svg(self):
        self.run_case("svg", "vector")
        sources = [
            "/nix/store/spn1xzg7rfnffadkf4r3giv8vawgx2y3-foot-riscv64-unknown-linux-gnu-1.28.0/share/icons/hicolor/scalable/apps/foot.svg",
            "/nix/store/nyy80gvhfcalcm8g9x3fcx3bgilllj3g-htop-riscv64-unknown-linux-gnu-3.5.3/share/icons/hicolor/scalable/apps/htop.svg",
            "/nix/store/4sx1s01fbcsjdsqs7c7smyi4ldhxqxm9-mpv-riscv64-unknown-linux-gnu-0.41.0/share/icons/hicolor/scalable/apps/mpv.svg",
        ]
        for source in sources:
            if Path(source).exists():
                self.run_case("svg", "unused", copied_icon=source)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", choices=CASES)
    chosen = parser.parse_args().case
    tests = unittest.defaultTestLoader.loadTestsFromTestCase(IconCases)
    if chosen:
        names = {"theme": "test_theme", "theme-switch": "test_theme_switch", "missing": "test_missing", "cache-bound": "test_cache_bound",
                 "notification-icon": "test_notification_icon", "private-no-identity": "test_private_no_identity",
                 "absolute": "test_absolute", "svg": "test_svg"}
        tests = unittest.TestSuite(IconCases(names[c]) for c in dict.fromkeys(chosen))
    result = unittest.TextTestRunner(verbosity=2).run(tests)
    raise SystemExit(not result.wasSuccessful())
