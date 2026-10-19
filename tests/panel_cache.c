#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <drm_fourcc.h>
#include <pixman.h>
#include "scaled-cache.h"
#include "rounded-clip.h"
#include "quarter-turn.h"
static void compare(bool fast,int turn,int radius,bool partial,int sw,int sh,int dw,int dh,int source_kind){
 bool rgb565=source_kind==1,alpha=source_kind==2;
 uint32_t data[38*30],scaled[56*44];
 pixman_image_t *src=pixman_image_create_bits(rgb565?PIXMAN_r5g6b5:alpha?PIXMAN_a8r8g8b8:PIXMAN_x8r8g8b8,sw,sh,data,sw*(rgb565?2:4));
 pixman_image_t *cache=pixman_image_create_bits(alpha?PIXMAN_a8r8g8b8:PIXMAN_x8r8g8b8,dw,dh,scaled,dw*4);
 pixman_image_t *a=pixman_image_create_bits(PIXMAN_r5g6b5,80,64,NULL,0),*b=pixman_image_create_bits(PIXMAN_r5g6b5,80,64,NULL,0);
 pixman_image_t *ar=pixman_image_create_bits(PIXMAN_r5g6b5,64,80,NULL,0),*br=pixman_image_create_bits(PIXMAN_r5g6b5,64,80,NULL,0);
 assert(src&&cache&&a&&b&&ar&&br);
 struct k230_round_cache masks={0};
 for(int frame=0;frame<3;frame++){
  for(int i=0;i<sw*sh;i++) {
   if(rgb565)((uint16_t*)data)[i]=(uint16_t)(i*3911+frame*731);
   else {
    unsigned a=alpha ? 32+(unsigned)(i*17+frame*23)%224 : 255;
    unsigned r=(unsigned)(i*19+frame*11)%256*a/255;
    unsigned g=(unsigned)(i*7+frame*13)%256*a/255;
    unsigned b=(unsigned)(i*29+frame*3)%256*a/255;
    data[i]=(a<<24)|(r<<16)|(g<<8)|b;
   }
  }
  memset(pixman_image_get_data(a),0x5a,160*64);memset(pixman_image_get_data(b),0x5a,160*64);
  assert(card_scale_pixels(scaled,(size_t)dw*4,dw,dh,alpha?DRM_FORMAT_ARGB8888:DRM_FORMAT_XRGB8888,data,(size_t)sw*(rgb565?2:4),sw,sh,rgb565?DRM_FORMAT_RGB565:alpha?DRM_FORMAT_ARGB8888:DRM_FORMAT_XRGB8888,fast));
  pixman_transform_t t;pixman_transform_init_identity(&t);pixman_transform_scale(&t,NULL,pixman_double_to_fixed((double)sw/dw),pixman_double_to_fixed((double)sh/dh));
  pixman_image_set_transform(src,&t);pixman_image_set_repeat(src,PIXMAN_REPEAT_PAD);pixman_image_set_filter(src,fast?PIXMAN_FILTER_NEAREST:PIXMAN_FILTER_BILINEAR,NULL,0);
  struct k230_round_box box={7,11,dw,dh};
  pixman_region32_t clip;pixman_region32_init_rect(&clip,partial?12:0,partial?14:0,partial?dw/2:80,partial?dh/2:64);
  pixman_image_set_clip_region32(a,&clip);pixman_image_set_clip_region32(b,&clip);
  assert(k230_round_composite(&masks,alpha?PIXMAN_OP_OVER:PIXMAN_OP_SRC,src,NULL,a,0,0,box,box,radius,65535));
  struct k230_round_box fragment = partial ?
      (struct k230_round_box){12,14,dw/2,dh/2} : box;
  assert(k230_round_composite(&masks,alpha?PIXMAN_OP_OVER:PIXMAN_OP_SRC,cache,NULL,b,
      fragment.x-box.x,fragment.y-box.y,fragment,box,radius,65535));
  pixman_region32_fini(&clip);
  assert(memcmp(pixman_image_get_data(a),pixman_image_get_data(b),160*64)==0);
  assert(k230_turn_into(ar,a,turn)&&k230_turn_into(br,b,turn));
  assert(memcmp(pixman_image_get_data(ar),pixman_image_get_data(br),128*80)==0);
 }
 k230_round_cache_finish(&masks);pixman_image_unref(src);pixman_image_unref(cache);pixman_image_unref(a);pixman_image_unref(b);pixman_image_unref(ar);pixman_image_unref(br);
}
int main(void){
 unsigned cases=0;
 for(int fast=0;fast<2;fast++)for(int turn=1;turn<=3;turn+=2)for(int r=0;r<=7;r+=7)for(int crop=0;crop<2;crop++)for(int up=0;up<2;up++)for(int fmt=0;fmt<3;fmt++){
  compare(fast,turn,r,crop,38,30,up?56:20,up?44:16,fmt);cases++;
 }
 assert(card_cache_logical_output(0,false,true,true));
 for(int t=1;t<8;t++){
  assert(!card_cache_logical_output(t,false,false,false));
  assert(!card_cache_logical_output(t,true,true,false));
  assert(!card_cache_logical_output(t,true,false,true));
  assert(card_cache_logical_output(t,true,false,false)==(t==1||t==3));
 }
 uint32_t source[4]={0},target[4]={0};
 assert(!card_scale_pixels(target,8,2,2,DRM_FORMAT_ABGR8888,source,8,2,2,DRM_FORMAT_XRGB8888,false));
 assert(!card_scale_pixels(target,4,2,2,DRM_FORMAT_XRGB8888,source,8,2,2,DRM_FORMAT_XRGB8888,false));
 assert(!card_scale_pixels(target,8,2,2,DRM_FORMAT_XRGB8888,source,8,2,2,DRM_FORMAT_ARGB8888,false));
 printf("PASS full-precision cached rounded/partial/rotated pixels: %u cases, three live frames each\n",cases);
}
