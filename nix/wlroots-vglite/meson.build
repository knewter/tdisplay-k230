vglite_dep = declare_dependency(
  include_directories: include_directories('@VGLITE_INCLUDE@'),
  link_args: ['-L@VGLITE_LIB@', '-lvg_lite'],
)
wlr_deps += vglite_dep
wlr_files += files('renderer.c')
