#ifndef NATIVE_COMMON_H
#define NATIVE_COMMON_H
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <ctype.h>
#include <stdint.h>
typedef unsigned char uchar;
typedef unsigned long ulong;
#undef EOF
#define max(a,b) ((a)>(b)?(a):(b))
#define __maybe_unused __attribute__((unused))
extern char console_buffer[];
int set_local_var(const char*,int);
int parse_string_outer(const char*,int);
#define DECLARE_GLOBAL_DATA_PTR
#define CONFIG_SYS_CBSIZE 1024
#define CONFIG_SYS_MAXARGS 16
#define CONFIG_SYS_PROMPT "> "
#define CONFIG_SYS_PROMPT_HUSH_PS2 "> "
#define FLAG_EXIT_FROM_LOOP 1
#define FLAG_PARSE_SEMICOLON (1<<1)
#define FLAG_REPARSING (1<<2)
#define FLAG_CONT_ON_NEWLINE (1<<3)
#define CMD_FLAG_REPEAT 1
#define U_BOOT_CMD(...)
struct cmd_tbl { int unused; };
int cmd_process(int,int,char *const[],int*,unsigned long*);
char *env_get(const char*);
int env_set(const char*,const char*);
int cli_readline(const char*);
int ctrlc(void);
int had_ctrlc(void);
void clear_ctrlc(void);
void bootretry_reset_cmd_timeout(void);
#endif
