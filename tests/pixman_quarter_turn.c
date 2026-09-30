#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdio.h>
#include <time.h>
#include "quarter-turn.h"
#include "rounded-clip.h"

struct box { int x,y,w,h; };
static void transform(pixman_image_t *image, struct box crop, struct box dst, int turn) {
	pixman_transform_t t;
	pixman_transform_init_identity(&t);
	pixman_transform_scale(&t,NULL,pixman_double_to_fixed((double)(turn ? crop.h : crop.w)/dst.w),
		pixman_double_to_fixed((double)(turn ? crop.w : crop.h)/dst.h));
	if (turn == 1) {
		pixman_transform_translate(&t,NULL,0,-pixman_int_to_fixed(crop.w));
		pixman_transform_rotate(&t,NULL,0,pixman_int_to_fixed(1));
	} else if (turn == 3) {
		pixman_transform_translate(&t,NULL,-pixman_int_to_fixed(crop.h),0);
		pixman_transform_rotate(&t,NULL,0,pixman_int_to_fixed(-1));
	}
	pixman_transform_translate(&t,NULL,pixman_int_to_fixed(crop.x),pixman_int_to_fixed(crop.y));
	pixman_image_set_transform(image,&t);
}
static void paint(pixman_image_t *source,pixman_image_t *dest,struct box crop,
		struct box dst,int turn,bool fast,bool bilinear,int radius,uint16_t alpha,
		struct k230_turn_scratch *scratch) {
	pixman_image_t *image=source;
	/* Match the candidate eligibility: scaled bilinear keeps the sampler. */
	fast = fast && (!bilinear || (crop.h==dst.w && crop.w==dst.h));
	if (fast) {
		image=k230_turn_image(scratch,source,turn);
		assert(image);
		int width=pixman_image_get_width(source),height=pixman_image_get_height(source);
		crop= turn==1 ? (struct box){crop.y,width-crop.x-crop.w,crop.h,crop.w} :
			(struct box){height-crop.y-crop.h,crop.x,crop.h,crop.w};
		turn=0;
	}
	transform(image,crop,dst,turn);
	pixman_image_set_repeat(image,PIXMAN_REPEAT_PAD);
	pixman_image_set_filter(image,bilinear ? PIXMAN_FILTER_BILINEAR : PIXMAN_FILTER_NEAREST,NULL,0);
	struct k230_round_cache cache={0};
	struct k230_round_box bounds={dst.x,dst.y,dst.w,dst.h};
	pixman_image_t *mask=alpha==65535 ? NULL : pixman_image_create_solid_fill(&(pixman_color_t){.alpha=alpha});
	assert(alpha==65535 || mask);
	assert(k230_round_composite(&cache,PIXMAN_OP_OVER,image,mask,dest,0,0,bounds,
		radius ? bounds : (struct k230_round_box){0},radius,alpha));
	k230_round_cache_finish(&cache);
	if(mask)pixman_image_unref(mask);
	pixman_image_set_transform(image,NULL);
	if(fast)pixman_image_unref(image);
}
static pixman_image_t *pattern(pixman_format_code_t format,int w,int h,int seed) {
	pixman_image_t *image=pixman_image_create_bits(format,w,h,NULL,0);
	assert(image);
	uint8_t *data=(uint8_t *)pixman_image_get_data(image);
	int stride=pixman_image_get_stride(image);
	for(int y=0;y<h;y++)for(int x=0;x<w;x++) {
		if(PIXMAN_FORMAT_BPP(format)==16)
			*(uint16_t *)(data+y*stride+x*2)=(uint16_t)(x*537+y*271+seed*97);
		else {
			uint32_t a=PIXMAN_FORMAT_A(format) ? 64+(x*17+y*7+seed)%192 : 255;
			uint32_t r=(x*19+y*3+seed)%256*a/255,g=(x*5+y*23+seed)%256*a/255,b=(x*11+y*13+seed)%256*a/255;
			*(uint32_t *)(data+y*stride+x*4)=(a<<24)|(r<<16)|(g<<8)|b;
		}
	}
	return image;
}
static uint64_t ns(void) { struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000+t.tv_nsec; }
static int benchmark(void) {
	struct k230_turn_scratch scratch={0};
	pixman_image_t *source=pattern(PIXMAN_a8r8g8b8,1080,1920,3),*dest=pattern(PIXMAN_a8r8g8b8,1920,1080,1);
	struct box crop={0,0,1080,1920},dst={0,0,1920,1080};
	for(int fast=0;fast<2;fast++) {
		uint64_t start=ns();
		for(int i=0;i<12;i++)paint(source,dest,crop,dst,3,fast,false,0,65535,&scratch);
		printf("quarter-turn-benchmark fast=%d frames=12 average_ms=%.3f scratch_bytes=%zu\n",fast,(ns()-start)/12000000.0,scratch.bytes);
	}
	for(int f=0;f<3;f++) {
		pixman_format_code_t fmt=f==0 ? PIXMAN_a8r8g8b8 : f==1 ? PIXMAN_x8r8g8b8 : PIXMAN_r5g6b5;
		pixman_image_t *logical=pattern(fmt,1080,1920,4),*physical=pattern(fmt,1920,1080,5);
		uint64_t start=ns();
		for(int i=0;i<24;i++)assert(k230_turn_into(physical,logical,3));
		printf("quarter-turn-output-copy format=%s frames=24 average_wall_ms=%.3f\n",
			f==0 ? "ARGB8888" : f==1 ? "XRGB8888" : "RGB565",(ns()-start)/24000000.0);
		pixman_image_unref(logical);pixman_image_unref(physical);
	}
	pixman_image_unref(source);pixman_image_unref(dest);k230_turn_finish(&scratch);return 0;
}
int main(int argc,char **argv) {
	if(argc==2 && !strcmp(argv[1],"--benchmark"))return benchmark();
	struct k230_turn_scratch scratch={0};
	pixman_format_code_t formats[]={PIXMAN_a8r8g8b8,PIXMAN_x8r8g8b8,PIXMAN_r5g6b5,PIXMAN_a8b8g8r8,PIXMAN_x8b8g8r8,PIXMAN_b5g6r5};
	unsigned cases=0;
	for(unsigned f=0;f<6;f++)for(unsigned d=0;d<2;d++)for(int turn=1;turn<=3;turn+=2)
	for(int scale=0;scale<3;scale++)for(int crop_on=0;crop_on<2;crop_on++)
	for(int bilinear=0;bilinear<2;bilinear++)for(int radius=0;radius<=12;radius+=12)
	for(int alpha=32768;alpha<=65535;alpha+=32767) {
		pixman_image_t *source=pattern(formats[f],37,61,2);
		/* Reusing scratch after changed pixels also proves it is not a pixel cache. */
		struct box crop=crop_on ? (struct box){2,3,29,51} : (struct box){0,0,37,61};
		struct box dst={3,5,scale==0 ? crop.h : scale==1 ? 41 : 97,
			scale==0 ? crop.w : scale==1 ? 29 : 79};
		pixman_format_code_t output=d ? PIXMAN_r5g6b5 : PIXMAN_a8r8g8b8;
		pixman_image_t *ref=pattern(output,104,90,7),*got=pattern(output,104,90,7);
		pixman_region32_t damage;pixman_region32_init_rect(&damage,1,2,90,83);
		pixman_region32_union_rect(&damage,&damage,96,0,8,90);
		pixman_image_set_clip_region32(ref,&damage);pixman_image_set_clip_region32(got,&damage);
		paint(source,ref,crop,dst,turn,false,bilinear,radius,(uint16_t)alpha,&scratch);
		paint(source,got,crop,dst,turn,true,bilinear,radius,(uint16_t)alpha,&scratch);
		unsigned diff=0;int stride=pixman_image_get_stride(ref),cpp=d ? 2 : 4;
		uint8_t *a=(uint8_t *)pixman_image_get_data(ref),*b=(uint8_t *)pixman_image_get_data(got);
		for(int y=0;y<90;y++)for(int x=0;x<104*cpp;x++)if(a[y*stride+x]!=b[y*stride+x])diff++;
		if(diff) {fprintf(stderr,"pixel mismatch format=%u output=%u turn=%d scale=%d crop=%d bilinear=%d radius=%d alpha=%d bytes=%u\n",f,d,turn,scale,crop_on,bilinear,radius,alpha,diff);return 1;}
        cases++;pixman_region32_fini(&damage);pixman_image_unref(source);pixman_image_unref(ref);pixman_image_unref(got);
	}
	for(unsigned f=0;f<6;f++) {
		pixman_image_t *source=pattern(formats[f],37,61,5);
		pixman_image_t *dest=pattern(formats[f],61,37,6);
		int cpp=PIXMAN_FORMAT_BPP(formats[f])/8;
		for(int update=0;update<4;update++)for(int turn=1;turn<=3;turn+=2) {
			uint8_t *src=(uint8_t *)pixman_image_get_data(source);
			int ss=pixman_image_get_stride(source),ds=pixman_image_get_stride(dest);
			/* A real texture may change in place with the very same identity. */
			for(int y=0;y<61;y++)for(int x=0;x<37*cpp;x++)src[y*ss+x]^=(uint8_t)(17+update);
			assert(k230_turn_into(dest,source,turn));
			uint8_t *out=(uint8_t *)pixman_image_get_data(dest);
			for(int y=0;y<61;y++)for(int x=0;x<37;x++) {
				int dx=turn==1 ? y : 60-y,dy=turn==1 ? 36-x : x;
				assert(!memcmp(src+y*ss+x*cpp,out+dy*ds+dx*cpp,(size_t)cpp));
			}
		}
		assert(!k230_turn_into(source,source,1));
		assert(!k230_turn_into(dest,source,2));
		pixman_image_unref(source);pixman_image_unref(dest);
	}
	pixman_image_t *unsupported=pixman_image_create_bits(PIXMAN_a8,7,9,NULL,0);
	assert(!k230_turn_image(&scratch,unsupported,1));pixman_image_unref(unsupported);
	assert(!k230_turn_image(&scratch,NULL,0));
	k230_turn_finish(&scratch);
	printf("PASS quarter-turn: %u exact pixel comparisons; scaled bilinear sampler fallback\n",cases);
	return 0;
}
