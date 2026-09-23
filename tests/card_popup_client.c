#define _GNU_SOURCE
#include <assert.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <wayland-client.h>
#include "xdg-shell-client-protocol.h"
static struct wl_display *display;
static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct xdg_wm_base *wm;
static struct wl_buffer *buffer;
static struct wl_surface *parent, *child;
static struct xdg_surface *parent_xdg;
static void ping(void *data,struct xdg_wm_base *w,uint32_t serial){xdg_wm_base_pong(w,serial);}
static const struct xdg_wm_base_listener wm_events={.ping=ping};
static void global(void *data,struct wl_registry *registry,uint32_t id,const char *name,uint32_t version){
 if(!strcmp(name,"wl_compositor"))compositor=wl_registry_bind(registry,id,&wl_compositor_interface,4);
 if(!strcmp(name,"wl_shm"))shm=wl_registry_bind(registry,id,&wl_shm_interface,1);
 if(!strcmp(name,"xdg_wm_base")){wm=wl_registry_bind(registry,id,&xdg_wm_base_interface,1);xdg_wm_base_add_listener(wm,&wm_events,NULL);}
}
static void removed(void *data,struct wl_registry *r,uint32_t id){}
static const struct wl_registry_listener registry_events={global,removed};
static void configured(void *data,struct xdg_surface *xdg,uint32_t serial){
 struct wl_surface *surface=data;xdg_surface_ack_configure(xdg,serial);
 wl_surface_attach(surface,buffer,0,0);wl_surface_damage(surface,0,0,200,120);wl_surface_commit(surface);
 puts(surface==parent?"parent":"popup");fflush(stdout);
}
static const struct xdg_surface_listener surface_events={configured};
static void top_configure(void *data,struct xdg_toplevel *top,int32_t w,int32_t h,struct wl_array *states){}
static void close_top(void *data,struct xdg_toplevel *top){exit(0);}
static const struct xdg_toplevel_listener top_events={.configure=top_configure,.close=close_top};
static void popup_configure(void *data,struct xdg_popup *popup,int32_t x,int32_t y,int32_t w,int32_t h){}
static void popup_done(void *data,struct xdg_popup *popup){exit(0);}
static const struct xdg_popup_listener popup_events={.configure=popup_configure,.popup_done=popup_done};
int main(void){
 display=wl_display_connect(NULL);assert(display);struct wl_registry *registry=wl_display_get_registry(display);
 wl_registry_add_listener(registry,&registry_events,NULL);assert(wl_display_roundtrip(display)>=0);assert(compositor&&shm&&wm);
 int fd=memfd_create("synthetic-card-popup",0);assert(fd>=0);assert(ftruncate(fd,200*120*4)==0);
 uint32_t *pixels=mmap(NULL,200*120*4,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);assert(pixels!=MAP_FAILED);
 for(int i=0;i<200*120;i++)pixels[i]=0x00df4020;
 struct wl_shm_pool *pool=wl_shm_create_pool(shm,fd,200*120*4);buffer=wl_shm_pool_create_buffer(pool,0,200,120,800,WL_SHM_FORMAT_XRGB8888);
 wl_shm_pool_destroy(pool);close(fd);munmap(pixels,200*120*4);
 parent=wl_compositor_create_surface(compositor);parent_xdg=xdg_wm_base_get_xdg_surface(wm,parent);xdg_surface_add_listener(parent_xdg,&surface_events,parent);
 struct xdg_toplevel *top=xdg_surface_get_toplevel(parent_xdg);xdg_toplevel_add_listener(top,&top_events,NULL);xdg_toplevel_set_app_id(top,"k230.card.popup");xdg_toplevel_set_title(top,"Synthetic popup fixture");wl_surface_commit(parent);
 for(;;){
  assert(wl_display_dispatch_pending(display)>=0);wl_display_flush(display);
  struct pollfd fds[2]={{wl_display_get_fd(display),POLLIN,0},{child?-1:STDIN_FILENO,POLLIN,0}};
  assert(poll(fds,2,-1)>=0);
  if(fds[1].revents&POLLIN){char command;assert(read(STDIN_FILENO,&command,1)==1);
   struct xdg_positioner *position=xdg_wm_base_create_positioner(wm);xdg_positioner_set_size(position,200,120);xdg_positioner_set_anchor_rect(position,0,0,200,120);
   child=wl_compositor_create_surface(compositor);struct xdg_surface *xdg=xdg_wm_base_get_xdg_surface(wm,child);xdg_surface_add_listener(xdg,&surface_events,child);
   struct xdg_popup *popup=xdg_surface_get_popup(xdg,parent_xdg,position);xdg_popup_add_listener(popup,&popup_events,NULL);xdg_positioner_destroy(position);wl_surface_commit(child);
  }
  if(fds[0].revents&POLLIN)assert(wl_display_dispatch(display)>=0);
 }
}
