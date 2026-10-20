#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pixman.h>
static bool allocation_failure;
static unsigned allocations, releases;
static void *allocate(size_t n,size_t size){if(allocation_failure)return NULL;void*p=calloc(n,size);if(p)allocations++;return p;}
static void release(void*p){releases++;free(p);}
#define CARD_INTERIOR_CALLOC allocate
#define CARD_INTERIOR_FREE release
#include "opaque-interior.h"
#include "rounded-clip.h"
struct registration {pixman_image_t*image;bool fail;unsigned calls;};
static bool register_image(void*context,void*data,size_t stride,int width,int height){
 struct registration*r=context;r->calls++;assert(!r->image);
 if(r->fail)return false;
 r->image=pixman_image_create_bits_no_clear(PIXMAN_r5g6b5,width,height,data,(int)stride);
 return r->image!=NULL;
}
static void finish_image(struct registration*r){if(r->image)pixman_image_unref(r->image);r->image=NULL;}
static void lifetime(void){
 uint32_t source[64];for(unsigned i=0;i<64;i++)source[i]=0xff000000u|i*7919;
 uint32_t original[64];memcpy(original,source,sizeof(source));
 struct card_opaque_interior owner={0};struct registration r={0};size_t used=sizeof(source),base=used,limit=8u*1024u*1024u;
 assert(!card_opaque_interior_prepare(&owner,NULL,32,8,8,&used,limit,register_image,&r));
 assert(!card_opaque_interior_prepare(&owner,source,31,8,8,&used,limit,register_image,&r));
 assert(!card_opaque_interior_prepare(&owner,(uint8_t*)source+1,32,8,8,&used,limit,register_image,&r));
 assert(!card_opaque_interior_prepare(&owner,source,SIZE_MAX,8,8,&used,limit,register_image,&r));
 assert(!card_opaque_interior_prepare(&owner,source,32,0,8,&used,limit,register_image,&r));
 unsigned before=allocations;
 assert(!card_opaque_interior_prepare(&owner,source,32,8,8,&used,limit,register_image,&r));assert(allocations==before&&used==base);
 used=limit-1;
 assert(!card_opaque_interior_prepare(&owner,source,32,8,8,&used,limit,register_image,&r));assert(allocations==before&&used==limit-1);
 used=limit+1;
 assert(!card_opaque_interior_prepare(&owner,source,32,8,8,&used,limit,register_image,&r));assert(allocations==before&&used==limit+1);
 used=base;allocation_failure=true;
 assert(!card_opaque_interior_prepare(&owner,source,32,8,8,&used,limit,register_image,&r));assert(!owner.pixels&&used==base);allocation_failure=false;
 r.fail=true;
 assert(!card_opaque_interior_prepare(&owner,source,32,8,8,&used,limit,register_image,&r));assert(!owner.pixels&&!r.image&&used==base);r.fail=false;
 assert(card_opaque_interior_prepare(&owner,source,32,8,8,&used,limit,register_image,&r));assert(owner.pixels&&r.image&&used==base+owner.bytes&&used<=limit);
 unsigned registered=r.calls;
 assert(card_opaque_interior_prepare(&owner,source,32,8,8,&used,limit,register_image,&r));assert(r.calls==registered);
 assert(!memcmp(source,original,sizeof(source)));
 finish_image(&r);card_opaque_interior_finish(&owner,&used);card_opaque_interior_finish(&owner,&used);assert(used==base);
 /* A new immutable generation has its own owner and repeats the reuse gate. */
 source[0]^=0x007b6d53;
 assert(!card_opaque_interior_prepare(&owner,source,32,8,8,&used,limit,register_image,&r));assert(!r.image);
 card_opaque_interior_finish(&owner,&used);assert(used==base);
}
static unsigned selected,precision_sentinels;
static void pixels(int seed,bool alpha,bool masked,int radius,int op,int edge,int destination_cpp){
 enum{SW=47,SH=39,SS=208,DW=83,DH=65};int ds=DW*destination_cpp+12;ds=(ds+3)&~3;size_t bytes=(size_t)ds*DH;
 uint8_t*source=malloc(SS*SH+64),*original=malloc(SS*SH+64),*a=malloc(bytes+64),*b=malloc(bytes+64);assert(source&&original&&a&&b);
 memset(source,0x7b,SS*SH+64);memset(a,0xa6,bytes+64);memcpy(b,a,bytes+64);
 for(int y=0;y<SH;y++)for(int x=0;x<SW;x++){
  uint32_t value=(uint32_t)(x*109123+y*3911+seed*7919);unsigned aa=alpha?32+(unsigned)(x*17+y*11+seed)%224:255;
  value=aa<<24|(((value>>16)&255)*aa/255)<<16|(((value>>8)&255)*aa/255)<<8|((value&255)*aa/255);
  memcpy(source+16+(size_t)y*SS+x*4,&value,4);
 }
 memcpy(original,source,SS*SH+64);
 pixman_image_t*src=pixman_image_create_bits(alpha?PIXMAN_a8r8g8b8:PIXMAN_x8r8g8b8,SW,SH,(uint32_t*)(source+16),SS);
 pixman_image_t*ref=pixman_image_create_bits(destination_cpp==2?PIXMAN_r5g6b5:PIXMAN_x8r8g8b8,DW,DH,(uint32_t*)(a+16),ds),*got=pixman_image_create_bits(destination_cpp==2?PIXMAN_r5g6b5:PIXMAN_x8r8g8b8,DW,DH,(uint32_t*)(b+16),ds);assert(src&&ref&&got);
 struct card_opaque_interior owner={0};struct registration r={0};size_t base=SS*SH,used=base;
 assert(!card_opaque_interior_prepare(&owner,source+16,SS,SW,SH,&used,8u*1024u*1024u,register_image,&r));
 assert(card_opaque_interior_prepare(&owner,source+16,SS,SW,SH,&used,8u*1024u*1024u,register_image,&r));assert(used<=8u*1024u*1024u);
 for(int y=0;y<SH;y++)for(size_t x=SW*2;x<owner.stride;x++)assert(owner.pixels[(size_t)y*owner.stride+x]==0);
 pixman_region32_t clip;pixman_region32_init_rect(&clip,2,3,61,52);pixman_region32_union_rect(&clip,&clip,68,1,10,60);pixman_image_set_clip_region32(ref,&clip);pixman_image_set_clip_region32(got,&clip);
 pixman_image_t*mask=masked?pixman_image_create_solid_fill(&(pixman_color_t){.alpha=32768}):NULL;
 int dx=edge==0?-5:edge==1?7:edge==2?70:8,dy=edge==3?-3:9;
 struct k230_round_box dst={dx,dy,35,29},round=radius?(struct k230_round_box){dx-2,dy-1,39,31}:(struct k230_round_box){0};
 struct k230_round_cache rc={0},gc={0};bool interior_used=false;
 assert(k230_round_composite(&rc,(pixman_op_t)op,src,mask,ref,2+seed%2,3,dst,round,radius,masked?32768:65535));
 assert(k230_round_composite_unscaled_with_interior(&gc,(pixman_op_t)op,src,mask,got,2+seed%2,3,dst,round,radius,masked?32768:65535,&clip,r.image,&interior_used));
 if(alpha||masked||destination_cpp!=2)assert(!interior_used);
 if(interior_used)selected++;
 assert(!memcmp(a,b,bytes+64));assert(!memcmp(source,original,SS*SH+64));
 if(seed==0&&!alpha&&!masked&&radius&&destination_cpp==2&&op==PIXMAN_OP_OVER&&edge==1){
  pixman_image_t*wrong=pixman_image_create_bits(PIXMAN_r5g6b5,SW+3,SH+2,NULL,0);assert(wrong);struct k230_round_cache wc={0};bool selected_wrong=true;
  memset(b,0xa6,bytes+64);
  assert(k230_round_composite_unscaled_with_interior(&wc,(pixman_op_t)op,src,NULL,got,2,3,dst,round,radius,65535,&clip,wrong,&selected_wrong));
  assert(!selected_wrong&&!memcmp(a,b,bytes+64));
  memset(b,0xa6,bytes+64);selected_wrong=true;
  assert(k230_round_composite_unscaled_with_interior(&wc,(pixman_op_t)op,src,NULL,got,2,3,dst,round,radius,65535,&clip,src,&selected_wrong));
  assert(!selected_wrong&&!memcmp(a,b,bytes+64));
  k230_round_cache_finish(&wc);pixman_image_unref(wrong);
 }
 if(!alpha&&!masked&&radius&&destination_cpp==2){
  uint8_t*naive=malloc(bytes+64);assert(naive);memset(naive,0xa6,bytes+64);pixman_image_t*d=pixman_image_create_bits(PIXMAN_r5g6b5,DW,DH,(uint32_t*)(naive+16),ds);assert(d);pixman_image_set_clip_region32(d,&clip);struct k230_round_cache nc={0};
  assert(k230_round_composite(&nc,(pixman_op_t)op,r.image,NULL,d,2+seed%2,3,dst,round,radius,65535));
  if(memcmp(a,naive,bytes+64))precision_sentinels++;
  k230_round_cache_finish(&nc);pixman_image_unref(d);free(naive);
 }
 k230_round_cache_finish(&rc);k230_round_cache_finish(&gc);pixman_region32_fini(&clip);if(mask)pixman_image_unref(mask);pixman_image_unref(src);pixman_image_unref(ref);pixman_image_unref(got);
 finish_image(&r);card_opaque_interior_finish(&owner,&used);assert(used==base);free(source);free(original);free(a);free(b);
}
int main(void){lifetime();unsigned cases=0;for(int seed=0;seed<4;seed++)for(int alpha=0;alpha<2;alpha++)for(int mask=0;mask<2;mask++)for(int radius=0;radius<=7;radius+=7)for(int op=0;op<2;op++)for(int edge=0;edge<4;edge++)for(int cpp=2;cpp<=4;cpp+=2){pixels(seed,alpha,mask,radius,op?PIXMAN_OP_OVER:PIXMAN_OP_SRC,edge,cpp);cases++;}assert(selected==64&&precision_sentinels>0&&allocations==releases);printf("PASS opaque interiors: %u exact guarded Pixman cases, %u selected; %u sentinels reject quantized corners; reuse/budget/allocation/registration/teardown pass\n",cases,selected,precision_sentinels);}
