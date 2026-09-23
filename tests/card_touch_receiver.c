#define _GNU_SOURCE
#include <errno.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <wayland-client.h>
#include "xdg-shell-client-protocol.h"
#include "wlr-layer-shell-client-protocol.h"

/* Real protocol receiver: no fake touch delivery and no capture of user text. */
struct app {
    struct wl_display *display;
    struct wl_compositor *compositor;
    struct wl_shm *shm;
    struct wl_seat *seat;
    struct wl_touch *touch;
    struct xdg_wm_base *wm;
    struct zwlr_layer_shell_v1 *layers;
    struct wl_surface *surface;
    struct wl_buffer *buffer;
    void *pixels;
    size_t bytes;
    int width,height;
    struct xdg_surface *xdg;
    struct xdg_toplevel *top;
    struct zwlr_layer_surface_v1 *layer;
    struct wl_callback *ready;
    const char *role,*app_id;
    int32_t ids[16];
    unsigned points;
    bool mapped,failed;
};
static volatile sig_atomic_t stopped;
static void signal_stop(int sig) {(void)sig;stopped=1;}
static void log_event(struct app *a,const char *event,int32_t id,double x,double y) {
    printf("{\"event\":\"%s\",\"role\":\"%s\",\"id\":%d,\"active\":%u,\"x\":%.3f,\"y\":%.3f}\n",
           event,a->role,id,a->points,x,y);
    fflush(stdout);
}
static int point(struct app *a,int32_t id) {
    for (unsigned i=0;i<a->points;i++) if (a->ids[i]==id) return (int)i;
    return -1;
}
static void down(void *data,struct wl_touch *touch,uint32_t serial,uint32_t time,struct wl_surface *surface,int32_t id,wl_fixed_t x,wl_fixed_t y) {
    (void)touch;(void)serial;(void)time;(void)surface;
    struct app *a=data;
    if (a->points==16 || point(a,id)>=0) {a->failed=true;log_event(a,"invalid_down",id,0,0);return;}
    a->ids[a->points++]=id;log_event(a,"down",id,wl_fixed_to_double(x),wl_fixed_to_double(y));
}
static void up(void *data,struct wl_touch *touch,uint32_t serial,uint32_t time,int32_t id) {
    (void)touch;(void)serial;(void)time;
    struct app *a=data;int index=point(a,id);
    if (index<0) {a->failed=true;log_event(a,"unpaired_up",id,0,0);return;}
    a->ids[index]=a->ids[--a->points];log_event(a,"up",id,0,0);
}
static void motion(void *data,struct wl_touch *touch,uint32_t time,int32_t id,wl_fixed_t x,wl_fixed_t y) {
    (void)touch;(void)time;
    struct app *a=data;
    if (point(a,id)<0) {a->failed=true;log_event(a,"unpaired_motion",id,0,0);return;}
    log_event(a,"motion",id,wl_fixed_to_double(x),wl_fixed_to_double(y));
}
static void frame(void *data,struct wl_touch *touch) {(void)data;(void)touch;}
static void cancel(void *data,struct wl_touch *touch) {
    (void)touch;struct app *a=data;a->points=0;log_event(a,"cancel",-1,0,0);
}
static const struct wl_touch_listener touch_listener={.down=down,.up=up,.motion=motion,.frame=frame,.cancel=cancel};
static void touch_ready(void *data,struct wl_callback *callback,uint32_t serial) {
    (void)serial;wl_callback_destroy(callback);log_event(data,"touch_ready",-1,0,0);
}
static const struct wl_callback_listener sync_listener={.done=touch_ready};
static void caps(void *data,struct wl_seat *seat,uint32_t caps) {
    struct app *a=data;
    if ((caps&WL_SEAT_CAPABILITY_TOUCH) && !a->touch) {
        a->touch=wl_seat_get_touch(seat);wl_touch_add_listener(a->touch,&touch_listener,a);
        struct wl_callback *sync=wl_display_sync(a->display);
        wl_callback_add_listener(sync,&sync_listener,a);
    } else if (!(caps&WL_SEAT_CAPABILITY_TOUCH) && a->touch) {
        wl_touch_destroy(a->touch);a->touch=NULL;log_event(a,"touch_removed",-1,0,0);
    }
}
static const struct wl_seat_listener seat_listener={.capabilities=caps};
static void ping(void *data,struct xdg_wm_base *wm,uint32_t serial) {(void)data;xdg_wm_base_pong(wm,serial);}
static const struct xdg_wm_base_listener wm_listener={.ping=ping};
static void registry(void *data,struct wl_registry *reg,uint32_t name,const char *interface,uint32_t version) {
    struct app *a=data;
    if (!strcmp(interface,"wl_compositor") && version>=4) a->compositor=wl_registry_bind(reg,name,&wl_compositor_interface,4);
    else if (!strcmp(interface,"wl_shm")) a->shm=wl_registry_bind(reg,name,&wl_shm_interface,1);
    else if (!strcmp(interface,"wl_seat") && !a->seat) {
        a->seat=wl_registry_bind(reg,name,&wl_seat_interface,1);wl_seat_add_listener(a->seat,&seat_listener,a);
    } else if (!strcmp(interface,"xdg_wm_base")) {
        a->wm=wl_registry_bind(reg,name,&xdg_wm_base_interface,1);xdg_wm_base_add_listener(a->wm,&wm_listener,a);
    } else if (!strcmp(interface,"zwlr_layer_shell_v1")) a->layers=wl_registry_bind(reg,name,&zwlr_layer_shell_v1_interface,1);
}
static void global_remove(void *data,struct wl_registry *reg,uint32_t name) {(void)data;(void)reg;(void)name;}
static const struct wl_registry_listener registry_listener={.global=registry,.global_remove=global_remove};
static void ready(void *data,struct wl_callback *callback,uint32_t serial) {
    (void)serial;struct app *a=data;wl_callback_destroy(callback);a->ready=NULL;a->mapped=true;log_event(a,"ready",-1,0,0);
}
static const struct wl_callback_listener ready_listener={.done=ready};
static void draw(struct app *a) {
    if (a->width<1 || a->height<1 || a->width>4096 || a->height>4096) {a->failed=true;return;}
    size_t bytes=(size_t)a->width*a->height*4;
    int fd=memfd_create("card-touch-receiver",MFD_CLOEXEC);
    if (fd<0 || ftruncate(fd,(off_t)bytes)<0) {if(fd>=0)close(fd);a->failed=true;return;}
    void *pixels=mmap(NULL,bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
    if (pixels==MAP_FAILED) {close(fd);a->failed=true;return;}
    uint32_t color=!strcmp(a->role,"launcher") ? 0x00553388 : !strcmp(a->role,"bar") ? 0x003377aa : 0x00448855;
    for (size_t i=0;i<bytes/4;i++) ((uint32_t *)pixels)[i]=color;
    struct wl_shm_pool *pool=wl_shm_create_pool(a->shm,fd,(int)bytes);
    struct wl_buffer *buffer=wl_shm_pool_create_buffer(pool,0,a->width,a->height,a->width*4,WL_SHM_FORMAT_XRGB8888);
    wl_shm_pool_destroy(pool);close(fd);
    /* Immutable backing is never rewritten; compositor retains its own reference. */
    if (a->buffer) wl_buffer_destroy(a->buffer);
    if (a->pixels) munmap(a->pixels,a->bytes);
    a->buffer=buffer;a->pixels=pixels;a->bytes=bytes;
    wl_surface_attach(a->surface,buffer,0,0);wl_surface_damage_buffer(a->surface,0,0,a->width,a->height);
    if (!a->mapped && !a->ready) {
        a->ready=wl_surface_frame(a->surface);wl_callback_add_listener(a->ready,&ready_listener,a);
    }
    wl_surface_commit(a->surface);
}
static void xdg_configure(void *data,struct xdg_surface *surface,uint32_t serial) {
    struct app *a=data;xdg_surface_ack_configure(surface,serial);draw(a);
}
static const struct xdg_surface_listener xdg_listener={.configure=xdg_configure};
static void top_configure(void *data,struct xdg_toplevel *top,int32_t width,int32_t height,struct wl_array *states) {
    (void)top;(void)states;struct app *a=data;if(width>0)a->width=width;if(height>0)a->height=height;
}
static void top_close(void *data,struct xdg_toplevel *top) {(void)data;(void)top;stopped=1;}
static const struct xdg_toplevel_listener top_listener={.configure=top_configure,.close=top_close};
static void layer_configure(void *data,struct zwlr_layer_surface_v1 *layer,uint32_t serial,uint32_t width,uint32_t height) {
    struct app *a=data;zwlr_layer_surface_v1_ack_configure(layer,serial);a->width=(int)width;a->height=(int)height;draw(a);
}
static void layer_closed(void *data,struct zwlr_layer_surface_v1 *layer) {(void)data;(void)layer;stopped=1;}
static const struct zwlr_layer_surface_v1_listener layer_listener={.configure=layer_configure,.closed=layer_closed};
int main(int argc,char **argv) {
    struct app a={.role="app",.app_id="k230.touch.one",.width=520,.height=1040};
    for (int i=1;i<argc;i++) {
        if (!strcmp(argv[i],"--role") && i+1<argc) a.role=argv[++i];
        else if (!strcmp(argv[i],"--app-id") && i+1<argc) a.app_id=argv[++i];
        else return 64;
    }
    if (strcmp(a.role,"app") && strcmp(a.role,"launcher") && strcmp(a.role,"bar") && strcmp(a.role,"keyboard")) return 64;
    if (strcmp(a.app_id,"k230.touch.one") && strcmp(a.app_id,"k230.touch.two")) return 64;
    signal(SIGTERM,signal_stop);signal(SIGINT,signal_stop);
    a.display=wl_display_connect(NULL);if(!a.display)return 1;
    struct wl_registry *reg=wl_display_get_registry(a.display);wl_registry_add_listener(reg,&registry_listener,&a);
    if (wl_display_roundtrip(a.display)<0 || !a.compositor || !a.shm || !a.seat) return 1;
    a.surface=wl_compositor_create_surface(a.compositor);
    if (!strcmp(a.role,"app")) {
        if (!a.wm) return 1;
        a.xdg=xdg_wm_base_get_xdg_surface(a.wm,a.surface);xdg_surface_add_listener(a.xdg,&xdg_listener,&a);
        a.top=xdg_surface_get_toplevel(a.xdg);xdg_toplevel_add_listener(a.top,&top_listener,&a);
        xdg_toplevel_set_app_id(a.top,a.app_id);xdg_toplevel_set_title(a.top,"Synthetic touch receiver");
    } else {
        if (!a.layers) return 1;
        bool bar=!strcmp(a.role,"bar"),keyboard=!strcmp(a.role,"keyboard");
        a.layer=zwlr_layer_shell_v1_get_layer_surface(a.layers,a.surface,NULL,
            (bar || keyboard) ? ZWLR_LAYER_SHELL_V1_LAYER_TOP : ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY,
            bar ? "card-touch-bar" : keyboard ? "card-touch-keyboard" : "k230-launcher");
        zwlr_layer_surface_v1_add_listener(a.layer,&layer_listener,&a);
        zwlr_layer_surface_v1_set_size(a.layer,0,bar ? 56 : keyboard ? 300 : 0);
        zwlr_layer_surface_v1_set_anchor(a.layer,(keyboard ? 0 : ZWLR_LAYER_SURFACE_V1_ANCHOR_TOP)|
            ZWLR_LAYER_SURFACE_V1_ANCHOR_LEFT|ZWLR_LAYER_SURFACE_V1_ANCHOR_RIGHT|
            (bar ? 0 : ZWLR_LAYER_SURFACE_V1_ANCHOR_BOTTOM));
        zwlr_layer_surface_v1_set_exclusive_zone(a.layer,bar ? 56 : keyboard ? 300 : -1);
    }
    wl_surface_commit(a.surface);
    while (!stopped && !a.failed) {
        while (wl_display_prepare_read(a.display)!=0) if(wl_display_dispatch_pending(a.display)<0){a.failed=true;goto done;}
        int flushed=wl_display_flush(a.display);
        if(flushed<0 && errno!=EAGAIN){wl_display_cancel_read(a.display);a.failed=true;break;}
        struct pollfd fd={.fd=wl_display_get_fd(a.display),.events=POLLIN|(flushed<0?POLLOUT:0)};
        int result=poll(&fd,1,100);
        if(result>0 && (fd.revents&POLLIN)) {
            if(wl_display_read_events(a.display)<0){a.failed=true;break;}
        } else wl_display_cancel_read(a.display);
        if((result<0 && errno!=EINTR) || (fd.revents&(POLLHUP|POLLERR))){a.failed=true;break;}
        if(wl_display_dispatch_pending(a.display)<0){a.failed=true;break;}
    }
done:
    log_event(&a,a.points ? "exit_active" : "exit",-1,0,0);
    if(a.points)a.failed=true;
    if(a.ready)wl_callback_destroy(a.ready);
    if(a.layer)zwlr_layer_surface_v1_destroy(a.layer);
    if(a.top)xdg_toplevel_destroy(a.top);
    if(a.xdg)xdg_surface_destroy(a.xdg);
    wl_surface_destroy(a.surface);
    if(a.buffer)wl_buffer_destroy(a.buffer);
    if(a.pixels)munmap(a.pixels,a.bytes);
    if(a.touch)wl_touch_destroy(a.touch);
    wl_seat_destroy(a.seat);
    if(a.layers)zwlr_layer_shell_v1_destroy(a.layers);
    if(a.wm)xdg_wm_base_destroy(a.wm);
    wl_shm_destroy(a.shm);wl_compositor_destroy(a.compositor);wl_registry_destroy(reg);wl_display_disconnect(a.display);
    return a.failed ? 2 : 0;
}
