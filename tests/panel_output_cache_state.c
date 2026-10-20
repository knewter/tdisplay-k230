#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pixman.h>
static bool alloc_fail, image_fail;
static unsigned allocations, releases;
static void *allocate(size_t n) {if(alloc_fail)return NULL;allocations++;void*p=malloc(n);assert(p);memset(p,0xc7,n);return p;}
static void release(void*p){releases++;free(p);}
static pixman_image_t *test_image(pixman_format_code_t f,int w,int h,uint32_t*p,int s){if(image_fail)return NULL;return pixman_image_create_bits_no_clear(f,w,h,p,s);}
#define K230_OUTPUT_ALLOC allocate
#define K230_OUTPUT_FREE release
#define K230_OUTPUT_IMAGE test_image
#include "output-cache.h"
int main(void){
 struct k230_output_cache c={0};bool preserved=true;
 assert(k230_output_cache_begin(&c,32,20,PIXMAN_r5g6b5,1,&preserved));assert(!preserved);
 void *data=c.data;k230_output_cache_submitted(&c,true);
 assert(k230_output_cache_begin(&c,32,20,PIXMAN_r5g6b5,1,&preserved));assert(preserved&&data==c.data);
 assert(k230_output_cache_begin(&c,32,20,PIXMAN_r5g6b5,1,&preserved));assert(!preserved); /* interrupted */
 k230_output_cache_submitted(&c,false);
 assert(k230_output_cache_begin(&c,32,20,PIXMAN_r5g6b5,1,&preserved));assert(!preserved);
 k230_output_cache_submitted(&c,true);k230_output_cache_invalidate(&c);
 assert(k230_output_cache_begin(&c,32,20,PIXMAN_r5g6b5,1,&preserved));assert(!preserved);
 k230_output_cache_submitted(&c,true);
 assert(k230_output_cache_begin(&c,32,20,PIXMAN_r5g6b5,3,&preserved));assert(!preserved);
 assert(k230_output_cache_begin(&c,20,32,PIXMAN_r5g6b5,3,&preserved));assert(!preserved);
 assert(k230_output_cache_begin(&c,20,32,PIXMAN_x8r8g8b8,3,&preserved));assert(!preserved);
 assert(!k230_output_cache_begin(&c,0,32,PIXMAN_x8r8g8b8,3,&preserved));assert(!preserved);
 assert(!k230_output_cache_begin(&c,20,32,PIXMAN_a8,3,&preserved));assert(!preserved);
 assert(!k230_output_cache_begin(&c,16384,16384,PIXMAN_x8r8g8b8,3,&preserved));
 alloc_fail=true;assert(!k230_output_cache_begin(&c,40,32,PIXMAN_r5g6b5,3,&preserved));assert(!c.image&&!c.data);alloc_fail=false;
 image_fail=true;assert(!k230_output_cache_begin(&c,40,32,PIXMAN_r5g6b5,3,&preserved));assert(!c.image&&!c.data);image_fail=false;
 assert(k230_output_cache_begin(&c,40,32,PIXMAN_r5g6b5,3,&preserved));assert(!preserved);
 k230_output_cache_finish(&c);k230_output_cache_finish(&c);assert(allocations==releases);
 puts("PASS retained output lifecycle: keys, failed/interrupted/fallback passes, allocation/image failure and balanced teardown");
}
