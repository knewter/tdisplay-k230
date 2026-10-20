#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "output-cache.h"
#include "rounded-clip.h"
struct scene {pixman_image_t *wall,*card,*clock;struct k230_round_cache rounded;int width,height;};
static int card_x(int frame){return frame%9*3-4;}
static int card_y(int frame){return frame%5*2+6;}
static void render(struct scene*s,pixman_image_t*d,const pixman_region32_t*clip,int frame){
 uint32_t*p=pixman_image_get_data(s->card);int stride=pixman_image_get_stride(s->card)/4;
 for(int y=0;y<24;y++)for(int x=0;x<32;x++){
  unsigned a=frame%3==0?255:(unsigned)(x*17+y*11+frame*23)%256;
  unsigned r=(unsigned)(x*71+frame*29)%256,g=(unsigned)(y*37+frame*17)%256,b=(unsigned)(x*19+y*13+frame*7)%256;
  p[(size_t)y*stride+x]=a<<24|(r*a/255)<<16|(g*a/255)<<8|b*a/255;
 }
 pixman_image_set_clip_region32(d,(pixman_region32_t*)clip);
 pixman_image_composite32(PIXMAN_OP_SRC,s->wall,NULL,d,0,0,0,0,0,0,s->width,s->height);
 struct k230_round_box box={card_x(frame),card_y(frame),32,24};
 assert(k230_round_composite(&s->rounded,PIXMAN_OP_OVER,s->card,NULL,d,0,0,box,box,7,65535));
 uint32_t*c=pixman_image_get_data(s->clock);for(int i=0;i<12;i++)c[i]=0xff000000u|((unsigned)frame*19391+i*7919);
 pixman_image_composite32(PIXMAN_OP_OVER,s->clock,NULL,d,0,0,0,0,s->width-7,1,4,3);
 pixman_image_set_clip_region32(d,NULL);
}
static unsigned test(int width,int height,pixman_format_code_t format,int initial_turn){
 int cpp=k230_turn_cpp(format),ds=((height*cpp+3)&~3)+12;size_t bytes=(size_t)ds*width;
 struct k230_output_cache buffers[3]={0};pixman_region32_t pending[3];pixman_image_t*targets[3];uint8_t*data[3];
 for(int i=0;i<3;i++){pixman_region32_init(&pending[i]);data[i]=malloc(bytes+64);assert(data[i]);memset(data[i],0xa7,bytes+64);targets[i]=pixman_image_create_bits_no_clear(format,height,width,(uint32_t*)(data[i]+16),ds);assert(targets[i]);}
 pixman_image_t*reference=pixman_image_create_bits(format,width,height,NULL,0);assert(reference);
 struct scene s={.width=width,.height=height,.wall=pixman_image_create_bits(PIXMAN_a8r8g8b8,width,height,NULL,0),.card=pixman_image_create_bits(PIXMAN_a8r8g8b8,32,24,NULL,0),.clock=pixman_image_create_bits(PIXMAN_a8r8g8b8,4,3,NULL,0)};assert(s.wall&&s.card&&s.clock);
 uint32_t*wall=pixman_image_get_data(s.wall);int ws=pixman_image_get_stride(s.wall)/4;
 for(int y=0;y<height;y++)for(int x=0;x<width;x++)wall[(size_t)y*ws+x]=0xff000000u|((unsigned)(x*109123+y*3911)&0xffffff);
 unsigned comparisons=0;
 for(int frame=0;frame<24;frame++){
  for(int i=0;i<3;i++){
   pixman_region32_union_rect(&pending[i],&pending[i],card_x(frame),card_y(frame),32,24);
   if(frame)pixman_region32_union_rect(&pending[i],&pending[i],card_x(frame-1),card_y(frame-1),32,24);
   pixman_region32_union_rect(&pending[i],&pending[i],width-7,1,4,3);
  }
  int index=frame%3,turn=frame<17?initial_turn:4-initial_turn;
  if(frame==10){ /* Ordinary renderer wrote this buffer: old scratch is invalid. */
   k230_output_cache_invalidate(&buffers[index]);memset(data[index]+16,0x3d,bytes);continue;
  }
  if(frame==21)k230_output_cache_finish(&buffers[index]); /* buffer-wrapper recreation */
  bool preserved;pixman_image_t*image=k230_output_cache_begin(&buffers[index],width,height,format,turn,&preserved);assert(image);
  for(int other=0;other<3;other++)if(other!=index&&buffers[other].image)assert(buffers[other].image!=image&&buffers[other].data!=buffers[index].data);
  pixman_region32_t damage;pixman_region32_init(&damage);
  if(preserved)pixman_region32_copy(&damage,&pending[index]);else pixman_region32_union_rect(&damage,&damage,0,0,width,height);
  /* The scene damage ring is physical. Build that input from the independent
   * pixel-coordinate oracle, then execute the production inverse mapping. */
  pixman_region32_t clipped,physical,logical;pixman_region32_init(&clipped);pixman_region32_init(&physical);pixman_region32_init(&logical);
  assert(pixman_region32_intersect_rect(&clipped,&damage,0,0,width,height));
  int count;pixman_box32_t *boxes=pixman_region32_rectangles(&clipped,&count);
  for(int i=0;i<count;i++){
   pixman_box32_t b=boxes[i];int dx=turn==1?b.y1:height-b.y2,dy=turn==1?width-b.x2:b.x1;
   assert(pixman_region32_union_rect(&physical,&physical,dx,dy,b.y2-b.y1,b.x2-b.x1));
  }
  assert(k230_turn_damage_from_output(&logical,&physical,width,height,turn));assert(pixman_region32_equal(&logical,&clipped));
  /* Production converts the ring in place. */
  assert(k230_turn_damage_from_output(&physical,&physical,width,height,turn));assert(pixman_region32_equal(&physical,&clipped));
  pixman_region32_copy(&damage,&logical);pixman_region32_fini(&logical);pixman_region32_fini(&physical);pixman_region32_fini(&clipped);
  render(&s,image,&damage,frame);
  if(frame==13){k230_output_cache_submitted(&buffers[index],false);pixman_region32_fini(&damage);continue;}
  pixman_region32_t painted;pixman_region32_init(&painted);assert(k230_turn_damage_add(&painted,0,0,width,height,&damage,width,height));
  assert(pixman_region32_equal(&painted,&damage));assert(k230_turn_region_into(targets[index],image,turn,&painted));pixman_region32_fini(&painted);k230_output_cache_submitted(&buffers[index],true);pixman_region32_clear(&pending[index]);pixman_region32_fini(&damage);
  render(&s,reference,NULL,frame);
  uint8_t*expected=malloc(bytes+64);assert(expected);memset(expected,0xa7,bytes+64);uint8_t*source=(uint8_t*)pixman_image_get_data(reference);int ss=pixman_image_get_stride(reference);
  for(int y=0;y<height;y++)for(int x=0;x<width;x++){
   int dx=turn==1?y:height-1-y,dy=turn==1?width-1-x:x;
   memcpy(expected+16+(size_t)dy*ds+dx*cpp,source+(size_t)y*ss+x*cpp,cpp);
  }
  /* The simulated ordinary pass also wrote padding; padding is outside our
   * update contract and remains whatever was there before quarter-turn. */
  if(index==10%3&&frame>10)for(int row=0;row<width;row++)memset(expected+16+(size_t)row*ds+height*cpp,0x3d,(size_t)ds-height*cpp);
  if(memcmp(expected,data[index],bytes+64)){fprintf(stderr,"Mismatch width=%d height=%d format=%x frame=%d turn=%d preserved=%d\n",width,height,format,frame,turn,preserved);abort();}
  if(frame==0){
   pixman_region32_t empty;pixman_region32_init(&empty);uint8_t *pixel=(uint8_t*)pixman_image_get_data(image);pixel[0]^=0x77;
   assert(k230_turn_region_into(targets[index],image,turn,&empty));assert(!memcmp(expected,data[index],bytes+64));
   pixman_region32_union_rect(&empty,&empty,-20,-20,2,2);
   assert(k230_turn_region_into(targets[index],image,turn,&empty));assert(!memcmp(expected,data[index],bytes+64));
   assert(!k230_turn_region_into(targets[index],NULL,turn,&empty));pixel[0]^=0x77;pixman_region32_fini(&empty);
  }
  free(expected);comparisons++;
 }
 k230_round_cache_finish(&s.rounded);pixman_image_unref(s.wall);pixman_image_unref(s.card);pixman_image_unref(s.clock);pixman_image_unref(reference);
 for(int i=0;i<3;i++){k230_output_cache_finish(&buffers[i]);pixman_region32_fini(&pending[i]);pixman_image_unref(targets[i]);free(data[i]);}
 return comparisons;
}
int main(void){unsigned frames=0,cases=0;int sizes[][2]={{63,47},{64,48},{65,49},{1232,568}};for(unsigned size=0;size<4;size++)for(int cpp=2;cpp<=4;cpp+=2)for(int turn=1;turn<=3;turn+=2){frames+=test(sizes[size][0],sizes[size][1],cpp==2?PIXMAN_r5g6b5:PIXMAN_x8r8g8b8,turn);cases++;}printf("PASS retained output: %u three-buffer cases, %u exact multi-frame compositions\n",cases,frames);}
