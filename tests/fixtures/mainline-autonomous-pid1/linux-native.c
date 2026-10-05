/* Host adapters only: setup dispatch models kernel __setup registration.
 * The tokenizer, parse_args, setup handlers, repair and argv append are exact
 * selected source excerpts; other pre-- kernel handlers are deliberately inert.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <stdbool.h>
#include <errno.h>
#include <stdint.h>
#define __init
#define MAX_INIT_ARGS 32
#define BUG() abort()
#define pr_debug(...) ((void)0)
#define pr_warn(...) abort()
#define pr_err(...) abort()
#define ERR_PTR(x) ((void*)(intptr_t)(x))
typedef short s16;
struct kernel_param { int unused; };
typedef int (*parse_unknown_fn)(char*,char*,const char*,void*);
static char *argv_init[MAX_INIT_ARGS+2]={"init"};
static char *panic_later,*panic_param,*execute_command,*ramdisk_execute_command;
static bool ramdisk_execute_command_set;
static char *skip_spaces(char *s) { while(isspace((unsigned char)*s))s++;return s; }
static int irqs_disabled(void) { return 0; }
static int init_setup(char*);
static int rdinit_setup(char*);
static int parse_one(char *p,char *v,const char *d,const struct kernel_param *k,
 unsigned n,s16 lo,s16 hi,void *a,parse_unknown_fn cb) {
 if(cb) return cb(p,v,d,a);
 if(!strcmp(p,"init")) return init_setup(v)==1?0:1;
 if(!strcmp(p,"rdinit")) return rdinit_setup(v)==1?0:1;
 return 0;
}
#include "linux-selected-functions.h"
int main(void) {
 char data[2048];size_t n=fread(data,1,sizeof(data)-1,stdin);data[n]=0;
 argv_init[1]="discard-before-init";
 char *rest=parse_args("Booting kernel",data,NULL,0,-1,-1,NULL,NULL);
 if(!rest || (intptr_t)rest<0) return 2;
 parse_args("Setting init args",rest,NULL,0,-1,-1,NULL,set_init_arg);
 if(panic_later || !ramdisk_execute_command_set || !execute_command) return 3;
 fprintf(stderr,"init=%s rdinit=%s rdinit_set=%u\n",execute_command,ramdisk_execute_command,ramdisk_execute_command_set);
 for(unsigned i=1;argv_init[i];i++){fwrite(argv_init[i],1,strlen(argv_init[i]),stdout);fputc(0,stdout);}
 return 0;
}
