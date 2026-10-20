# Rejected isolated rotation experiments — 2026-10-19

All experiments compare the current748545c0 RGB565 rotation with a proposed
loop in separate source-built binaries, while baseline48af remains running.
The sole board lock is held. Buffers are fresh heap/unattached DRM dumb
allocations; no modesetting and no integrated or optical claim. Each variant
has three alternating12-frame rounds/transform/memory, exact destination
pixels including padding. The block transpose also passes288 guarded native
three-frame geometry cases under UBSan. None is integrated into production.

The aligned4×4 register transpose regressed DRM rotation1 from4.190ms to
7.565ms, and rotation3 from4.182ms to7.157ms (median CPU per copy). The
unchanged32-bit path stays similar. Increasing or reducing the RGB565 tile
also loses against16; the raw rows and exact generator/compiler/source are
adjacent. This is measured rejection, not a claimed theoretical speedup.

| Tile | DRM rotation1 baseline | Candidate | Result |
| --- | ---: | ---: | --- |
| 4 | 4.094ms | 5.516ms | reject |
| 8 | 4.075ms | 4.495ms | reject |
| 32 | 4.060ms | 5.582ms | reject |
| 64 | 4.084ms | 6.100ms | reject |
| 128 | 4.059ms | 5.983ms | reject |

The existing16 tile and packed64-bit stores remain unchanged. Neither failed
experiments nor synthetic copies are counted as motion acceptance.

A final function-local GCCO3/unroll-loops experiment also loses for the actual
RGB565 path: DRM rotation1 median4.069→4.411ms, rotation3 4.043→4.204ms.
The unchanged source's32-bit loop does improve under these compiler options
(12.060→8.749ms and11.168→7.870ms), but that is not the selected panel format.
The experiment is rejected for this change; production compilation is unchanged.
Sources/compiler command/timestamps/raw rows are in compiler-o3/.
