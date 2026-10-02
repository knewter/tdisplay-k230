#!/usr/bin/env python3
"""Compile exact patched clock/PM bodies with fault-injecting host clock stubs."""
import pathlib
import re
import subprocess
import sys
import tempfile

source = pathlib.Path(sys.argv[1]).read_text()
functions = []
for name in ('dwcmshc_enable_clks', 'dwcmshc_disable_clks', 'dwcmshc_suspend', 'dwcmshc_resume'):
    match = re.search(r'^static (?:int|void) ' + name + r'\([^;]+?\)\n\{', source, re.M)
    if not match:
        raise ValueError(f'missing actual function {name}')
    end = match.end()
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    functions.append(source[match.start():end])

stubs = r'''
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
struct clk { int index, enabled; };
struct clk_bulk_data { const char *id; struct clk *clk; };
struct sdhci_pltfm_host { struct clk *clk; };
struct dwcmshc_priv { struct clk *bus_clk; struct clk_bulk_data extra_clks[3]; };
struct device { int unused; };
struct sdhci_host { int unused; };
static struct clk clocks[5];
static struct sdhci_pltfm_host platform;
static struct dwcmshc_priv private;
static struct sdhci_host host;
static int failed_clock = -1, resume_error, suspend_error;
static int clk_prepare_enable(struct clk *clk) {
    if (clk->index == failed_clock) return -EIO;
    assert(clk->enabled == 0); clk->enabled++; return 0;
}
static void clk_disable_unprepare(struct clk *clk) {
    assert(clk->enabled == 1); clk->enabled--;
}
static int clk_bulk_prepare_enable(int count, struct clk_bulk_data *bulk) {
    for (int i = 0; i < count; i++) {
        int ret = clk_prepare_enable(bulk[i].clk);
        if (ret) {
            while (i--) clk_disable_unprepare(bulk[i].clk);
            return ret;
        }
    }
    return 0;
}
static void clk_bulk_disable_unprepare(int count, struct clk_bulk_data *bulk) {
    while (count--) clk_disable_unprepare(bulk[count].clk);
}
static struct sdhci_host *dev_get_drvdata(struct device *dev) { (void)dev; return &host; }
static struct sdhci_pltfm_host *sdhci_priv(struct sdhci_host *h) { (void)h; return &platform; }
static struct dwcmshc_priv *sdhci_pltfm_priv(struct sdhci_pltfm_host *p) { (void)p; return &private; }
static int sdhci_resume_host(struct sdhci_host *h) { (void)h; return resume_error; }
static int sdhci_suspend_host(struct sdhci_host *h) { (void)h; return suspend_error; }
'''
main = r'''
static void check_counts(int expected) {
    for (int i = 0; i < 5; i++) assert(clocks[i].enabled == expected);
}
int main(void) {
    struct device dev = {0};
    for (int i = 0; i < 5; i++) clocks[i].index = i;
    platform.clk = &clocks[0]; private.bus_clk = &clocks[1];
    for (int i = 0; i < 3; i++) private.extra_clks[i].clk = &clocks[i + 2];
    for (failed_clock = 0; failed_clock < 5; failed_clock++) {
        assert(dwcmshc_enable_clks(&platform, &private) == -EIO); check_counts(0);
        assert(dwcmshc_resume(&dev) == -EIO); check_counts(0);
    }
    failed_clock = -1; resume_error = -EIO;
    assert(dwcmshc_resume(&dev) == -EIO); check_counts(0);
    resume_error = 0;
    assert(dwcmshc_resume(&dev) == 0); check_counts(1);
    suspend_error = -EIO;
    assert(dwcmshc_suspend(&dev) == -EIO); check_counts(1);
    suspend_error = 0;
    assert(dwcmshc_suspend(&dev) == 0); check_counts(0);
    assert(dwcmshc_enable_clks(&platform, &private) == 0); check_counts(1);
    dwcmshc_disable_clks(&platform, &private); check_counts(0);
    puts("actual clock/PM bodies: five enable failures, host resume failure, suspend failure and successful cycles passed");
    return 0;
}
'''
base = pathlib.Path(__file__).resolve().parents[3] / '.scratch' / 'sd1-clocks'
base.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='lifecycle.', dir=base) as run:
    path = pathlib.Path(run)
    c = path / 'check.c'; exe = path / 'check'
    c.write_text(stubs + '\n'.join(functions) + main)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
