#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "rounded-clip.h"
static void compare(int seed,int op,bool alpha,bool masked,int radius,int dx,int dy,int sx,int sy,int w,int h){
 enum {SW=47,SH=39,DW=83,DH=65,SS=208,DS=176};
 uint8_t source[SS*SH+64],a[DS*DH+64],b[DS*DH+64];
 memset(source,0x7b,sizeof(source));memset(a,0xa6,sizeof(a));memcpy(b,a,sizeof(a));
 for(int y=0;y<SH;y++)for(int x=0;x<SW;x++){
  uint32_t value=(uint32_t)(x*109123+y*3911+seed*7919);
  if(alpha){unsigned aa=32+(unsigned)(x*17+y*11+seed)%224;value=(aa<<24)|(((value>>16)&255)*aa/255<<16)|(((value>>8)&255)*aa/255<<8)|((value&255)*aa/255);}
  memcpy(source+16+(size_t)y*SS+x*4,&value,4);
 }
 pixman_image_t *src=pixman_image_create_bits(alpha?PIXMAN_a8r8g8b8:PIXMAN_x8r8g8b8,SW,SH,(uint32_t*)(source+16),SS);
 pixman_image_t *ref=pixman_image_create_bits(PIXMAN_r5g6b5,DW,DH,(uint32_t*)(a+16),DS),*got=pixman_image_create_bits(PIXMAN_r5g6b5,DW,DH,(uint32_t*)(b+16),DS);
 assert(src&&ref&&got);pixman_image_set_repeat(src,PIXMAN_REPEAT_PAD);pixman_image_set_transform(src,NULL);
 pixman_region32_t clip;pixman_region32_init_rect(&clip,2,3,61,52);pixman_region32_union_rect(&clip,&clip,68,1,10,60);
 pixman_image_set_clip_region32(ref,&clip);pixman_image_set_clip_region32(got,&clip);
 pixman_image_t *mask=masked?pixman_image_create_solid_fill(&(pixman_color_t){.alpha=32768}):NULL;
 struct k230_round_cache rc={0},gc={0};struct k230_round_box box={dx,dy,w,h},round=radius?(struct k230_round_box){dx-2,dy-1,w+4,h+2}:(struct k230_round_box){0};
 assert(k230_round_composite(&rc,(pixman_op_t)op,src,mask,ref,sx,sy,box,round,radius,masked?32768:65535));
 assert(k230_round_composite_unscaled(&gc,(pixman_op_t)op,src,mask,got,sx,sy,box,round,radius,masked?32768:65535,&clip));
 assert(memcmp(a,b,sizeof(a))==0);
 k230_round_cache_finish(&rc);k230_round_cache_finish(&gc);pixman_region32_fini(&clip);
 if(mask)pixman_image_unref(mask);
 pixman_image_unref(src);pixman_image_unref(ref);pixman_image_unref(got);
}
int main(void){
 unsigned n=0;
 for(int seed=0;seed<4;seed++)for(int alpha=0;alpha<2;alpha++)for(int mask=0;mask<2;mask++)for(int radius=0;radius<=6;radius+=6)
 for(int op=0;op<2;op++)for(int edge=0;edge<4;edge++){
  int dx=edge==0?-5:edge==1?7:edge==2?70:8,dy=edge==3?-3:9;
  compare(seed,op?PIXMAN_OP_OVER:PIXMAN_OP_SRC,alpha,mask,radius,dx,dy,2+seed%2,3,35,29);n++;
 }
 uint32_t pixels[16]={0};uint16_t target[16]={0};
 pixman_image_t *src=pixman_image_create_bits(PIXMAN_x8r8g8b8,4,4,pixels,16),*dst=pixman_image_create_bits(PIXMAN_r5g6b5,4,4,(uint32_t*)target,8);
 assert(!k230_rgb565_blit(PIXMAN_OP_SRC,src,NULL,dst,-1,0,0,0,4,4,NULL));
 assert(!k230_rgb565_blit(PIXMAN_OP_SRC,src,NULL,dst,0,0,0,0,5,4,NULL));
 assert(!k230_rgb565_blit(PIXMAN_OP_ADD,src,NULL,dst,0,0,0,0,4,4,NULL));
 assert(!k230_rgb565_blit(PIXMAN_OP_SRC,src,NULL,src,0,0,0,0,4,4,NULL));
 assert(!k230_rgb565_blit(PIXMAN_OP_SRC,NULL,NULL,dst,0,0,0,0,4,4,NULL));
 pixman_image_unref(src);pixman_image_unref(dst);
 printf("PASS RGB565 unscaled conversion: %u clipped/rounded/alpha-fallback oracle cases\n",n);
}
