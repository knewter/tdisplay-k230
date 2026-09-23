#define _GNU_SOURCE
#include "pixman-private.h"
#include <asm/hwprobe.h>
#include <errno.h>
#include <inttypes.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <unistd.h>

/* Pinned 0.46.4 private test API. No library code or arithmetic is replaced:
 * wrappers count a dispatched RVV callback, then invoke the original callback.
 * This process is single-threaded; it is a pixel test, never a cost benchmark. */
static pixman_fast_path_t paths[257];
static pixman_composite_func_t originals[256];
static pixman_implementation_t original;
static uint64_t fast_calls, combine_calls;
#define WRAP_SLOT(N) static void wrap_##N(pixman_implementation_t *imp, pixman_composite_info_t *info) { fast_calls++; originals[N](imp, info); }
#include "rvv-wrappers.h"
static void combine(pixman_implementation_t *imp, pixman_op_t op,
                    uint32_t *dst, const uint32_t *src, const uint32_t *mask, int width) {
    combine_calls++; original.combine_32[op](imp,op,dst,src,mask,width);
}
static void combine_ca(pixman_implementation_t *imp, pixman_op_t op,
                    uint32_t *dst, const uint32_t *src, const uint32_t *mask, int width) {
    combine_calls++; original.combine_32_ca[op](imp,op,dst,src,mask,width);
}
static unsigned install_hooks(int vector) {
    pixman_implementation_t *top = _pixman_internal_only_get_implementation();
    unsigned depth = 0;
    for (pixman_implementation_t *p=top; p; p=p->fallback) depth++;
    /* Source order is general, fast, optional RVV, noop. Refuse another ABI or
     * dispatch chain rather than accidentally counting scalar callbacks. */
    if (depth != (vector ? 4u : 3u)) { fprintf(stderr,"unexpected implementation chain %u\n",depth); exit(2); }
    if (!vector) return depth;
    pixman_implementation_t *rvv=top->fallback;
    original=*rvv;
    unsigned n=0;
    while (rvv->fast_paths[n].op != PIXMAN_OP_NONE) {
        if (n == 256) { fprintf(stderr,"too many fast paths\n"); exit(2); }
        paths[n]=rvv->fast_paths[n]; originals[n]=paths[n].func; paths[n].func=wrappers[n]; n++;
    }
    paths[n]=rvv->fast_paths[n]; rvv->fast_paths=paths;
    for (unsigned i=0; i<PIXMAN_N_OPERATORS; i++) {
        if (rvv->combine_32[i]) rvv->combine_32[i]=combine;
        if (rvv->combine_32_ca[i]) rvv->combine_32_ca[i]=combine_ca;
    }
    return depth;
}
static uint32_t random_state;
static uint32_t next(void) {
    random_state ^= random_state << 13; random_state ^= random_state >> 17;
    random_state ^= random_state << 5; return random_state;
}
static void pixels(uint8_t *data,int stride,int w,int h,int format) {
    for (int y=0;y<h;y++) for (int x=0;x<w;x++) {
        uint32_t v=next();
        if (format==0) ((uint16_t *)(data+y*stride))[x]=(uint16_t)v;
        else {
            uint32_t a=format==2 ? 255 : v>>24;
            uint32_t r=((v>>16)&255)*a/255,g=((v>>8)&255)*a/255,b=(v&255)*a/255;
            ((uint32_t *)(data+y*stride))[x]=(a<<24)|(r<<16)|(g<<8)|b;
        }
    }
}
int main(int argc,char **argv) {
    if (argc<2 || argc>3 || (argc==3 && strcmp(argv[2],"--corrupt"))) return 2;
    struct riscv_hwprobe hw={RISCV_HWPROBE_KEY_IMA_EXT_0,0};
    if (syscall(SYS_riscv_hwprobe,&hw,1,0,NULL,0)<0 || hw.key!=RISCV_HWPROBE_KEY_IMA_EXT_0 || !(hw.value&RISCV_HWPROBE_IMA_V)) {
        puts("K230_PIXELS_SKIP no usable standard V"); return 77;
    }
    const char *disabled=getenv("PIXMAN_DISABLE");
    if (disabled && strcmp(disabled,"rvv")) { fputs("unsupported disable policy\n",stderr);return 2; }
    int vector=!disabled;
    if (strcmp(pixman_version_string(),"0.46.4")) return 2;
    unsigned depth=install_hooks(vector),cases=0;
    const int widths[]={1,7,15,16,17,31,64,568};
    const pixman_format_code_t formats[]={PIXMAN_r5g6b5,PIXMAN_a8r8g8b8,PIXMAN_x8r8g8b8};
    const char *names[]={"rgb565","argb8888","xrgb8888"};
    const char *modes[]={"copy","over","nearest","bilinear"};
    uint64_t total_fast=0,total_combine=0;
    for (int sf=0;sf<3;sf++) for(int df=0;df<2;df++)
    for (int mode=0;mode<4;mode++) for(unsigned wi=0;wi<sizeof(widths)/sizeof(*widths);wi++) {
        int w=widths[wi],h=9,sw=w*2+9,sh=23,dw=w+8,dh=h+5;
        int ss=((sw*(sf?4:2)+3)&~3)+20,ds=((dw*(df?4:2)+3)&~3)+12;
        size_t sn=(size_t)ss*sh,dn=(size_t)ds*dh;
        uint8_t *s=malloc(sn),*d=malloc(dn);
        if(!s||!d)return 3;
        memset(s,0x96,sn);memset(d,0x69,dn);random_state=0x230af101;
        pixels(s,ss,sw,sh,sf);pixels(d,ds,dw,dh,df);
        pixman_image_t *src=pixman_image_create_bits(formats[sf],sw,sh,(uint32_t *)s,ss);
        pixman_image_t *dst=pixman_image_create_bits(formats[df],dw,dh,(uint32_t *)d,ds);
        if(!src||!dst)return 3;
        pixman_region32_t clip;pixman_region32_init_rect(&clip,3,2,w,h);
        if (!pixman_image_set_clip_region32(dst,&clip)) return 3;
        if (mode>=2) {
            pixman_transform_t t;pixman_transform_init_scale(&t,pixman_double_to_fixed(1.25),pixman_double_to_fixed(1.5));
            if(!pixman_image_set_transform(src,&t) || !pixman_image_set_filter(src,mode==2?PIXMAN_FILTER_NEAREST:PIXMAN_FILTER_BILINEAR,NULL,0))return 3;
        }
        fast_calls=combine_calls=0;
        pixman_image_composite32(mode==0?PIXMAN_OP_SRC:PIXMAN_OP_OVER,src,NULL,dst,1,1,0,0,3,2,w,h);
        if(argc==3 && cases==0)d[2*ds+3*(df?4:2)]^=1;
        char file[4096],name[160];
        snprintf(name,sizeof(name),"%s-%s-%s-w%d",names[sf],names[df],modes[mode],w);
        int length=snprintf(file,sizeof(file),"%s/%s.bin",argv[1],name);
        if(length<0 || (size_t)length>=sizeof(file))return 3;
        FILE *f=fopen(file,"wb");if(!f)return 3;
        if(fwrite(d,1,dn,f)!=dn || fclose(f))return 3;
        printf("K230_PIXELS_CASE {\"case\":\"%s\",\"bytes\":%zu,\"source_stride\":%d,\"target_stride\":%d,\"rvv_fast_calls\":%"PRIu64",\"rvv_combine_calls\":%"PRIu64"}\n",name,dn,ss,ds,fast_calls,combine_calls);
        total_fast+=fast_calls;total_combine+=combine_calls;cases++;
        pixman_region32_fini(&clip);pixman_image_unref(src);pixman_image_unref(dst);free(s);free(d);
    }
    printf("K230_PIXELS_SUMMARY {\"cases\":%u,\"vector_dispatch_enabled\":%s,\"implementation_depth\":%u,\"rvv_fast_calls\":%"PRIu64",\"rvv_combine_calls\":%"PRIu64",\"corrupt_control\":%s}\n",cases,vector?"true":"false",depth,total_fast,total_combine,argc==3?"true":"false");
    return vector && total_fast+total_combine==0 ? 4 : 0;
}
