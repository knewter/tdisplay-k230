#include "card-shell-policy.h"
#include <limits.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

static bool valid_config(const struct cs_config *c) {
    if (!c) return false;
    const double values[]={c->width,c->height,c->top_reserved,c->bottom_reserved,
        c->inset,c->gap,c->title_height,c->footer_height,c->card_width,c->card_height,
        c->edge_band,c->entry_distance,c->tap_slop,c->select_fraction,
        c->throw_distance,c->throw_speed};
    for (size_t i=0;i<sizeof(values)/sizeof(values[0]);i++)
        if (!isfinite(values[i]) || values[i]<0) return false;
    double available=c->height-c->top_reserved-c->bottom_reserved;
    return c->width>=112 && c->height>=224 && c->width<=16384 && c->height<=16384 &&
        c->top_reserved>=56 && c->footer_height>=56 && c->inset>=24 && c->gap>=8 &&
        c->title_height>=56 && c->card_width>=56 && c->card_height>=56 &&
        c->card_width<=c->width-2*c->inset &&
        c->card_height<=available-c->title_height-c->footer_height-2*c->inset &&
        c->edge_band>0 && c->edge_band<=available && c->entry_distance>c->tap_slop &&
        c->entry_distance<available && c->tap_slop>0 &&
        c->select_fraction>0 && c->select_fraction<=1 &&
        c->throw_distance>c->tap_slop && c->throw_speed>0 &&
        c->close_timeout_ms>0 && c->close_timeout_ms<=60000;
}
struct cs_config cs_default_config(double width,double height) {
    return (struct cs_config){.width=width,.height=height,.top_reserved=56,
        .inset=24,.gap=16,.title_height=128,.footer_height=56,
        .card_width=.84*(width-48),.card_height=.72*(height-56-128-56-48),
        .edge_band=48,.entry_distance=72,.tap_slop=12,.select_fraction=.25,
        .throw_distance=120,.throw_speed=.4,.close_timeout_ms=1500};
}
bool cs_init(struct cs_policy *p,const struct cs_config *config) {
    if (!p || !valid_config(config)) return false;
    *p=(struct cs_policy){.config=*config};
    return true;
}
void cs_finish(struct cs_policy *p) {
    if (!p) return;
    free(p->cards);
    memset(p,0,sizeof(*p));
}
static size_t find(const struct cs_policy *p,uint64_t id) {
    if (id) for (size_t i=0;i<p->count;i++) if (p->cards[i].id==id) return i;
    return SIZE_MAX;
}
static struct cs_result result(const struct cs_policy *p,unsigned actions,bool consumed) {
    return (struct cs_result){.actions=actions,.consumed=consumed,.message=p->message};
}
static uint64_t fallback(const struct cs_policy *p) {
    size_t index=find(p,p->saved_focus_id);
    if (index<p->count && p->cards[index].focusable) return p->saved_focus_id;
    if (p->selected<p->count && p->cards[p->selected].focusable) return p->cards[p->selected].id;
    for (size_t i=0;i<p->count;i++) if (p->cards[i].focusable) return p->cards[i].id;
    return 0;
}
static void reset_drag(struct cs_policy *p) {
    p->contact=false;p->pressed_id=0;p->dx=0;p->dy=0;p->velocity_y=0;p->axis=CS_AXIS_NONE;
}
static enum cs_message card_message(const struct cs_policy *p) {
    if (!p->count) return CS_MESSAGE_EMPTY;
    switch (p->cards[p->selected].content) {
    case CS_PRIVATE:return CS_MESSAGE_PRIVATE;
    case CS_UNAVAILABLE:return CS_MESSAGE_UNAVAILABLE;
    case CS_LIVE:return CS_MESSAGE_NONE;
    }
    return CS_MESSAGE_UNAVAILABLE;
}
struct cs_result cs_leave(struct cs_policy *p) {
    uint64_t focus=fallback(p);
    if (p->contact || p->edge.tracking) {p->blocked_until_up=true;p->blocked_contacts=1;}
    reset_drag(p);
    p->edge.tracking=false;
    p->closing_id=0;p->close_deadline_ms=0;p->mode=CS_NORMAL;
    p->message=CS_MESSAGE_NONE;
    struct cs_result r=result(p,CS_RESTORE|CS_RECONCILE,true);
    r.focus_id=focus;
    return r;
}
static struct cs_result fail(struct cs_policy *p) {
    struct cs_result r=cs_leave(p);
    p->message=CS_MESSAGE_FAILED;r.message=p->message;
    return r;
}
struct cs_result cs_set_cards(struct cs_policy *p,const struct cs_card *cards,size_t count) {
    if ((count && !cards) || count>SIZE_MAX/sizeof(*cards)) return fail(p);
    for (size_t i=0;i<count;i++) {
        if (!cards[i].id || cards[i].content<CS_UNAVAILABLE || cards[i].content>CS_LIVE) return fail(p);
        for (size_t j=0;j<i;j++) if (cards[i].id==cards[j].id) return fail(p);
    }
    struct cs_card *copy=count ? malloc(count*sizeof(*copy)) : NULL;
    if (count && !copy) return fail(p);
    if (count) memcpy(copy,cards,count*sizeof(*copy));
    size_t old_selected=p->selected;
    enum cs_content old_selected_content=p->selected<p->count ? p->cards[p->selected].content : CS_UNAVAILABLE;
    size_t old_pressed=find(p,p->pressed_id);
    enum cs_content old_content=old_pressed<p->count ? p->cards[old_pressed].content : CS_UNAVAILABLE;
    uint64_t selected=p->selected<p->count ? p->cards[p->selected].id : 0;
    free(p->cards);p->cards=copy;p->count=count;
    size_t index=find(p,selected);
    if (index<count) p->selected=index;
    else if (p->selected>=count) p->selected=count ? count-1 : 0;
    unsigned actions=p->mode==CS_NORMAL ? CS_RECONCILE : CS_RECONCILE|CS_REDRAW;
    uint64_t gone=0;
    if (p->mode==CS_DECK && (index==SIZE_MAX ||
            (p->count && p->cards[p->selected].content!=old_selected_content)))
        p->message=card_message(p);
    if (p->closing_id && find(p,p->closing_id)==SIZE_MAX) {
        gone=p->closing_id;
        p->closing_id=0;p->close_deadline_ms=0;p->mode=CS_DECK;
        p->message=count ? CS_MESSAGE_SOURCE_GONE : CS_MESSAGE_EMPTY;
    } else if (p->closing_id && !cs_can_mirror(p,p->closing_id)) {
        p->closing_id=0;p->close_deadline_ms=0;p->mode=CS_DECK;
        p->message=card_message(p);
    }
    size_t pressed=find(p,p->pressed_id);
    if (p->contact && (pressed==SIZE_MAX || pressed!=old_pressed || p->selected!=old_selected ||
            p->cards[pressed].content!=old_content)) {
        reset_drag(p);p->mode=CS_DECK;
        /* The adapter must consume the remainder of the cancelled touch. */
        p->blocked_until_up=true;p->blocked_contacts=1;
        p->message=pressed==SIZE_MAX ? CS_MESSAGE_SOURCE_GONE : card_message(p);
    }
    if (!count && p->mode!=CS_NORMAL) p->message=CS_MESSAGE_EMPTY;
    if (p->saved_focus_id && find(p,p->saved_focus_id)==SIZE_MAX) p->saved_focus_id=0;
    struct cs_result r=result(p,actions,false);r.source_gone_id=gone;
    return r;
}
struct cs_result cs_set_config(struct cs_policy *p,const struct cs_config *config) {
    if (!valid_config(config)) return fail(p);
    p->config=*config;
    if (p->contact) {
        reset_drag(p);p->mode=CS_DECK;p->message=CS_MESSAGE_CANCELLED;
        p->blocked_until_up=true;p->blocked_contacts=1;
    }
    cs_edge_cancel(p);
    return result(p,p->mode==CS_NORMAL ? 0 : CS_REDRAW,false);
}
struct cs_result cs_enter(struct cs_policy *p,uint64_t focused_id) {
    if (p->mode!=CS_NORMAL) return result(p,CS_REDRAW,true);
    p->saved_focus_id=focused_id;
    size_t index=find(p,focused_id);
    if (index<p->count) p->selected=index;
    else if (p->selected>=p->count) p->selected=0;
    reset_drag(p);p->edge.tracking=false;p->mode=CS_DECK;
    p->message=card_message(p);
    return result(p,CS_SHRINK|CS_REDRAW|CS_RECONCILE,true);
}
struct cs_rect cs_content_rect(const struct cs_policy *p) {
    return (struct cs_rect){0,p->config.top_reserved,p->config.width,
        p->config.height-p->config.top_reserved-p->config.bottom_reserved};
}
struct cs_rect cs_card_rect(const struct cs_policy *p,size_t index) {
    if (index>=p->count) return (struct cs_rect){0};
    double pitch=p->config.card_width+p->config.gap;
    return (struct cs_rect){
        .x=(p->config.width-p->config.card_width)/2+((double)index-(double)p->selected)*pitch+
            (p->axis==CS_AXIS_HORIZONTAL ? p->dx : 0),
        .y=p->config.top_reserved+p->config.title_height+p->config.inset+
            (p->cards[index].id==p->pressed_id && p->axis==CS_AXIS_VERTICAL ? p->dy : 0),
        .width=p->config.card_width,.height=p->config.card_height};
}
static bool contains(struct cs_rect r,double x,double y) {
    return isfinite(x) && isfinite(y) && x>=r.x && y>=r.y && x<r.x+r.width && y<r.y+r.height;
}
size_t cs_hit_test(const struct cs_policy *p,double x,double y) {
    if (!contains(cs_content_rect(p),x,y)) return SIZE_MAX;
    for (size_t i=0;i<p->count;i++) if (contains(cs_card_rect(p,i),x,y)) return i;
    return SIZE_MAX;
}
bool cs_can_mirror(const struct cs_policy *p,uint64_t id) {
    size_t index=find(p,id);
    return p->mode!=CS_NORMAL && index<p->count && p->cards[index].content==CS_LIVE;
}
static struct cs_result multiple_contacts(struct cs_policy *p) {
    struct cs_result r=cs_leave(p);
    p->message=CS_MESSAGE_CANCELLED;p->blocked_until_up=true;p->blocked_contacts=2;
    r.message=p->message;
    return r;
}
struct cs_result cs_down(struct cs_policy *p,int32_t contact_id,double x,double y,uint64_t time_ms) {
    if (p->blocked_until_up) {
        if (p->blocked_contacts<UINT_MAX) p->blocked_contacts++;
        return result(p,0,true);
    }
    if (p->contact || p->edge.tracking) return multiple_contacts(p);
    if (p->mode==CS_NORMAL || !contains(cs_content_rect(p),x,y)) return result(p,0,false);
    if (p->mode==CS_CLOSING) {
        p->blocked_until_up=true;p->blocked_contacts=1;return result(p,0,true);
    }
    size_t index=cs_hit_test(p,x,y);
    if (index==SIZE_MAX) {
        p->blocked_until_up=true;p->blocked_contacts=1;return result(p,0,true);
    }
    p->contact=true;p->contact_id=contact_id;p->mode=CS_DRAGGING;
    /* Do not recenter on down: the adjacent card stays under the finger. */
    p->pressed_id=p->cards[index].id;
    p->down_x=p->last_x=x;p->down_y=p->last_y=y;p->last_time_ms=time_ms;
    p->dx=p->dy=p->velocity_y=0;p->axis=CS_AXIS_NONE;
    p->message=card_message(p);
    return result(p,CS_REDRAW,true);
}
static double bound(double value,double extent) {
    return fmax(-extent,fmin(extent,value));
}
struct cs_result cs_motion(struct cs_policy *p,int32_t contact_id,double x,double y,uint64_t time_ms) {
    if (p->blocked_until_up) return result(p,0,true);
    if (!p->contact || contact_id!=p->contact_id) return result(p,0,false);
    if (!isfinite(x) || !isfinite(y) || time_ms<p->last_time_ms) return cs_cancel(p);
    double dx=bound(x-p->down_x,2*p->config.width);
    double dy=bound(y-p->down_y,2*p->config.height);
    if (p->axis==CS_AXIS_NONE && hypot(dx,dy)>p->config.tap_slop)
        p->axis=fabs(dx)>=fabs(dy) ? CS_AXIS_HORIZONTAL : CS_AXIS_VERTICAL;
    uint64_t elapsed=time_ms-p->last_time_ms;
    p->velocity_y=elapsed ? (y-p->last_y)/(double)elapsed : 0;
    p->last_x=x;p->last_y=y;p->last_time_ms=time_ms;p->dx=dx;p->dy=dy;
    return result(p,CS_REDRAW,true);
}
struct cs_result cs_up(struct cs_policy *p,int32_t contact_id,uint64_t time_ms) {
    if (p->blocked_until_up) {
        if (p->blocked_contacts) p->blocked_contacts--;
        if (!p->blocked_contacts) p->blocked_until_up=false;
        return result(p,0,true);
    }
    if (!p->contact || contact_id!=p->contact_id) return result(p,0,false);
    if (time_ms<p->last_time_ms) return cs_cancel(p);
    size_t index=find(p,p->pressed_id);
    bool tap=p->axis==CS_AXIS_NONE && hypot(p->dx,p->dy)<=p->config.tap_slop &&
        index<p->count && contains(cs_card_rect(p,index),p->last_x,p->last_y) &&
        contains(cs_content_rect(p),p->last_x,p->last_y);
    bool thrown=p->axis==CS_AXIS_VERTICAL && -p->dy>=p->config.throw_distance &&
        -p->velocity_y>=p->config.throw_speed && time_ms-p->last_time_ms<=150;
    if (tap && index<p->count) {
        p->selected=index;
        if (p->cards[index].content==CS_LIVE && p->cards[index].focusable) {
            uint64_t target=p->cards[index].id;
            p->contact=false; /* This up already completes the touch sequence. */
            struct cs_result r=cs_leave(p);
            r.actions|=CS_EXPAND;r.focus_id=target;
            return r;
        }
    } else if (thrown && index<p->count && p->cards[index].content==CS_LIVE &&
            p->cards[index].closeable) {
        p->contact=false; /* This up completes the owned contact. */
        return cs_request_close(p,p->cards[index].id,time_ms);
    } else if (p->axis==CS_AXIS_HORIZONTAL && p->count) {
        double pitch=p->config.card_width+p->config.gap;
        if (fabs(p->dx)>=pitch*p->config.select_fraction) {
            size_t steps=(size_t)fmax(1,round(fabs(p->dx)/pitch));
            if (p->dx<0) p->selected+=steps>p->count-1-p->selected ? p->count-1-p->selected : steps;
            else p->selected-=steps>p->selected ? p->selected : steps;
        }
    }
    reset_drag(p);p->mode=CS_DECK;p->message=card_message(p);
    return result(p,CS_REDRAW,true);
}
struct cs_result cs_step(struct cs_policy *p,int direction) {
    if (p->mode==CS_NORMAL || (direction!=-1 && direction!=1)) return result(p,0,false);
    if (p->mode==CS_CLOSING) return result(p,0,true);
    if (p->contact) {p->blocked_until_up=true;p->blocked_contacts=1;}
    reset_drag(p);p->mode=CS_DECK;
    if (direction>0 && p->count && p->selected<p->count-1) p->selected++;
    else if (direction<0 && p->selected) p->selected--;
    p->message=card_message(p);
    return result(p,CS_REDRAW,true);
}
struct cs_result cs_request_close(struct cs_policy *p,uint64_t id,uint64_t time_ms) {
    if (p->mode==CS_NORMAL) return result(p,0,false);
    if (p->mode==CS_CLOSING) return result(p,0,true);
    size_t index=find(p,id);
    if (index==SIZE_MAX) {
        p->message=CS_MESSAGE_SOURCE_GONE;return result(p,CS_REDRAW,true);
    }
    if (p->cards[index].content!=CS_LIVE || !p->cards[index].closeable) {
        p->message=p->cards[index].content==CS_PRIVATE ? CS_MESSAGE_PRIVATE : CS_MESSAGE_UNAVAILABLE;
        return result(p,CS_REDRAW,true);
    }
    if (p->contact) {p->blocked_until_up=true;p->blocked_contacts=1;}
    reset_drag(p);p->selected=index;p->closing_id=id;
    p->close_deadline_ms=time_ms>UINT64_MAX-p->config.close_timeout_ms ?
        UINT64_MAX : time_ms+p->config.close_timeout_ms;
    p->mode=CS_CLOSING;p->message=CS_MESSAGE_CLOSING;
    struct cs_result r=result(p,CS_CLOSE|CS_REDRAW,true);r.close_id=id;
    return r;
}
struct cs_result cs_cancel(struct cs_policy *p) {
    bool owned=p->contact;
    reset_drag(p);
    if (owned) {p->blocked_until_up=true;p->blocked_contacts=1;}
    cs_edge_cancel(p);
    if (p->mode==CS_DRAGGING) p->mode=CS_DECK;
    p->message=CS_MESSAGE_CANCELLED;
    return result(p,p->mode==CS_NORMAL ? 0 : CS_REDRAW,owned);
}
struct cs_result cs_tick(struct cs_policy *p,uint64_t time_ms) {
    if (p->mode!=CS_CLOSING || time_ms<p->close_deadline_ms) return result(p,0,false);
    p->closing_id=0;p->close_deadline_ms=0;p->mode=CS_DECK;
    p->message=CS_MESSAGE_CLOSE_TIMEOUT;
    return result(p,CS_REDRAW,false);
}
struct cs_result cs_close_result(struct cs_policy *p,uint64_t id,bool refused) {
    if (p->mode!=CS_CLOSING || id!=p->closing_id) return result(p,0,false);
    p->closing_id=0;p->close_deadline_ms=0;p->mode=CS_DECK;
    p->message=refused ? CS_MESSAGE_CLOSE_REFUSED : CS_MESSAGE_CLOSE_FAILED;
    return result(p,CS_REDRAW,false);
}
struct cs_result cs_edge_down(struct cs_policy *p,int32_t id,double x,double y,uint64_t time_ms) {
    if (p->blocked_until_up) return cs_down(p,id,x,y,time_ms);
    if (p->edge.tracking || p->contact) return multiple_contacts(p);
    if (p->mode!=CS_NORMAL || !contains(cs_content_rect(p),x,y)) return result(p,0,false);
    /* No global bottom edge while a keyboard reserves it: the persistent
     * button remains available; do not steal keys or invent a keyboard edge. */
    if (p->config.bottom_reserved>0 || y<p->config.height-p->config.edge_band) return result(p,0,false);
    p->edge.tracking=true;p->edge.contact_id=id;p->edge.x=x;p->edge.y=y;p->edge.time_ms=time_ms;
    return result(p,0,true);
}
struct cs_result cs_edge_motion(struct cs_policy *p,int32_t id,double x,double y,uint64_t time_ms,uint64_t focused_id) {
    if (p->blocked_until_up) return result(p,0,true);
    if (!p->edge.tracking || id!=p->edge.contact_id) return result(p,0,false);
    if (!isfinite(x) || !isfinite(y) || time_ms<p->edge.time_ms) {
        cs_edge_cancel(p);return result(p,0,true);
    }
    if (p->edge.y-y>=p->config.entry_distance && p->edge.y-y>fabs(x-p->edge.x)) {
        struct cs_result r=cs_enter(p,focused_id);
        p->blocked_until_up=true;p->blocked_contacts=1;
        return r;
    }
    return result(p,0,true);
}
struct cs_result cs_edge_up(struct cs_policy *p,int32_t id) {
    if (p->blocked_until_up) return cs_up(p,id,p->last_time_ms);
    bool owned=p->edge.tracking && id==p->edge.contact_id;
    if (owned) p->edge.tracking=false;
    return result(p,0,owned);
}
void cs_edge_cancel(struct cs_policy *p) {
    if (p->edge.tracking) {p->blocked_until_up=true;p->blocked_contacts=1;}
    p->edge.tracking=false;
}
const char *cs_message_text(enum cs_message message) {
    switch (message) {
    case CS_MESSAGE_NONE:return "Tap to return. Swipe up to close.";
    case CS_MESSAGE_EMPTY:return "No running apps. Open Apps or Home.";
    case CS_MESSAGE_PRIVATE:return "Private preview. Use Windows or Back.";
    case CS_MESSAGE_UNAVAILABLE:return "Preview unavailable. Use Windows or Back.";
    case CS_MESSAGE_CLOSING:return "Closing app. Back and Home remain available.";
    case CS_MESSAGE_CLOSE_REFUSED:return "App stayed open. Return to it or use Back.";
    case CS_MESSAGE_CLOSE_TIMEOUT:return "App has not closed. Return to it or use Back.";
    case CS_MESSAGE_CLOSE_FAILED:return "Could not close app. Return to it or use Back.";
    case CS_MESSAGE_CANCELLED:return "Gesture cancelled. Choose a card or use Back.";
    case CS_MESSAGE_SOURCE_GONE:return "App is no longer visible. Choose a card or use Home.";
    case CS_MESSAGE_FAILED:return "Cards unavailable. Use Apps or Home.";
    }
    return "Cards unavailable. Use Apps or Home.";
}
const char *cs_card_text(enum cs_content content) {
    return content==CS_LIVE ? "Live app" : content==CS_PRIVATE ? "Private app" : "Preview unavailable";
}
