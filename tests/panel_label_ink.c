#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <pixman.h>
#include <pango/pangocairo.h>
#include "label-ink.h"

/* Composite the complete authored image and the bounded image into independent
 * changing destinations, including every padding byte. Pixman is the oracle. */
static int comparisons;
static void compare(uint8_t *data, int width, int height, int stride) {
    struct card_label_ink ink;
    assert(card_label_ink_find(&ink, data, stride, width, height));
    for (int cpp = 2; cpp <= 4; cpp += 2) {
        pixman_format_code_t format = cpp == 2 ? PIXMAN_r5g6b5 : PIXMAN_x8r8g8b8;
        int dw = 173, dh = 89, ds = (dw*cpp+15)&~15;
        size_t bytes = (size_t)ds*dh;
        uint8_t *a = malloc(bytes), *b = malloc(bytes);
        assert(a && b);
        pixman_image_t *source = pixman_image_create_bits_no_clear(PIXMAN_a8r8g8b8,
            width, height, (uint32_t *)data, stride);
        pixman_image_t *full = pixman_image_create_bits_no_clear(format,dw,dh,(uint32_t *)a,ds);
        pixman_image_t *crop = pixman_image_create_bits_no_clear(format,dw,dh,(uint32_t *)b,ds);
        assert(source && full && crop);
        const int positions[] = {-160,-80,-50,-5,43,90,170,220};
        for (int moved = 0; moved < 8; moved++) for (int alpha = 0; alpha < 3; alpha++) {
            for (size_t i = 0; i < bytes; i++) a[i] = b[i] = (uint8_t)(i*17+moved*31);
            int x = positions[moved], y = -19+(moved%4)*23;
            pixman_color_t color = {.alpha = alpha == 0 ? 0 : alpha == 1 ? 32767 : 65535};
            pixman_image_t *mask = pixman_image_create_solid_fill(&color);
            assert(mask);
            pixman_region32_t clip;
            pixman_region32_init_rect(&clip, 3, 2, dw-10, dh-8);
            pixman_region32_union_rect(&clip, &clip, 0, 17, dw, 11);
            pixman_image_set_clip_region32(full, &clip);
            pixman_image_set_clip_region32(crop, &clip);
            pixman_image_composite32(PIXMAN_OP_OVER,source,mask,full,0,0,0,0,x,y,width,height);
            if (ink.width && ink.height) {
                pixman_image_composite32(PIXMAN_OP_OVER,source,mask,crop,ink.x,ink.y,0,0,
                    x+ink.x,y+ink.y,ink.width,ink.height);
            } /* The empty image is a no-op; production retains its full path. */
            assert(memcmp(a,b,bytes) == 0);
            pixman_region32_fini(&clip);
            pixman_image_unref(mask);
            comparisons++;
        }
        pixman_image_unref(source);pixman_image_unref(full);pixman_image_unref(crop);
        free(a);free(b);
    }
}
int main(void) {
    enum {W=127,H=44,STRIDE=528};
    uint8_t pixels[STRIDE*H];
    for (int changed = 0; changed < 8; changed++) {
        memset(pixels,0,sizeof(pixels));
        /* Nonzero padding must not influence bounds. */
        for (int y=0;y<H;y++) memset(pixels+y*STRIDE+W*4,0xa5,STRIDE-W*4);
        for (int y=5;y<27;y++) for (int x=7;x<49;x++) {
            uint8_t alpha=(uint8_t)((x*31+y*13+changed*17)&255);
            if ((x+y+changed)%3) continue;
            uint32_t pixel=(uint32_t)alpha<<24 | (uint32_t)(alpha/2)<<16 |
                (uint32_t)(alpha/3)<<8 | alpha/4;
            memcpy(pixels+y*STRIDE+x*4,&pixel,4);
        }
        if(changed==1) pixels[0]=1; /* alpha-zero/nonzero RGB is still ink */
        if(changed==2) pixels[(H-1)*STRIDE+(W-1)*4+3]=255;
        if(changed==3) memset(pixels,0,sizeof(pixels));
        uint8_t original[sizeof(pixels)];memcpy(original,pixels,sizeof(pixels));
        compare(pixels,W,H,STRIDE);
        assert(memcmp(original,pixels,sizeof(pixels))==0);
    }
    /* Real Pango glyphs, antialiasing, clipping, ellipsis, multilingual text
     * and size/weight changes: scan the completed raster, never font metrics. */
    const char *texts[] = {"Motion-one", "j\xc3\xa9 tail", "A very long label that must ellipsize", "", "\xce\xa9 \xe4\xb8\xad"};
    for (int t=0;t<5;t++) for (int size=14;size<=30;size+=8) {
        cairo_surface_t *surface=cairo_image_surface_create(CAIRO_FORMAT_ARGB32,W,H);
        assert(cairo_surface_status(surface)==CAIRO_STATUS_SUCCESS);
        cairo_t *cr=cairo_create(surface);
        PangoLayout *layout=pango_cairo_create_layout(cr);
        PangoFontDescription *font=pango_font_description_from_string("DejaVu Sans");
        pango_font_description_set_absolute_size(font,size*PANGO_SCALE);
        pango_font_description_set_weight(font,t%2 ? PANGO_WEIGHT_BOLD : PANGO_WEIGHT_NORMAL);
        pango_layout_set_font_description(layout,font);
        pango_layout_set_text(layout,texts[t],-1);
        pango_layout_set_width(layout,W*PANGO_SCALE);
        pango_layout_set_height(layout,H*PANGO_SCALE);
        pango_layout_set_ellipsize(layout,PANGO_ELLIPSIZE_END);
        cairo_set_source_rgba(cr,.2,.4,.7,t%2 ? .45 : 1);
        pango_cairo_show_layout(cr,layout);
        cairo_surface_flush(surface);
        compare(cairo_image_surface_get_data(surface),W,H,cairo_image_surface_get_stride(surface));
        pango_font_description_free(font);g_object_unref(layout);
        cairo_destroy(cr);cairo_surface_destroy(surface);
    }
    struct card_label_ink untouched={1,2,3,4},out=untouched;
    assert(!card_label_ink_find(&out,NULL,STRIDE,W,H));
    assert(!card_label_ink_find(&out,pixels,4,W,H));
    assert(!card_label_ink_find(&out,pixels,STRIDE,0,H));
    assert(!card_label_ink_find(&out,pixels,SIZE_MAX,W,H));
    assert(!card_label_ink_find(NULL,pixels,STRIDE,W,H));
    assert(memcmp(&out,&untouched,sizeof(out))==0);
    printf("label ink: %d exact clipped/alpha/moving RGB565/XRGB comparisons; immutable sources, padded rows, real glyphs, empty/failure bounds PASS\n",comparisons);
    return 0;
}
