#include "rounded-clip.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define W 89
#define H 103
/* Independent oracle: one full output-sized alpha mask, using floating
 * point circle tests at sample positions, then one ordinary Pixman draw.
 * Production instead touches only the four corner squares. */
static void compare(struct k230_round_cache *cache, int radius, bool translucent,
		bool transform, bool cropped_child, bool damage, bool rgb565) {
	uint32_t src[W*H], actual[W*H], expected[W*H];
	uint8_t coverage[(W+3)/4*4*H];
	int stride = (W+3)/4*4;
	uint16_t alpha = translucent ? 32767 : 65535;
	for (int y=0; y<H; y++) for (int x=0; x<W; x++) {
		src[y*W+x] = translucent ? 0x80604020u : 0xff000000u | ((x*97+y*719)&0xffffffu);
		actual[y*W+x] = expected[y*W+x] = 0xff000000u | ((x*7309+y*401)&0xffffffu);
	}
	struct k230_round_box round = {-4, 12, 70, 82};
	struct k230_round_box dst = cropped_child ? (struct k230_round_box){-1,9,46,59} :
		(struct k230_round_box){-7,3,81,99};
	int r=radius;
	if(r>round.width/2)r=round.width/2;
	if(r>round.height/2)r=round.height/2;
	memset(coverage,0,sizeof(coverage));
	/* Build mask in output coordinates; source coordinates are independent. */
	for(int y=0;y<H;y++)for(int x=0;x<W;x++) {
		unsigned inside=0;
		for(int sy=0;sy<4;sy++)for(int sx=0;sx<4;sx++) {
			double px=x+(sx+.5)/4, py=y+(sy+.5)/4;
			if(px<round.x||px>=round.x+round.width||py<round.y||py>=round.y+round.height)continue;
			double cx=fmax(round.x+r,fmin(px,round.x+round.width-r));
			double cy=fmax(round.y+r,fmin(py,round.y+round.height-r));
			inside+=(px-cx)*(px-cx)+(py-cy)*(py-cy)<=r*r;
		}
		coverage[y*stride+x]=(inside*(uint32_t)alpha*255+16u*65535/2)/(16u*65535);
	}
	pixman_image_t *source=pixman_image_create_bits(PIXMAN_a8r8g8b8,W,H,src,W*4);
	pixman_image_t *out=pixman_image_create_bits(rgb565?PIXMAN_r5g6b5:PIXMAN_a8r8g8b8,W,H,actual,W*4);
	pixman_image_t *ref=pixman_image_create_bits(rgb565?PIXMAN_r5g6b5:PIXMAN_a8r8g8b8,W,H,expected,W*4);
	pixman_image_t *mask=pixman_image_create_bits(PIXMAN_a8,W,H,(uint32_t *)coverage,stride);
	pixman_image_t *opacity=translucent?pixman_image_create_solid_fill(&(pixman_color_t){.alpha=alpha}):NULL;
	pixman_transform_t t;
	pixman_transform_init_identity(&t);
	if(transform) {
		pixman_transform_scale(&t,NULL,pixman_double_to_fixed(.71),pixman_double_to_fixed(1.11));
		pixman_transform_rotate(&t,NULL,0,pixman_int_to_fixed(1));
		pixman_transform_translate(&t,NULL,pixman_int_to_fixed(83),pixman_int_to_fixed(5));
		pixman_image_set_transform(source,&t);
	}
	pixman_image_set_repeat(source,PIXMAN_REPEAT_PAD);
	pixman_image_set_filter(source,PIXMAN_FILTER_BILINEAR,NULL,0);
	pixman_region32_t clip;
	pixman_region32_init_rect(&clip,damage?8:0,damage?19:0,damage?49:W,damage?56:H);
	pixman_image_set_clip_region32(out,&clip);
	pixman_image_set_clip_region32(ref,&clip);
	assert(k230_round_composite(cache,PIXMAN_OP_OVER,source,opacity,out,2,7,dst,round,radius,alpha));
	/* Composite to temporary over a translated mask: Pixman coordinates for
	 * the mask are output coordinates, not the source's crop/transform. */
	pixman_image_composite32(PIXMAN_OP_OVER,source,mask,ref,2,7,dst.x,dst.y,
		dst.x,dst.y,dst.width,dst.height);
	if(memcmp(actual,expected,sizeof(actual))) {
		for(int y=0;y<H;y++)for(int x=0;x<W;x++)if(actual[y*W+x]!=expected[y*W+x]) {
			fprintf(stderr,"mismatch radius=%d alpha=%d transform=%d child=%d damage=%d rgb565=%d at %d,%d %08x != %08x\n",radius,translucent,transform,cropped_child,damage,rgb565,x,y,actual[y*W+x],expected[y*W+x]);
			abort();
		}
	}
	pixman_region32_fini(&clip);
	if(opacity)pixman_image_unref(opacity);
	pixman_image_unref(mask);pixman_image_unref(ref);pixman_image_unref(out);pixman_image_unref(source);
}
int main(void) {
	struct k230_round_cache cache={0};
	int radii[]={0,1,2,7,13,25,26,35,64};
	int count=0;
	for(unsigned r=0;r<sizeof(radii)/sizeof(radii[0]);r++)
	for(int bits=0;bits<32;bits++) {
		compare(&cache,radii[r],bits&1,bits&2,bits&4,bits&8,bits&16);
		count++;
	}
	/* Radius and opacity changes exceed the LRU capacity above; destruction
	 * is checked under ASan/LSan as well as ordinary execution. */
	k230_round_cache_finish(&cache);
	printf("PASS %d rounded clip pixel comparisons (wallpaper, alpha, transform, cropped child, damage, RGB565)\n",count);
}
