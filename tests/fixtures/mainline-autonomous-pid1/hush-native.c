/* Native capture hooks, not U-Boot hardware or environment persistence. */
#include "cli_hush-v2022.10.c"
static unsigned commands, lookups, writes, expansions;
static char *captured;
char console_buffer[CONFIG_SYS_CBSIZE + 1];
char *env_get(const char *key) { lookups++; if(strcmp(key,"IFS")) expansions++; return NULL; }
int env_set(const char *k,const char *v) { writes++; return 0; }
int cli_readline(const char *p) { abort(); }
int ctrlc(void) { return 0; }
int had_ctrlc(void) { return 0; }
void clear_ctrlc(void) {}
void bootretry_reset_cmd_timeout(void) {}
int cmd_process(int flags,int argc,char *const argv[],int *repeat,unsigned long *ticks) {
 commands++;
 fprintf(stderr,"dispatch=%s argc=%d\n",argc ? argv[0] : "",argc);
 if(argc != 3 || strcmp(argv[0],"setenv") || strcmp(argv[1],"bootargs")) return 1;
 free(captured); captured=strdup(argv[2]); return 0;
}
int main(int argc, char **argv) {
 char data[2048]; size_t n=fread(data,1,sizeof(data)-1,stdin); data[n]=0;
 if(argc == 3) {
  if(strlen(argv[1])!=32 || strspn(argv[1],"0123456789abcdef")!=32 || strcmp(data,argv[2])) { fprintf(stderr,"rejected-before-parser\n");return 64; }
 } else if(argc != 1) return 64;
 u_boot_hush_start(); unsigned initial=lookups;
 int rc=parse_string_outer(data,FLAG_PARSE_SEMICOLON|FLAG_EXIT_FROM_LOOP);
 fprintf(stderr,"rc=%d commands=%u lookups=%u writes=%u expansions=%u\n",rc,commands,lookups-initial,writes,expansions);
 if(captured) fwrite(captured,1,strlen(captured),stdout);
 return rc || commands!=1 || writes || expansions || !captured;
}
