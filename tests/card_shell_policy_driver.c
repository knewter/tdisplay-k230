#include "card-shell-policy.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static struct cs_policy setup(void) {
    struct cs_policy p;
    struct cs_config c=cs_default_config(568,1232);
    assert(cs_init(&p,&c));
    const struct cs_card cards[]={
        {101,CS_LIVE,true,true},{202,CS_LIVE,true,true},
        {303,CS_PRIVATE,true,true},{404,CS_UNAVAILABLE,false,false}
    };
    assert(cs_set_cards(&p,cards,4).actions&CS_RECONCILE);
    return p;
}
static void down(struct cs_policy *p,uint64_t t) {
    struct cs_rect r=cs_card_rect(p,p->selected);
    assert(cs_down(p,1,r.x+r.width/2,r.y+r.height/2,t).consumed);
}
static struct cs_result throw_card(struct cs_policy *p,uint64_t t) {
    down(p,t);
    assert(cs_motion(p,1,p->down_x,p->down_y-150,t+100).consumed);
    return cs_up(p,1,t+101);
}
static void enter_expand(void) {
    struct cs_policy p=setup();
    assert(!cs_can_mirror(&p,101));
    struct cs_result r=cs_enter(&p,202);
    assert((r.actions&(CS_SHRINK|CS_REDRAW))==(CS_SHRINK|CS_REDRAW));
    assert(p.selected==1 && p.mode==CS_DECK && cs_can_mirror(&p,101));
    down(&p,10);r=cs_up(&p,1,11);
    assert(r.actions&CS_EXPAND);assert(r.focus_id==202 && p.mode==CS_NORMAL);
    assert(!p.blocked_until_up && !cs_can_mirror(&p,202));
    cs_finish(&p);
}
static void horizontal(void) {
    struct cs_policy p=setup();cs_enter(&p,101);
    struct cs_rect a=cs_card_rect(&p,0),b=cs_card_rect(&p,1);
    assert(b.x>a.x+a.width && b.y==a.y);
    /* A drag expressed as a fraction of the pitch (not a fixed pixel
     * literal) so this test keeps meaning "well past half a card" however
     * big the overview's own card is -- see overview_geometry's Android-
     * recents sizing, which made the pitch much wider than the pixel
     * literal this test used to hardcode. */
    double pitch=p.config.card_width+p.config.gap;
    double drag=pitch*.6;
    down(&p,10);cs_motion(&p,1,p.down_x-drag,p.down_y+3,100);
    assert(fabs(cs_card_rect(&p,0).x-(a.x-drag))<.001);
    assert(fabs(cs_card_rect(&p,1).x-(b.x-drag))<.001);
    assert(cs_card_rect(&p,0).y==a.y);
    struct cs_result r=cs_up(&p,1,101);
    assert(!(r.actions&(CS_EXPAND|CS_CLOSE)) && p.selected==1 && p.mode==CS_DECK);
    /* Release begins a momentum coast, not an instant snap: the selected
     * index is already correct, but the visual position keeps tracking a
     * decaying scroll_from_dx (continuous with the dragged position) until
     * cs_tick settles it. */
    assert(p.scroll_settling);
    /* Continuous at release: card 1's x here equals its dragged position
     * (b.x-drag, checked above) now re-expressed relative to the new
     * selected index -- dx_new = dx_old + delta*pitch = -.6*pitch+pitch =
     * .4*pitch. */
    assert(fabs(cs_card_rect(&p,1).x-(a.x+.4*pitch))<.001);
    cs_tick(&p,101+240);
    assert(!p.scroll_settling);
    assert(fabs(cs_card_rect(&p,1).x-a.x)<.001);
    down(&p,200);cs_motion(&p,1,p.down_x+1000,p.down_y,300);cs_up(&p,1,301);
    assert(p.selected==0); /* clamp deck beginning; never unsigned underflow */
    cs_finish(&p);
}
/* The user's explicit "more like Android does" ask, superseding the earlier
 * webOS-fan overview (docs/design/shell-ux-critique.md #3): the focused
 * card is Android-recents-sized -- 80% of the panel on both axes, matching
 * the panel's own aspect ratio -- with only a thin sliver of each neighbour
 * peeking at the screen edges, not a 2-3 card fan. The direct bottom-edge
 * app-switch gesture's own entry-target slot stays fully independent of
 * that sizing (card-shell-policy.h's cs_config comment). */
static void overview_geometry(void) {
    struct cs_policy p=setup();
    const struct cs_config *c=&p.config;
    assert(c->card_width>=.75*c->width && c->card_width<=.85*c->width);
    double pitch=c->card_width+c->gap;
    double half_gap=(c->width-c->card_width)/2;
    assert(fabs(half_gap-cs_card_rect(&p,p.selected).x)<.001);
    /* A thin Android-recents-style peek at rest: some of a neighbour is on
     * screen (not zero -- a person can still tell something else is open),
     * but nowhere near the ~46%-of-card-width the prior webOS-fan pass
     * showed, since the card itself now fills most of the panel. */
    double right_neighbor_visible=c->width-(half_gap+pitch);
    assert(right_neighbor_visible>0 && right_neighbor_visible<=.15*c->card_width);
    /* A third card is never visible at all -- there is no room left once
     * the focused card is 80% of the panel width, unlike the prior 2-3
     * card fan. */
    double third_visible=c->width-(half_gap+2*pitch);
    assert(third_visible<0);
    /* Decoupling: the direct-switch entry target stays exactly its own
     * fixed pre-fan formula regardless of card_width/card_height above --
     * this is what keeps that gesture's 30% width threshold, flick
     * velocity, 1:1 tracking and full-size neighbour feel unchanged. The
     * overview's own card is now itself close to full-panel size, so the
     * entry target is no longer necessarily larger than it -- exact-formula
     * match, not a size comparison, is the real proof of independence. */
    struct cs_rect entry_target=cs_entry_target_rect(&p);
    assert(fabs(entry_target.width-.84*(c->width-48))<.001);
    assert(fabs(entry_target.height-.72*(c->height-56-128-56-48))<.001);
    assert(c->card_width<=c->width-2*c->inset);
    assert(c->card_height<=c->height-c->top_reserved-c->bottom_reserved-
        c->title_height-c->footer_height-2*c->inset);
    /* The user's requested ~80-85% of the panel height too, matching the
     * width fraction so the card keeps the panel's own aspect ratio,
     * vertically centered (via card_top_offset) in the space between the
     * title and the footer/hint, not sitting flush under the title. */
    assert(c->card_height>=.75*c->height && c->card_height<=.85*c->height);
    double band=c->height-c->top_reserved-c->bottom_reserved-c->title_height-c->footer_height;
    double block=c->card_top_offset+c->card_height;
    assert(block<=band);
    /* Centered: the leftover margin above the header and below the card
     * are within a pixel of each other. card_top_offset itself is
     * center_margin+header_gap+header_h (it anchors the card, not the
     * header), so the header/gap constants (matching
     * card-shell-policy.c's CS_CARD_HEADER_GAP/CS_CARD_HEADER_H) have to
     * come back out to compare like with like. */
    double margin_above=c->card_top_offset-14.0-44.0,margin_below=band-block;
    assert(fabs(margin_above-margin_below)<2.0);
    cs_finish(&p);
}
/* Overview horizontal scroll physics, requested directly after a real-glass
 * report ("i can't flick to swipe through multiple cards quickly, it snaps
 * to each card as i go"): a fling projects its resting card from the
 * release velocity (v0/CS_SCROLL_OMEGA total signed displacement, the
 * closed form of an exponential-decay coast), so a fast flick can carry
 * several cards, not just the adjacent one; a slow release still snaps to
 * the nearest card (the same formula with v0~=0); a fresh touch mid-coast
 * catches it and continues 1:1 with no jump; the ends clamp with a soft
 * rubber band, not a hard stop. */
static void scroll_fling_multi_card(void) {
    struct cs_policy p=setup();cs_enter(&p,101); /* 4 cards, selected=0 */
    double pitch=p.config.card_width+p.config.gap;
    down(&p,10);
    /* Two real ~8ms-cadence samples with a clean, known velocity: the same
     * touch_window_span selects exactly this pair (dt=8>=CS_ENTRY_MIN_SPAN_MS).
     * The pixel deltas here are bigger than they used to be (-25/-70 rather
     * than -20/-40) because the overview's card -- and so its pitch -- is
     * now much wider (Android-recents sizing, overview_geometry): the same
     * flick speed that used to project past two of the old, narrower cards
     * needs more raw velocity to still project past two of the new, wider
     * ones. */
    cs_motion(&p,1,p.down_x-25,p.down_y,18);
    cs_motion(&p,1,p.down_x-70,p.down_y,26);
    assert(fabs(p.dx-(-70))<.001);
    /* Independently recompute the expected target from the documented
     * formula (mirrors production, not a call into it): v0=-5.625px/ms,
     * projected_dx=dx+v0/CS_SCROLL_OMEGA=-70+(-5.625/.006)=~-1007.5, landing
     * at card round(0-projected_dx/pitch)=round(2.17)=2 -- two cards away,
     * not the single adjacent one a distance-threshold model would give. */
    double v0=(-70.0-(-25.0))/8.0;
    double projected_dx=-70.0+v0/.006;
    size_t expected=(size_t)lround(fmax(0.0,fmin(3.0,0.0-projected_dx/pitch)));
    assert(expected==2);
    struct cs_rect before[4];
    for (size_t i=0;i<4;i++) before[i]=cs_card_rect(&p,i);
    struct cs_result r=cs_up(&p,1,26);
    assert(r.actions&CS_REDRAW);
    /* A fast flick must carry several cards: this one lands well past the
     * single adjacent card, not snapped to it. */
    assert(p.selected==expected);
    assert(p.scroll_settling);
    /* Continuity at release, generalized to a multi-card jump: the newly
     * selected card's on-screen x must equal where it already was under
     * the finger (before[selected].x, captured pre-release with the same
     * dx already baked into cs_card_rect's translation term), not a jump
     * to its eventual rest position. */
    assert(fabs(cs_card_rect(&p,p.selected).x-before[p.selected].x)<.001);
    double previous=fabs(p.dx);
    cs_tick(&p,26+60);
    assert(fabs(p.dx)<previous); /* decays monotonically toward rest */
    cs_tick(&p,26+(uint64_t)p.scroll_duration+5);
    assert(!p.scroll_settling && p.dx==0);
    assert(fabs(cs_card_rect(&p,p.selected).x-(p.config.width-p.config.card_width)/2)<.001);
    cs_finish(&p);
}
static void scroll_slow_release_snaps_nearest(void) {
    struct cs_policy p=setup();cs_enter(&p,101);
    double pitch=p.config.card_width+p.config.gap;
    /* A slow drag well past half a pitch, released gently (no measurable
     * flick): still snaps forward one card, the same "nearest card to the
     * released distance" a fling reduces to at v0~=0. */
    down(&p,10);
    cs_motion(&p,1,p.down_x-pitch*.6,p.down_y,500); /* one slow sample: no history pair, v0=0 */
    assert(cs_up(&p,1,501).actions&CS_REDRAW);
    assert(p.selected==1);
    cs_tick(&p,501+(uint64_t)p.scroll_duration+5);
    assert(!p.scroll_settling && p.dx==0);

    /* A short drag well under half a pitch returns to the same card. */
    down(&p,600);
    cs_motion(&p,1,p.down_x-pitch*.2,p.down_y,1100);
    assert(cs_up(&p,1,1101).actions&CS_REDRAW);
    assert(p.selected==1); /* unchanged */
    cs_finish(&p);
}
static void scroll_catch_mid_coast(void) {
    struct cs_policy p=setup();cs_enter(&p,101);
    double pitch=p.config.card_width+p.config.gap;
    /* A single slow sample (no measurable velocity, the same shape as the
     * horizontal() test's own drag), expressed as a fraction of the pitch
     * rather than a fixed pixel literal (see horizontal()'s own comment):
     * keeps the coast's whole magnitude (a fraction of one pitch's worth of
     * continuity residual) comfortably on-screen throughout, unlike a hard
     * flick's much larger excursion. */
    down(&p,10);
    cs_motion(&p,1,p.down_x-pitch*.6,p.down_y+3,100);
    assert(cs_up(&p,1,101).actions&CS_REDRAW);
    assert(p.selected==1 && p.scroll_settling);
    cs_tick(&p,101+30); /* partway through the coast */
    struct cs_rect mid=cs_card_rect(&p,p.selected);
    double mid_x=mid.x,touch_y=mid.y+5;
    /* A fresh touch at the card's current (mid-coast) screen position
     * catches it: consumed, no jump, and the coast stops settling on its
     * own (it is now an ordinary held drag). */
    assert(cs_down(&p,2,mid_x+5,touch_y,101+30).consumed);
    assert(!p.scroll_settling);
    assert(fabs(cs_card_rect(&p,p.selected).x-mid_x)<.001); /* no jump on catch */
    /* Continues 1:1 from there: a further 15px drag moves the card by
     * exactly 15px from the caught position. */
    cs_motion(&p,2,mid_x+5-15,touch_y,101+38);
    assert(fabs(cs_card_rect(&p,p.selected).x-(mid_x-15))<.001);
    cs_up(&p,2,101+39);
    cs_finish(&p);
}
static void scroll_end_clamp_soft(void) {
    struct cs_policy p=setup();cs_enter(&p,101); /* selected=0, the first card */
    /* A hard fling further into the deck's start end: never underflows
     * past card 0, and the coast's velocity is damped (soft rubber band),
     * not a hard stop at the same magnitude as an unclamped fling. */
    down(&p,10);
    cs_motion(&p,1,p.down_x+20,p.down_y,18);
    cs_motion(&p,1,p.down_x+40,p.down_y,26); /* v0 = +2.5px/ms, well past the deck start */
    assert(cs_up(&p,1,26).actions&CS_REDRAW);
    assert(p.selected==0); /* clamped, never wraps/underflows */
    assert(fabs(p.scroll_release_velocity)<2.5); /* damped below the raw flick velocity */
    cs_tick(&p,26+(uint64_t)p.scroll_duration+5);
    assert(!p.scroll_settling && p.dx==0);
    assert(fabs(cs_card_rect(&p,0).x-(p.config.width-p.config.card_width)/2)<.001);
    cs_finish(&p);

    /* Same at the deck's other end. Two fast samples (a real flick, not a
     * single big drag): with the overview's card now much wider (Android-
     * recents sizing, overview_geometry), the deck's last card is several
     * pitches away, well past what a single drag's dx -- itself capped at
     * 2*width regardless of pitch (cs_motion's own `bound`) -- can reach on
     * raw position alone. A flick's velocity term is not subject to that
     * same cap (scroll_release_velocity_x reads the raw, unclamped touch
     * history), so it reliably lands on the last card however wide the
     * pitch is. */
    struct cs_policy q=setup();cs_enter(&q,101);
    down(&q,10);
    cs_motion(&q,1,q.down_x-1000,q.down_y,18);
    cs_motion(&q,1,q.down_x-3000,q.down_y,26); /* land on the last card first */
    cs_up(&q,1,27);cs_tick(&q,27+(uint64_t)q.scroll_duration+5);
    assert(q.selected==q.count-1 && !q.scroll_settling);
    down(&q,200);
    cs_motion(&q,1,q.down_x-20,q.down_y,208);
    cs_motion(&q,1,q.down_x-40,q.down_y,216); /* fling further past the last card */
    assert(cs_up(&q,1,216).actions&CS_REDRAW);
    assert(q.selected==q.count-1); /* clamped, never runs past the end */
    cs_finish(&q);
}
static void adjacent_tap(void) {
    struct cs_policy p=setup();cs_enter(&p,101);
    struct cs_rect b=cs_card_rect(&p,1);
    assert(b.x<568); /* visible next-card edge */
    assert(cs_down(&p,1,b.x+2,b.y+20,1).consumed);
    assert(cs_card_rect(&p,1).x==b.x); /* no jump on down */
    struct cs_result r=cs_up(&p,1,2);
    assert((r.actions&CS_EXPAND) && r.focus_id==202);
    cs_finish(&p);
}
static void adjacent_throw(void) {
    struct cs_policy p=setup();cs_enter(&p,101);
    struct cs_rect a=cs_card_rect(&p,0),b=cs_card_rect(&p,1);
    cs_down(&p,1,b.x+2,b.y+200,1);
    cs_motion(&p,1,b.x+2,b.y+50,101);
    assert(cs_card_rect(&p,0).y==a.y);
    /* Epsilon, not exact equality: card_top_offset is a computed (not
     * round-constant) value, so (a+dy) and (a)-|dy| can differ in the last
     * float bit despite being mathematically identical. */
    assert(fabs(cs_card_rect(&p,1).y-(b.y-150))<.001);
    struct cs_result r=cs_up(&p,1,102);
    assert((r.actions&CS_CLOSE) && r.close_id==202 && p.selected==1);
    cs_finish(&p);
}
static void privacy(void) {
    struct cs_policy p=setup();cs_enter(&p,303);
    assert(!cs_can_mirror(&p,303) && !cs_can_mirror(&p,404));
    assert(p.message==CS_MESSAGE_PRIVATE);
    down(&p,1);struct cs_result r=cs_up(&p,1,2);
    assert(!(r.actions&CS_EXPAND) && p.message==CS_MESSAGE_PRIVATE);
    r=throw_card(&p,10);assert(!(r.actions&CS_CLOSE));
    assert(!strcmp(cs_card_text(CS_PRIVATE),"Private app"));
    assert(strstr(cs_message_text(p.message),"Back"));
    cs_leave(&p);cs_enter(&p,404);down(&p,200);r=cs_up(&p,1,201);
    assert(!(r.actions&CS_EXPAND) && p.message==CS_MESSAGE_UNAVAILABLE);
    assert(!cs_can_mirror(&p,999));
    cs_finish(&p);
}
static void privacy_transition(void) {
    struct cs_policy p=setup();cs_enter(&p,101);down(&p,1);
    const struct cs_card changed[]={{101,CS_PRIVATE,true,true},{202,CS_LIVE,true,true}};
    struct cs_result r=cs_set_cards(&p,changed,2);
    assert(r.actions&CS_RECONCILE);assert(!cs_can_mirror(&p,101));
    assert(p.mode==CS_DECK && !p.contact && p.blocked_until_up);
    r=cs_up(&p,1,2);assert(!(r.actions&(CS_CLOSE|CS_EXPAND)) && !p.blocked_until_up);
    assert(p.message==CS_MESSAGE_PRIVATE);
    const struct cs_card public_again[]={{101,CS_LIVE,true,true}};
    cs_set_cards(&p,public_again,1);assert(p.message==CS_MESSAGE_NONE);
    cs_set_cards(&p,changed,2);assert(p.message==CS_MESSAGE_PRIVATE && !cs_can_mirror(&p,101));
    cs_finish(&p);
}
static void close_recovery(void) {
    struct cs_policy p=setup();cs_enter(&p,101);
    struct cs_result r=throw_card(&p,10);
    assert((r.actions&CS_CLOSE) && r.close_id==101 && p.mode==CS_CLOSING);
    assert(cs_can_mirror(&p,101)); /* request never destroys the source */
    assert(!cs_tick(&p,1610).actions); /* deadline = 1611 */
    assert(!cs_close_result(&p,202,true).actions); /* stale/other response */
    r=cs_tick(&p,1611);assert(r.message==CS_MESSAGE_CLOSE_TIMEOUT && p.mode==CS_DECK);
    assert(!r.close_id && cs_can_mirror(&p,101));
    r=throw_card(&p,2000);assert(r.close_id==101);
    r=cs_close_result(&p,101,true);assert(r.message==CS_MESSAGE_CLOSE_REFUSED);
    r=throw_card(&p,3000);assert(r.close_id==101);
    r=cs_close_result(&p,101,false);assert(r.message==CS_MESSAGE_CLOSE_FAILED);
    r=throw_card(&p,4000);assert(r.close_id==101);
    r=cs_leave(&p);assert(r.focus_id==101 && (r.actions&CS_RESTORE));
    assert(!cs_tick(&p,10000).actions); /* Back cancels pending UI only */
    cs_finish(&p);
}
static void slow_drag(void) {
    struct cs_policy p=setup();cs_enter(&p,101);down(&p,0);
    cs_motion(&p,1,p.down_x,p.down_y-150,2000);
    assert(!(cs_up(&p,1,2001).actions&CS_CLOSE));
    down(&p,3000);cs_motion(&p,1,p.down_x,p.down_y-150,3100);
    assert(!(cs_up(&p,1,4000).actions&CS_CLOSE)); /* held release is not throw */
    down(&p,5000);cs_motion(&p,1,p.down_x,p.down_y+150,5100);
    assert(!(cs_up(&p,1,5101).actions&CS_CLOSE));
    cs_finish(&p);
}
static void repeated_timestamp_throw(void) {
    /* Millisecond timestamps can repeat without the finger stopping. */
    for (unsigned duplicate=0;duplicate<2;duplicate++) {
        struct cs_policy p=setup();cs_enter(&p,101);down(&p,1000);
        double x=p.down_x,y=p.down_y;
        cs_motion(&p,1,x,y-100,1100);
        cs_motion(&p,1,x,y-150,1120);
        cs_motion(&p,1,x,y-(duplicate ? 150 : 175),1120);
        assert(cs_card_rect(&p,0).y==cs_card_rect(&p,1).y-(duplicate ? 150 : 175));
        struct cs_result r=cs_up(&p,1,1121);
        assert((r.actions&CS_CLOSE) && r.close_id==101);
        cs_finish(&p);
    }
}
static void repeated_timestamp_rejection(void) {
    for (unsigned scenario=0;scenario<5;scenario++) {
        struct cs_policy p=setup();cs_enter(&p,101);down(&p,1000);
        double x=p.down_x,y=p.down_y;
        if (scenario==0) {
            /* No elapsed interval exists at all. */
            cs_motion(&p,1,x,y-100,1000);cs_motion(&p,1,x,y-175,1000);
        } else if (scenario==1) {
            /* A later stationary sample really does describe a stop. */
            cs_motion(&p,1,x,y-175,1100);cs_motion(&p,1,x,y-175,1120);
        } else if (scenario==2) {
            /* Do not carry upward speed through a same-time reversal. */
            cs_motion(&p,1,x,y-175,1100);cs_motion(&p,1,x,y-150,1100);
        } else if (scenario==3) {
            cs_motion(&p,1,x,y-100,2000);cs_motion(&p,1,x,y-175,3000);
            cs_motion(&p,1,x,y-175,3000); /* slow with duplicate endpoint */
        } else {
            cs_motion(&p,1,x,y-175,1100);cs_motion(&p,1,x,y-175,1100);
        }
        assert(!(cs_up(&p,1,scenario==3 ? 3001 : scenario==4 ? 1251 : 1121).actions&CS_CLOSE));
        assert(p.mode==CS_DECK && cs_can_mirror(&p,101));
        cs_finish(&p);
    }
}
static void source_loss(void) {
    struct cs_policy p=setup();cs_enter(&p,101);throw_card(&p,1);
    const struct cs_card remaining[]={{202,CS_LIVE,true,true}};
    struct cs_result r=cs_set_cards(&p,remaining,1);
    assert(r.source_gone_id==101 && p.mode==CS_DECK && p.closing_id==0);
    assert(r.message==CS_MESSAGE_SOURCE_GONE && !cs_can_mirror(&p,101));
    r=cs_leave(&p);assert(r.focus_id==202);
    cs_enter(&p,202);down(&p,1000);r=cs_set_cards(&p,NULL,0);
    assert(p.mode==CS_DECK && r.message==CS_MESSAGE_EMPTY && !p.contact);
    assert(cs_up(&p,1,1001).consumed);
    r=cs_leave(&p);assert(r.focus_id==0); /* workspace fallback */
    cs_finish(&p);
}
static void restore_gesture(void) {
    struct cs_policy p=setup();cs_enter(&p,202);down(&p,1);
    struct cs_result r=cs_leave(&p); /* adapter executes a control after restore */
    assert(r.actions&CS_RESTORE);assert(r.focus_id==202 && p.mode==CS_NORMAL);
    assert(p.blocked_until_up && cs_up(&p,1,2).consumed && !p.blocked_until_up);
    assert(!cs_can_mirror(&p,202));
    cs_finish(&p);
}
static void multi_contact(void) {
    struct cs_policy p=setup();cs_enter(&p,101);down(&p,1);
    struct cs_result r=cs_down(&p,2,100,400,2);
    assert((r.actions&CS_RESTORE) && p.mode==CS_NORMAL && p.blocked_contacts==2);
    assert(cs_motion(&p,1,100,200,3).consumed);
    assert(cs_up(&p,2,4).consumed && p.blocked_until_up);
    assert(cs_down(&p,3,100,400,5).consumed && p.blocked_contacts==2);
    assert(cs_up(&p,1,6).consumed && p.blocked_until_up);
    assert(cs_up(&p,3,7).consumed && !p.blocked_until_up);
    assert(!cs_down(&p,4,100,400,8).consumed);
    cs_finish(&p);
}
static void edge(void) {
    struct cs_policy p=setup();
    assert(!cs_edge_down(&p,1,100,500,1).consumed);
    assert(cs_edge_down(&p,1,200,1220,2).consumed);
    assert(!cs_edge_motion(&p,1,280,1210,3,202).actions);
    assert(cs_edge_up(&p,1).consumed && p.mode==CS_NORMAL); /* tap/horizontal no entry */
    cs_edge_down(&p,2,200,1220,10);
    struct cs_result r=cs_edge_motion(&p,2,205,1100,100,202);
    assert((r.actions&CS_SHRINK) && p.mode==CS_DECK && p.selected==1);
    assert(cs_edge_up(&p,2).consumed && !p.blocked_until_up);
    cs_leave(&p);cs_edge_down(&p,3,200,1220,200);
    r=cs_edge_down(&p,4,100,500,201);
    assert(p.mode==CS_NORMAL && r.message==CS_MESSAGE_CANCELLED);
    cs_edge_up(&p,3);cs_edge_up(&p,4);
    cs_finish(&p);
}
static double entry_finger_y(const struct cs_policy *p) {
    struct cs_rect target=cs_card_rect(p,p->selected);
    double anchor=(1220.0-56.0)/1176.0;
    double progress=p->entry_progress;
    /* Mirrors entry_finger_x: includes the same entry_anchor_shift_y
     * correction cs_entry_visual_rect applies, which keeps the anchor
     * point under the finger exact even though the overview's card_height
     * (used to blend target.height here) is independent of the
     * entry_card_height that established entry_travel/the anchor fraction. */
    return 56.0*(1-progress)+target.y*progress+
        p->entry_anchor_shift_y*progress*p->entry_anchor_factor+
        anchor*(1176.0*(1-progress)+target.height*progress);
}
static double entry_finger_x(const struct cs_policy *p, double source_x) {
    size_t index=SIZE_MAX;
    for (size_t i=0;i<p->count;i++) if (p->cards[i].id==p->entry_id) index=i;
    assert(index<p->count);
    struct cs_rect target=cs_card_rect(p,index);
    double anchor=(p->edge.x-source_x)/568.0;
    double progress=p->entry_progress;
    return source_x*(1-progress)+(target.x-p->entry_dx)*progress+
        p->entry_dx+
        p->entry_anchor_shift*progress*p->entry_anchor_factor+
        anchor*(568.0*(1-progress)+target.width*progress);
}
static void entry_geometry(struct cs_policy *p) {
    /* The direct-switch entry gesture anchors against its own fixed slot
     * (cs_entry_target_rect), decoupled from the overview's own card_rect
     * geometry -- see card-shell-policy.c's cs_entry_target_rect and the
     * adapter.c sync_card/sync_scene_impl call sites it mirrors. */
    struct cs_rect target=cs_entry_target_rect(p);
    assert(cs_entry_set_geometry(p,0,56,568,1176,
                                 target.x,target.y,target.width,target.height));
}
/* Regression for the video-card trap (docs/evidence/card-shell/
 * video-card-gestures/): mpv's --vo=wlshm ignores the compositor's resize
 * configure and keeps reporting its small initial decode buffer (e.g.
 * 480x270) as its view geometry forever, even once its container is really
 * the full panel. adapter.c's sync_card and sync_scene_impl used to feed
 * that stale, tiny size straight into cs_entry_set_geometry as the "source
 * rect" the direct-switch entry gesture drags away from. This shows
 * exactly why that broke: the identical edge/finger state that opens the
 * overview with the real full-panel source rect (entry_geometry() above)
 * is rejected outright with a small one, because the far-oversized anchor
 * fraction ((edge.y-source_y)/source_height) projects the target anchor
 * point far past the bottom of the screen, making travel negative.
 * adapter.c's card_source_size() now always feeds the card's real
 * committed container box for this -- never the view's own (possibly
 * stale) geometry -- see its comment. A rejected call must leave the
 * gesture retryable rather than aborting it: entry_travel stays 0 and a
 * later call with the correct box still succeeds. */
static void entry_geometry_rejects_undersized_source(void) {
    struct cs_policy p=setup();
    assert(cs_begin_entry(&p,1,284,1220,10,202).consumed);
    struct cs_rect target=cs_entry_target_rect(&p);
    assert(!cs_entry_set_geometry(&p,0,56,480,270,
                                  target.x,target.y,target.width,target.height));
    assert(p.entry_travel==0);
    assert(cs_entry_set_geometry(&p,0,56,568,1176,
                                  target.x,target.y,target.width,target.height));
    assert(p.entry_travel>0);
    cs_finish(&p);
}
/* Regression for the video-card overview freeze (docs/evidence/card-shell/
 * video-card-gestures/): adapter.c routes every touch "up" through
 * cs_entry_up_at while mode==CS_ENTERING (its own routing comment), and
 * that function only ever resolves the ORIGINAL bottom-edge contact -- any
 * other contact's up (an interrupting touch landing during the
 * post-release settle) can never reach cs_up, so entry_interrupted_hold
 * used to have no way to clear on its own. Model the worst case directly:
 * an interrupting touch lands mid-settle and never gets an up at all
 * (indistinguishable, from the policy's own state, from a busy compositor
 * whose frame loop keeps issuing ticks without ever routing that up
 * through). The settle must still finish -- and reach a stable mode, here
 * CS_NORMAL via the reversal cs_leave triggers -- on its own bounded
 * timeline instead of hanging on that missing up. */
static void entry_settle_completes_despite_stuck_interrupt(void) {
    struct cs_policy p=setup();
    assert(cs_begin_entry(&p,1,200,1220,0,101).consumed);
    struct cs_rect target=cs_entry_target_rect(&p);
    assert(cs_entry_set_geometry(&p,0,56,568,1176,target.x,target.y,target.width,target.height));
    cs_entry_motion(&p,1,200,1100,10);
    struct cs_result r=cs_entry_up(&p,1);
    assert(r.consumed && p.mode==CS_ENTERING && p.entry_settling);
    assert(cs_down(&p,2,200,400,20).consumed);
    assert(p.entry_reversing && p.entry_interrupted_hold && !p.entry_settling);
    /* Repeated ticks -- as a busy, continuously-redrawing compositor frame
     * loop would issue -- keep it frozen only up to one settle duration,
     * never indefinitely. */
    cs_tick(&p,100);
    assert(p.mode==CS_ENTERING && p.entry_interrupted_hold);
    cs_tick(&p,200);
    assert(p.mode==CS_ENTERING && p.entry_interrupted_hold);
    struct cs_result done=cs_tick(&p,20+240+50);
    assert((done.actions&CS_RESTORE) && p.mode==CS_NORMAL);
    cs_finish(&p);
}
static void finish_entry(struct cs_policy *p,uint64_t time_ms,uint64_t target) {
    assert(cs_entry_up_at(p,p->edge.contact_id,time_ms).consumed);
    assert(p->entry_settling && p->mode==CS_ENTERING);
    double held_x=p->entry_dx, held_y=p->entry_progress;
    assert(!cs_tick(p,time_ms).actions);
    assert(p->entry_dx==held_x && p->entry_progress==held_y);
    if (target) {
        assert(p->entry_goal_progress==0);
        assert(fabs(p->entry_release_dx)==p->config.width);
    } else assert(p->entry_goal_progress==1);
    struct cs_result middle=cs_tick(p,time_ms+40);
    assert((middle.actions&CS_REDRAW) && p->mode==CS_ENTERING);
    struct cs_result endpoint=cs_tick(p,time_ms+240);
    if (target) {
        assert((endpoint.actions&CS_RESTORE) && endpoint.focus_id==target);
        assert(p->mode==CS_NORMAL && !p->entry_order);
        assert(p->expand_id==0); /* no forced deck-to-app expansion */
    } else {
        assert(endpoint.actions&CS_REDRAW);
        assert(p->mode==CS_DECK);
    }
}
static void two_axis_entry(void) {
    struct cs_policy p=setup();
    assert(cs_begin_entry(&p,1,284,1220,10,202).consumed);
    assert(p.entry_origin==1 && p.entry_left_id==101 && p.entry_right_id==303);
    entry_geometry(&p);
    cs_entry_motion(&p,1,284,1120,20); /* first up, then left in same contact */
    struct cs_result move=cs_entry_motion(&p,1,150,1100,30);
    assert(move.consumed && move.focus_id==0 && !(move.actions&CS_CLOSE));
    assert(fabs(entry_finger_x(&p,0)-150)<.001);
    assert(fabs(entry_finger_y(&p)-1100)<.001);
    double x=p.entry_dx,y=p.entry_progress;
    assert(!cs_tick(&p,40).actions && p.entry_dx==x && p.entry_progress==y);
    cs_entry_motion(&p,1,320,1160,50); /* reversal is direct in both axes */
    assert(fabs(entry_finger_x(&p,0)-320)<.001);
    assert(fabs(entry_finger_y(&p)-1160)<.001);
    assert(cs_entry_up(&p,1).consumed && p.entry_reversing);
    cs_tick(&p,60);
    assert(cs_tick(&p,290).focus_id==202 && p.mode==CS_NORMAL);
    assert(!p.entry_order && !p.entry_count);

    /* Bottom-center quick switch rightward chooses the stable left neighbor. */
    assert(cs_begin_entry(&p,2,284,1220,230,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,2,420,1220,240);
    assert(p.entry_progress==0 && fabs(entry_finger_x(&p,0)-420)<.001);
    assert(p.mode==CS_ENTERING && p.entry_target_id==0); /* never focus under contact */
    finish_entry(&p,250,101);
    assert(!p.entry_order && !p.entry_count);
    /* Focus-only raise must not reorder the deck: leftward returns to 202. */
    assert(cs_begin_entry(&p,3,284,1220,600,101).consumed);
    assert(p.entry_right_id==202 && p.entry_left_id==0);
    entry_geometry(&p);
    cs_entry_motion(&p,3,150,1220,610);
    finish_entry(&p,620,202);

    /* Up-then-left can target a private but focusable neighbor safely. */
    assert(cs_begin_entry(&p,4,284,1220,1000,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,4,284,1110,1010);
    cs_entry_motion(&p,4,140,1090,1020);
    assert(p.cards[2].content==CS_PRIVATE && !cs_can_mirror(&p,303));
    finish_entry(&p,1030,303);

    /* A side-start horizontal swipe switches like any other card: distance
     * and flick velocity gate the switch, not where along the bottom edge
     * the gesture started. A prior central-band-only quick-switch gate
     * made an 80%+ swipe starting near either side of the screen snap back
     * even though it plainly qualified on distance and speed. */
    cs_leave(&p);
    assert(cs_begin_entry(&p,5,80,1220,1400,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,5,210,1220,1410);
    assert(cs_entry_up(&p,5).consumed && p.entry_settling && p.entry_target_id==101);
    cs_tick(&p,1420);assert(cs_tick(&p,1650).focus_id==101);
    assert(p.mode==CS_NORMAL);

    /* A vanished target does not substitute a newly mapped neighbor. */
    assert(cs_begin_entry(&p,6,284,1220,1600,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,6,420,1220,1610);
    const struct cs_card gone[]={{202,CS_LIVE,true,true},{303,CS_PRIVATE,true,true},
                                  {404,CS_UNAVAILABLE,false,false},{505,CS_LIVE,true,true}};
    cs_set_cards(&p,gone,4);
    assert(p.mode==CS_ENTERING && p.entry_left_id==101);
    assert(cs_entry_up(&p,6).consumed && p.entry_reversing);
    cs_tick(&p,1620);assert(cs_tick(&p,1850).focus_id==202);
    assert(p.mode==CS_NORMAL);
    cs_finish(&p);
}
static void two_axis_conflicts(void) {
    struct cs_policy p=setup();
    /* A deck end responds within a declared edge bound and never wraps. */
    assert(cs_begin_entry(&p,1,284,1220,10,101).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,1,430,1220,20);
    assert(p.entry_raw_dx==146 && p.entry_dx<=48);
    assert(cs_entry_up(&p,1).consumed && p.entry_reversing);
    cs_tick(&p,30);
    assert(cs_tick(&p,260).focus_id==101 && p.mode==CS_NORMAL);

    const struct cs_card alone[]={{101,CS_LIVE,true,true}};
    cs_set_cards(&p,alone,1);
    assert(cs_begin_entry(&p,2,284,1220,200,101).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,2,135,1220,210);
    assert(p.entry_dx>=-48 && !p.entry_right_id);
    assert(cs_entry_up(&p,2).consumed && p.entry_reversing);
    cs_tick(&p,220);
    assert(cs_tick(&p,450).focus_id==101 && p.mode==CS_NORMAL);

    struct cs_config keyboard=p.config;
    keyboard.bottom_reserved=180;
    /* A real keyboard reservation shrinks available height; a caller
     * changing bottom_reserved must recompute card_height/card_top_offset
     * for it too (same note as keyboard_and_geometry's own fix). */
    keyboard.card_height=300;keyboard.card_top_offset=24;
    assert(cs_set_config(&p,&keyboard).message!=CS_MESSAGE_FAILED);
    assert(!cs_begin_entry(&p,3,284,1220,390,101).consumed);
    keyboard.bottom_reserved=0;
    assert(cs_set_config(&p,&keyboard).message!=CS_MESSAGE_FAILED);
    assert(!cs_begin_entry(&p,3,284,800,390,101).consumed);

    const struct cs_card restored[]={{101,CS_LIVE,true,true},{202,CS_LIVE,true,true}};
    cs_set_cards(&p,restored,2);
    assert(cs_begin_entry(&p,4,284,1220,400,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,4,420,1220,410);
    assert(cs_down(&p,5,300,900,411).consumed);
    assert(p.mode==CS_NORMAL && p.blocked_contacts==2 && !p.entry_order);
    assert(cs_up(&p,4,412).consumed && cs_up(&p,5,413).consumed);
    assert(!p.blocked_until_up);

    assert(cs_begin_entry(&p,10,284,1220,414,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,10,470,1220,415); /* clears distance alone; dt=1ms has no usable velocity */
    assert(cs_entry_up(&p,10).consumed && p.entry_settling);
    cs_tick(&p,416);cs_tick(&p,456);
    double partial_x=p.entry_dx,partial_y=p.entry_progress;
    assert(cs_down(&p,11,300,900,457).consumed && p.entry_reversing);
    assert(fabs(p.entry_dx-partial_x)<10 && fabs(p.entry_progress-partial_y)<.01);
    assert(cs_up(&p,11,458).consumed);
    assert(cs_tick(&p,700).focus_id==202 && p.mode==CS_NORMAL);

    assert(cs_begin_entry(&p,6,284,1220,620,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,6,420,1220,630);
    assert(cs_entry_up(&p,6).consumed && p.entry_target_id==101);
    cs_tick(&p,640);
    const struct cs_card target_gone[]={{202,CS_LIVE,true,true}};
    cs_set_cards(&p,target_gone,1);
    assert(cs_tick(&p,880).focus_id==202 && p.mode==CS_NORMAL);

    cs_set_cards(&p,restored,2);
    assert(cs_begin_entry(&p,9,284,1220,805,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,9,470,1220,806); /* clears distance alone; dt=1ms has no usable velocity */
    assert(cs_entry_up(&p,9).consumed);
    cs_tick(&p,807);
    const struct cs_card target_private[]={{101,CS_PRIVATE,true,true},
                                           {202,CS_LIVE,true,true}};
    cs_set_cards(&p,target_private,2);
    struct cs_result private_result=cs_tick(&p,1047);
    assert((private_result.actions&CS_RESTORE) && private_result.focus_id==101);
    assert(p.mode==CS_NORMAL && !p.entry_order); /* never expand a private mirror */

    cs_set_cards(&p,restored,2);
    assert(cs_begin_entry(&p,7,284,1220,980,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,7,420,1130,990);
    const struct cs_card source_private[]={{101,CS_LIVE,true,true},
                                           {202,CS_PRIVATE,true,true}};
    assert(cs_set_cards(&p,source_private,2).actions&CS_RESTORE);
    assert(p.mode==CS_NORMAL && !p.entry_order && p.blocked_until_up);
    assert(cs_up(&p,7,991).consumed);

    cs_set_cards(&p,restored,2);
    p.config.reduced_motion=true;
    assert(cs_begin_entry(&p,8,284,1220,1000,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,8,420,1220,1010);
    assert(cs_entry_up(&p,8).consumed);
    assert(cs_tick(&p,1020).actions&CS_REDRAW);
    assert(cs_tick(&p,1110).focus_id==101 && p.mode==CS_NORMAL);
    cs_finish(&p);
}
static void direct_carousel(void) {
    struct cs_policy p=setup();
    const struct cs_rect full={0,56,568,1176};
    assert(cs_begin_entry(&p,1,284,1220,10,202).consumed);
    entry_geometry(&p);
    struct cs_rect origin=cs_entry_visual_rect(&p,1,full,true);
    struct cs_rect left=cs_entry_visual_rect(&p,0,full,true);
    struct cs_rect unfocused={0,128,520,960};
    struct cs_rect aligned=cs_entry_visual_rect(&p,0,unfocused,true);
    assert(fabs(origin.x)<.001 && fabs(origin.width-568)<.001);
    assert(fabs(left.x+568)<.001 && fabs(left.width-568)<.001);
    assert(fabs(aligned.y-origin.y)<.001 && fabs(aligned.height-origin.height)<.001);
    struct cs_rect distinct=cs_entry_visual_rect(&p,0,unfocused,false);
    assert(fabs(distinct.y-unfocused.y)<.001 && fabs(distinct.height-unfocused.height)<.001);
    cs_entry_motion(&p,1,384,1220,20);
    origin=cs_entry_visual_rect(&p,1,full,true);
    left=cs_entry_visual_rect(&p,0,full,true);
    assert(fabs(origin.x-100)<.001 && fabs(left.x+468)<.001);
    assert(!cs_tick(&p,100).actions); /* held finger cannot advance */
    assert(fabs(cs_entry_visual_rect(&p,1,full,true).x-origin.x)<.001);
    cs_entry_motion(&p,1,324,1220,110); /* reverse follows x exactly */
    assert(fabs(cs_entry_visual_rect(&p,1,full,true).x-40)<.001);
    cs_entry_motion(&p,1,444,1220,120);
    origin=cs_entry_visual_rect(&p,1,full,true);
    assert(fabs(origin.x-160)<.001 && p.entry_progress==0);
    assert(cs_entry_up_at(&p,1,121).consumed && p.entry_target_id==101);
    assert(!cs_tick(&p,121).actions);
    assert(fabs(cs_entry_visual_rect(&p,1,full,true).x-origin.x)<.001);
    cs_tick(&p,122);
    assert(cs_entry_visual_rect(&p,1,full,true).x>origin.x); /* release momentum */
    assert(p.entry_progress==0); /* no forced zoom to overview */
    struct cs_result done=cs_tick(&p,361);
    assert((done.actions&CS_RESTORE) && done.focus_id==101 && p.mode==CS_NORMAL);
    assert(p.expand_id==0);

    assert(cs_begin_entry(&p,2,284,1220,400,101).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,2,284,1100,410);
    double held=p.entry_progress;
    assert(held>0 && held<1);
    assert(cs_entry_up_at(&p,2,411).consumed && !p.entry_target_id);
    assert(!cs_tick(&p,411).actions && p.entry_progress==held);
    cs_tick(&p,412);
    assert(p.entry_progress>held); /* measured upward derivative continues */
    assert(cs_tick(&p,651).actions&CS_REDRAW && p.mode==CS_DECK);
    cs_leave(&p);
    assert(cs_begin_entry(&p,3,284,1220,700,101).consumed);
    entry_geometry(&p);
    double near_deck_y=1220-.95*p.entry_travel;
    cs_entry_motion(&p,3,284,near_deck_y+40,710);
    cs_entry_motion(&p,3,284,near_deck_y,720);
    assert(p.entry_progress>.9 && p.entry_progress<1);
    assert(cs_entry_up_at(&p,3,721).consumed);
    cs_tick(&p,746);
    assert(p.entry_progress>1 && p.entry_progress<1.08);
    assert(cs_tick(&p,961).actions&CS_REDRAW && p.mode==CS_DECK);
    cs_leave(&p);
    assert(cs_begin_entry(&p,4,284,1220,1000,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,4,534,1220,1010); /* well past the switch distance */
    cs_entry_motion(&p,4,384,1220,1020); /* fast reverse flick still clears the source */
    assert(cs_entry_up_at(&p,4,1021).consumed && p.entry_reversing);
    assert(p.entry_target_id==0); /* visible left neighbor cannot become right */
    assert(cs_tick(&p,1261).focus_id==202 && p.mode==CS_NORMAL);
    cs_finish(&p);
}
static void tracked_entry(void) {
    struct cs_policy p=setup();
    struct cs_result r=cs_begin_entry(&p,1,200,1220,10,101);
    assert(r.consumed && (r.actions&CS_SHRINK) && p.mode==CS_ENTERING);
    assert(p.entry_id==101 && p.entry_progress==0 && cs_can_mirror(&p,101));
    struct cs_rect target=cs_entry_target_rect(&p);
    assert(cs_entry_set_geometry(&p,0,56,568,1176,target.x,target.y,target.width,target.height));
    assert(p.entry_travel>300 && p.entry_travel<400);
    double captured_travel=p.entry_travel;
    double captured_anchor=p.entry_anchor_shift;
    assert(cs_entry_set_geometry(&p,40,100,400,900,target.x+30,target.y+30,
                                 target.width-20,target.height-20));
    assert(p.entry_travel==captured_travel); /* later redraws keep the first anchor */
    assert(p.entry_anchor_shift==captured_anchor);
    r=cs_entry_motion(&p,1,200,1184,20);
    assert(r.consumed && (r.actions&CS_REDRAW) && p.entry_progress<.12);
    assert(fabs(entry_finger_y(&p)-1184)<.001);
    double held=p.entry_progress;
    assert(!cs_tick(&p,25).actions && p.entry_progress==held); /* no drift under contact */
    cs_entry_motion(&p,1,200,1160,30);
    assert(fabs(entry_finger_y(&p)-1160)<.001);
    cs_entry_motion(&p,1,200,1190,35);
    assert(fabs(entry_finger_y(&p)-1190)<.001); /* direct reverse */
    r=cs_entry_up(&p,1);
    assert(r.consumed && (r.actions&CS_REDRAW) && p.mode==CS_ENTERING);
    assert(p.entry_reversing && p.entry_progress>0);
    double partial=p.entry_progress;
    cs_tick(&p,40);
    r=cs_tick(&p,48);
    assert(r.actions&CS_REDRAW && p.entry_progress<=partial);
    r=cs_tick(&p,275);
    assert((r.actions&CS_RESTORE) && r.focus_id==101 && p.mode==CS_NORMAL);
    assert(!p.blocked_until_up && !cs_can_mirror(&p,101));
    /* A new touch during reversal is owned, not delivered to the app. */
    cs_begin_entry(&p,5,200,1220,82,101);
    target=cs_entry_target_rect(&p);
    assert(cs_entry_set_geometry(&p,0,56,568,1176,target.x,target.y,target.width,target.height));
    cs_entry_motion(&p,5,200,1184,83);
    cs_entry_up(&p,5);
    assert(cs_down(&p,6,200,400,84).consumed && p.blocked_until_up);
    cs_up(&p,6,85);
    cs_tick(&p,90);cs_tick(&p,325);
    assert(p.mode==CS_NORMAL && !p.blocked_until_up);
    cs_begin_entry(&p,2,200,1220,190,101);
    target=cs_entry_target_rect(&p);
    assert(cs_entry_set_geometry(&p,0,56,568,1176,target.x,target.y,target.width,target.height));
    cs_entry_motion(&p,2,200,1100,200);
    assert(p.entry_progress<.4 && fabs(entry_finger_y(&p)-1100)<.001);
    r=cs_entry_up(&p,2);
    assert(r.consumed && p.mode==CS_ENTERING && p.entry_settling);
    partial=p.entry_progress;
    assert(cs_tick(&p,205).actions&CS_REDRAW && p.entry_progress>=partial);
    assert(cs_tick(&p,230).actions&CS_REDRAW && p.entry_progress>partial);
    assert(cs_tick(&p,440).actions&CS_REDRAW && p.mode==CS_DECK);
    assert(cs_can_mirror(&p,101));
    cs_leave(&p);
    /* A fresh touch interrupts post-release settling from visible geometry. */
    cs_begin_entry(&p,9,200,1220,401,101);
    target=cs_entry_target_rect(&p);
    assert(cs_entry_set_geometry(&p,0,56,568,1176,target.x,target.y,target.width,target.height));
    cs_entry_motion(&p,9,200,1100,410);
    cs_entry_up(&p,9);
    cs_tick(&p,420);cs_tick(&p,440);
    partial=p.entry_progress;
    assert(cs_down(&p,10,200,400,441).consumed && p.entry_reversing);
    assert(!p.entry_settling && fabs(p.entry_reverse_from-partial)<.01);
    cs_up(&p,10,442);cs_tick(&p,470);cs_tick(&p,682);
    assert(p.mode==CS_NORMAL && !p.blocked_until_up);
    r=cs_begin_entry(&p,3,200,1220,210,303);
    assert(r.consumed && p.mode==CS_NORMAL && p.edge.tracking);
    assert(cs_edge_up(&p,3).consumed && p.mode==CS_NORMAL); /* bottom tap */
    r=cs_begin_entry(&p,3,200,1220,220,303);
    assert(r.consumed && p.mode==CS_NORMAL);
    r=cs_edge_motion(&p,3,200,1100,230,303);
    assert(r.consumed && p.mode==CS_DECK && p.blocked_until_up);
    assert(!cs_can_mirror(&p,303));
    cs_up(&p,3,231);cs_leave(&p);
    const struct cs_card empty[]={{202,CS_LIVE,true,true}};
    cs_set_cards(&p,empty,1);
    assert(cs_begin_entry(&p,8,200,1220,235,0).consumed && p.mode==CS_NORMAL);
    assert(cs_edge_up(&p,8).consumed && p.mode==CS_NORMAL);
    const struct cs_card restored[]={{101,CS_LIVE,true,true},{202,CS_LIVE,true,true}};
    cs_set_cards(&p,restored,2);
    cs_begin_entry(&p,4,200,1220,240,101);
    target=cs_entry_target_rect(&p);
    assert(cs_entry_set_geometry(&p,0,56,568,1176,target.x,target.y,target.width,target.height));
    cs_entry_motion(&p,4,200,1130,245);
    const struct cs_card changed[]={{101,CS_PRIVATE,true,true},{202,CS_LIVE,true,true}};
    r=cs_set_cards(&p,changed,2);
    assert(r.actions&CS_RESTORE && p.mode==CS_NORMAL && p.blocked_until_up);
    assert(p.entry_id==0 && p.entry_travel==0 && !p.entry_settling);
    cs_up(&p,4,241);assert(!p.blocked_until_up);
    cs_set_cards(&p,restored,2);
    cs_begin_entry(&p,11,200,1220,250,101);
    target=cs_entry_target_rect(&p);
    assert(cs_entry_set_geometry(&p,0,56,568,1176,target.x,target.y,target.width,target.height));
    cs_entry_motion(&p,11,200,1120,260);
    const struct cs_card source_gone[]={{202,CS_LIVE,true,true}};
    r=cs_set_cards(&p,source_gone,1);
    assert(r.actions&CS_RESTORE && p.mode==CS_NORMAL && r.focus_id==202);
    assert(p.entry_id==0 && p.entry_progress==0 && p.entry_travel==0);
    assert(p.blocked_until_up && cs_up(&p,11,261).consumed);
    cs_set_cards(&p,restored,2);
    cs_begin_entry(&p,12,200,1220,270,101);
    target=cs_entry_target_rect(&p);
    assert(cs_entry_set_geometry(&p,0,56,568,1176,target.x,target.y,target.width,target.height));
    cs_entry_motion(&p,12,200,1160,280);
    r=cs_stream_cancel(&p);
    assert(r.actions&CS_RESTORE && p.mode==CS_NORMAL && p.entry_travel==0);
    assert(!p.blocked_until_up);
    cs_finish(&p);
}
static void app_switch_swipe(void) {
    /* Scenarios from a real board report: swiping left/right along the
     * bottom edge to switch apps required far more travel than it looked
     * like, momentum was ignored, and an 80%+ swipe still snapped back.
     * Root causes: (1) a horizontal switch was additionally gated on the
     * touch-DOWN x position (a central 25-75% "quick switch" band) unless
     * the same contact also travelled entry_distance upward -- outside
     * that band a pure sideways swipe of any length reversed; (2) release
     * velocity was a single last-interval delta usable only inside a
     * fixed 80ms window after the LAST SAMPLE, so a slightly delayed
     * release, a sparse event cadence, or a naturally decelerating final
     * sample zeroed momentum. These replay the fixed behaviour; see
     * docs/evidence/card-shell/app-switch-swipe/ for the touch-cadence
     * evidence and threshold derivation. */
    struct cs_policy p=setup();

    /* 1. An 80% slow horizontal swipe, low measured release velocity:
     * distance alone must switch, starting near the side of the screen
     * (not the old central quick-switch band). Also checks that release
     * does not itself move the tracked position (no dead stop, no jump). */
    assert(cs_begin_entry(&p,1,90,1220,0,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,1,540,1220,1400); /* a big, unhurried initial travel */
    cs_entry_motion(&p,1,542,1220,1408); /* then real ~8ms-cadence samples, */
    cs_entry_motion(&p,1,544,1220,1416); /* each slow: 0.25 px/ms */
    cs_entry_motion(&p,1,546,1220,1424);
    assert(fabs(p.entry_raw_dx)>.8*p.config.width);
    double held_dx=p.entry_dx;
    struct cs_result up_result=cs_entry_up_at(&p,1,1424);
    assert(up_result.consumed && p.entry_settling && p.entry_target_id==101);
    assert(p.entry_dx==held_dx);
    assert(!cs_tick(&p,1424).actions);
    assert(cs_tick(&p,1664).focus_id==101 && p.mode==CS_NORMAL);
    cs_leave(&p);

    /* 2. A 30% fast flick: below the full switch distance, above half,
     * carried over the line by real ~8ms-cadence release velocity. */
    assert(cs_begin_entry(&p,2,100,1220,0,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,2,128,1220,8);
    cs_entry_motion(&p,2,156,1220,16);
    cs_entry_motion(&p,2,184,1220,24);
    cs_entry_motion(&p,2,212,1220,32);
    cs_entry_motion(&p,2,240,1220,40);
    assert(fabs(p.entry_raw_dx)<.3*p.config.width); /* below full distance */
    assert(cs_entry_up_at(&p,2,41).consumed && p.entry_target_id==101);
    cs_tick(&p,41);assert(cs_tick(&p,281).focus_id==101 && p.mode==CS_NORMAL);
    cs_leave(&p);

    /* 3. A sparse ~100ms event cadence: only two points 100ms apart, still
     * enough to estimate a decisive flick. */
    assert(cs_begin_entry(&p,3,100,1220,0,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,3,160,1220,100);
    cs_entry_motion(&p,3,220,1220,200);
    assert(cs_entry_up_at(&p,3,201).consumed && p.entry_target_id==101);
    cs_tick(&p,201);assert(cs_tick(&p,441).focus_id==101 && p.mode==CS_NORMAL);
    cs_leave(&p);

    /* 4. A flick with a stale last sample: fast ~8ms-cadence motion, but
     * the release event's own timestamp arrives 100ms after the last
     * motion sample (delayed dispatch, or the finger visibly settling
     * just before lift). The old 80ms-since-last-sample gate zeroed
     * momentum here and this exact case snapped back. */
    assert(cs_begin_entry(&p,4,100,1220,0,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,4,140,1220,8);
    cs_entry_motion(&p,4,180,1220,16);
    cs_entry_motion(&p,4,220,1220,24);
    assert(cs_entry_up_at(&p,4,124).consumed && p.entry_target_id==101);
    cs_tick(&p,124);assert(cs_tick(&p,364).focus_id==101 && p.mode==CS_NORMAL);
    cs_leave(&p);

    /* 5. Up then sideways, Android-style: an upward component past
     * entry_distance, then a lateral swipe past the switch distance in
     * the same contact. */
    assert(cs_begin_entry(&p,5,284,1220,0,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,5,284,1120,50); /* up first: entry_drag=100>=entry_distance */
    cs_entry_motion(&p,5,484,1120,90); /* then sideways past the switch distance */
    assert(p.entry_drag>=p.config.entry_distance);
    assert(cs_entry_up_at(&p,5,91).consumed && p.entry_target_id==101);
    cs_tick(&p,91);assert(cs_tick(&p,331).focus_id==101 && p.mode==CS_NORMAL);
    cs_leave(&p);

    /* 6. A reversal flick cancels: a fast rightward excursion well past
     * the switch distance, then a fast reverse flick right before
     * release, ending inside the switch band but heading back toward the
     * start. Must snap back, not switch. */
    assert(cs_begin_entry(&p,6,100,1220,0,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,6,400,1220,40); /* fast right, well past distance */
    cs_entry_motion(&p,6,220,1220,48); /* fast reverse flick before release */
    assert(cs_entry_up_at(&p,6,49).consumed && p.entry_reversing);
    assert(p.entry_target_id==0);
    cs_tick(&p,49);assert(cs_tick(&p,289).focus_id==202 && p.mode==CS_NORMAL);
    cs_leave(&p);

    /* 7. A pure vertical swipe still opens the overview: no lateral
     * component, unaffected by any of the above. */
    assert(cs_begin_entry(&p,7,284,1220,0,202).consumed);
    entry_geometry(&p);
    cs_entry_motion(&p,7,284,1120,50);
    assert(cs_entry_up_at(&p,7,50).consumed && p.entry_settling && !p.entry_target_id);
    cs_tick(&p,50);
    assert(cs_tick(&p,290).actions&CS_REDRAW && p.mode==CS_DECK);

    cs_finish(&p);
}
static void tracked_expansion(void) {
    struct cs_policy p=setup();
    struct cs_config cfg=p.config;cfg.touch_first_motion=true;
    cs_set_config(&p,&cfg);
    cs_enter(&p,101);
    struct cs_rect adjacent=cs_card_rect(&p,1);
    assert(cs_down(&p,1,adjacent.x+2,adjacent.y+20,10).consumed);
    struct cs_result r=cs_up(&p,1,11);
    assert(!(r.actions&CS_RESTORE) && p.mode==CS_EXPANDING && p.expand_id==202);
    assert(p.selected==0 && p.expand_progress==0); /* preserve visible slot */
    assert(!cs_step(&p,1).actions && p.mode==CS_EXPANDING);
    assert(!cs_request_close(&p,202,12).actions && p.mode==CS_EXPANDING);
    cs_tick(&p,100);r=cs_tick(&p,180);
    assert((r.actions&CS_REDRAW) && p.expand_progress==.5);
    r=cs_down(&p,2,200,400,181);
    assert(r.consumed && p.expand_reversing && p.expand_progress==.5);
    r=cs_tick(&p,221);assert(p.expand_progress==.25 && p.mode==CS_EXPANDING);
    r=cs_tick(&p,261);assert(p.mode==CS_DECK && p.expand_progress==0);
    assert(p.blocked_until_up);cs_up(&p,2,262);assert(!p.blocked_until_up);
    assert(cs_card_rect(&p,1).x==adjacent.x);
    assert(cs_down(&p,3,adjacent.x+2,adjacent.y+20,300).consumed);
    cs_up(&p,3,301);assert(p.mode==CS_EXPANDING && p.expand_id==202);
    cs_tick(&p,320);r=cs_tick(&p,480);
    assert(p.expand_progress==1 && p.expand_full_dwell && !(r.actions&CS_RESTORE));
    r=cs_tick(&p,496);
    assert((r.actions&CS_RESTORE) && r.focus_id==202 && p.mode==CS_NORMAL);
    cs_enter(&p,101);down(&p,500);cs_up(&p,1,501);
    assert(p.mode==CS_EXPANDING && p.expand_id==101);
    const struct cs_card changed[]={{101,CS_PRIVATE,true,true},{202,CS_LIVE,true,true}};
    r=cs_set_cards(&p,changed,2);
    assert((r.actions&CS_RESTORE) && p.mode==CS_NORMAL && !cs_can_mirror(&p,101));
    cs_finish(&p);
    struct cs_policy q=setup();
    cfg=q.config;cfg.touch_first_motion=true;cs_set_config(&q,&cfg);
    cs_enter(&q,101);
    adjacent=cs_card_rect(&q,1);
    cs_down(&q,7,adjacent.x+2,adjacent.y+20,10);
    cs_up(&q,7,11);
    cs_tick(&q,100);cs_tick(&q,180);
    assert(q.mode==CS_EXPANDING && q.expand_progress==.5);
    assert(cs_cancel(&q).consumed && q.expand_reversing);
    cs_finish(&q);
}
static void keyboard_and_geometry(void) {
    struct cs_policy p=setup();
    struct cs_config c=p.config;c.bottom_reserved=400;
    /* A real keyboard reservation shrinks available height for both the
     * overview's own slot and the (independent) direct-switch entry slot;
     * a caller changing bottom_reserved must recompute both, per the
     * header's "Recompute card dimensions after changing keyboard
     * reservation" note. */
    c.card_height=300;c.entry_card_height=300;cs_set_config(&p,&c);
    assert(!cs_edge_down(&p,1,200,1200,1).consumed);
    cs_enter(&p,101);
    assert(!cs_down(&p,1,200,20,1).consumed); /* bar still owned by bar */
    assert(!cs_down(&p,1,200,1000,1).consumed); /* keyboard still keyboard */
    struct cs_rect card=cs_card_rect(&p,0),clip=cs_content_rect(&p);
    assert(card.y+card.height+56<=clip.y+clip.height);
    assert(cs_hit_test(&p,card.x+1,card.y+1)==0);
    assert(cs_hit_test(&p,card.x+1,20)==SIZE_MAX);
    cs_finish(&p);
}
static void changed_ids(void) {
    struct cs_policy p=setup();cs_enter(&p,202);
    const struct cs_card reordered[]={{202,CS_LIVE,true,true},{101,CS_LIVE,true,true}};
    cs_set_cards(&p,reordered,2);assert(p.selected==0 && p.cards[p.selected].id==202);
    down(&p,1);
    const struct cs_card bad[]={{202,CS_LIVE,true,true},{202,CS_PRIVATE,true,true}};
    struct cs_result r=cs_set_cards(&p,bad,2);
    assert(p.mode==CS_NORMAL && r.message==CS_MESSAGE_FAILED && (r.actions&CS_RESTORE));
    assert(!cs_can_mirror(&p,202));cs_up(&p,1,2);
    cs_finish(&p);
}
static void many_cards(void) {
    struct cs_policy p=setup();struct cs_card cards[257];
    for (size_t i=0;i<257;i++) cards[i]=(struct cs_card){i+1,CS_LIVE,true,true};
    cs_set_cards(&p,cards,257);cs_enter(&p,257);
    assert(p.count==257 && p.selected==256 && cs_can_mirror(&p,1));
    assert(cs_card_rect(&p,256).x>0);
    down(&p,1);cs_motion(&p,1,p.down_x-1000,p.down_y,100);cs_up(&p,1,101);
    assert(p.selected==256);cs_finish(&p);
}
static void reduced_motion(void) {
    struct cs_policy a=setup(),b=setup();b.config.reduced_motion=true;
    cs_enter(&a,101);cs_enter(&b,101);down(&a,1);down(&b,1);
    cs_motion(&a,1,a.down_x-200,a.down_y,100);cs_motion(&b,1,b.down_x-200,b.down_y,100);
    struct cs_rect ar=cs_card_rect(&a,0),br=cs_card_rect(&b,0);
    assert(ar.x==br.x && ar.y==br.y);cs_up(&a,1,101);cs_up(&b,1,101);
    assert(a.selected==b.selected && a.mode==b.mode);
    struct cs_result ra=throw_card(&a,200),rb=throw_card(&b,200);
    assert(ra.actions==rb.actions && ra.close_id==rb.close_id);
    cs_finish(&a);cs_finish(&b);
}
static void invalid_events(void) {
    struct cs_policy p=setup();cs_enter(&p,101);down(&p,100);
    assert(!cs_motion(&p,2,0,0,101).consumed);
    struct cs_result r=cs_motion(&p,1,NAN,0,101);
    assert(r.message==CS_MESSAGE_CANCELLED && !p.contact && p.blocked_until_up);
    cs_up(&p,1,102);down(&p,200);r=cs_motion(&p,1,100,100,199);
    assert(r.message==CS_MESSAGE_CANCELLED);cs_up(&p,1,200);
    struct cs_config c=p.config;c.width=NAN;r=cs_set_config(&p,&c);
    assert(r.message==CS_MESSAGE_FAILED && p.mode==CS_NORMAL);
    cs_finish(&p);
}
static void buttons(void) {
    struct cs_policy p=setup();
    assert(!cs_step(&p,1).actions && !cs_request_close(&p,101,1).actions);
    cs_enter(&p,101);
    assert(cs_step(&p,1).actions&CS_REDRAW);assert(p.selected==1);
    cs_step(&p,1);assert(p.selected==2 && p.message==CS_MESSAGE_PRIVATE);
    assert(!(cs_request_close(&p,303,100).actions&CS_CLOSE));
    cs_step(&p,-1);assert(p.selected==1);
    assert(!cs_step(&p,42).actions && p.selected==1);
    struct cs_result r=cs_request_close(&p,202,200);
    assert((r.actions&CS_CLOSE) && r.close_id==202 && p.mode==CS_CLOSING);
    assert(!(cs_request_close(&p,202,201).actions&CS_CLOSE)); /* dispatch once */
    assert(!cs_step(&p,1).actions); /* close pending; Back remains available */
    cs_close_result(&p,202,true);assert(p.mode==CS_DECK);
    down(&p,300);cs_step(&p,-1);
    assert(!p.contact && p.blocked_until_up && p.selected==0);
    assert(cs_up(&p,1,301).consumed && !p.blocked_until_up);
    cs_finish(&p);
}
static void stream_cancel(void) {
    struct cs_policy p=setup();cs_enter(&p,101);down(&p,1);
    cs_motion(&p,1,p.down_x-180,p.down_y,100);
    struct cs_result r=cs_stream_cancel(&p); /* no up follows this stream */
    assert(r.consumed && (r.actions&CS_REDRAW) && p.mode==CS_DECK);
    assert(!p.contact && !p.edge.tracking && !p.blocked_until_up && !p.blocked_contacts);
    assert(p.dx==0 && p.dy==0 && p.selected==0);
    double pitch=p.config.card_width+p.config.gap;
    down(&p,200);cs_motion(&p,1,p.down_x-pitch*.6,p.down_y,300);cs_up(&p,1,301);
    assert(p.selected==1 && p.mode==CS_DECK); /* fresh complete stream works */
    down(&p,400);cs_cancel(&p);assert(p.blocked_until_up);
    cs_stream_cancel(&p); /* device removal after locally rejected gesture */
    down(&p,500);r=cs_up(&p,1,501);assert((r.actions&CS_EXPAND) && r.focus_id==202);
    cs_edge_down(&p,2,200,1220,600);assert(p.edge.tracking);
    cs_stream_cancel(&p);assert(!p.edge.tracking && !p.blocked_until_up);
    cs_edge_down(&p,3,200,1220,700);
    r=cs_edge_motion(&p,3,200,1100,800,101);assert(r.actions&CS_SHRINK);
    cs_edge_up(&p,3);assert(!p.blocked_until_up);
    r=cs_request_close(&p,101,900);assert(r.actions&CS_CLOSE);
    cs_down(&p,4,200,400,901);assert(p.blocked_until_up);
    r=cs_stream_cancel(&p);assert(!p.blocked_until_up && p.mode==CS_CLOSING);
    assert(r.message==CS_MESSAGE_CLOSING && p.closing_id==101);
    assert(cs_tick(&p,2400).message==CS_MESSAGE_CLOSE_TIMEOUT);
    cs_finish(&p);
}
static void stream_cancel_multitouch(void) {
    struct cs_policy p=setup();cs_enter(&p,101);down(&p,1);
    cs_down(&p,2,200,400,2);
    assert(p.mode==CS_NORMAL && p.blocked_contacts==2);
    cs_stream_cancel(&p); /* both contacts terminate without any up */
    assert(!p.blocked_until_up && !p.blocked_contacts && !p.contact);
    assert(!cs_down(&p,3,200,400,3).consumed); /* normal app routing restored */
    cs_enter(&p,101);down(&p,10);
    double pitch=p.config.card_width+p.config.gap;
    cs_motion(&p,1,p.down_x-pitch*.6,p.down_y,110);cs_up(&p,1,111);
    assert(p.selected==1 && p.mode==CS_DECK);
    cs_leave(&p);cs_edge_down(&p,4,200,1220,200);
    cs_edge_down(&p,5,100,500,201);assert(p.blocked_contacts==2);
    cs_stream_cancel(&p);assert(!p.blocked_until_up && !p.edge.tracking);
    cs_edge_down(&p,6,200,1220,300);
    assert(cs_edge_motion(&p,6,200,1100,400,202).actions&CS_SHRINK);
    cs_edge_up(&p,6);down(&p,500);
    assert(cs_up(&p,1,501).actions&CS_EXPAND);
    cs_finish(&p);
}
static void randomized(void) {
    struct cs_policy p=setup();unsigned seed=230;
    for (uint64_t i=1;i<10000;i++) {
        seed=seed*1664525u+1013904223u;
        switch ((seed>>16)%8) {
        case 0:cs_enter(&p,101);break;
        case 1:cs_leave(&p);break;
        case 2:cs_down(&p,1,100,400,i);break;
        case 3:cs_motion(&p,1,(seed%800)-100.0,(seed%1600)-100.0,i);break;
        case 4:cs_up(&p,1,i);break;
        case 5:cs_tick(&p,i);break;
        case 6:cs_close_result(&p,101,true);break;
        case 7:cs_cancel(&p);break;
        }
        assert(p.count==4 && p.selected<p.count);
        assert(p.mode!=CS_CLOSING || p.closing_id);
        for (size_t j=0;j<p.count;j++) {
            struct cs_rect r=cs_card_rect(&p,j);
            assert(isfinite(r.x) && isfinite(r.y));
            if (p.cards[j].content!=CS_LIVE || p.mode==CS_NORMAL) assert(!cs_can_mirror(&p,p.cards[j].id));
        }
    }
    cs_finish(&p);
}
int main(int argc,char **argv) {
    struct {const char *name;void (*run)(void);} cases[]={
        {"enter-expand",enter_expand},{"horizontal",horizontal},
        {"overview-geometry",overview_geometry},
        {"scroll-fling-multi-card",scroll_fling_multi_card},
        {"scroll-slow-release-snaps-nearest",scroll_slow_release_snaps_nearest},
        {"scroll-catch-mid-coast",scroll_catch_mid_coast},
        {"scroll-end-clamp-soft",scroll_end_clamp_soft},
        {"adjacent-tap",adjacent_tap},
        {"adjacent-throw",adjacent_throw},{"privacy",privacy},{"privacy-transition",privacy_transition},
        {"close-recovery",close_recovery},{"slow-drag",slow_drag},{"source-loss",source_loss},
        {"repeated-timestamp-throw",repeated_timestamp_throw},
        {"repeated-timestamp-rejection",repeated_timestamp_rejection},
        {"restore-gesture",restore_gesture},{"multi-contact",multi_contact},{"edge",edge},
        {"tracked-entry",tracked_entry},
        {"entry-geometry-rejects-undersized-source",entry_geometry_rejects_undersized_source},
        {"entry-settle-completes-despite-stuck-interrupt",entry_settle_completes_despite_stuck_interrupt},
        {"two-axis-entry",two_axis_entry},
        {"two-axis-conflicts",two_axis_conflicts},
        {"direct-carousel",direct_carousel},
        {"app-switch-swipe",app_switch_swipe},
        {"tracked-expansion",tracked_expansion},
        {"keyboard-geometry",keyboard_and_geometry},{"changed-ids",changed_ids},
        {"many-cards",many_cards},{"reduced-motion",reduced_motion},{"invalid-events",invalid_events},
        {"buttons",buttons},{"stream-cancel",stream_cancel},
        {"stream-cancel-multitouch",stream_cancel_multitouch},{"randomized",randomized}
    };
    assert(argc==2);
    for (size_t i=0;i<sizeof(cases)/sizeof(cases[0]);i++) if (!strcmp(argv[1],cases[i].name)) {
        cases[i].run();printf("PASS %s\n",cases[i].name);return 0;
    }
    return 64;
}
