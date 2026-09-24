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
    down(&p,10);cs_motion(&p,1,p.down_x-180,p.down_y+3,100);
    assert(fabs(cs_card_rect(&p,0).x-(a.x-180))<.001);
    assert(fabs(cs_card_rect(&p,1).x-(b.x-180))<.001);
    assert(cs_card_rect(&p,0).y==a.y);
    struct cs_result r=cs_up(&p,1,101);
    assert(!(r.actions&(CS_EXPAND|CS_CLOSE)) && p.selected==1 && p.mode==CS_DECK);
    assert(cs_card_rect(&p,1).x==a.x);
    down(&p,200);cs_motion(&p,1,p.down_x+1000,p.down_y,300);cs_up(&p,1,301);
    assert(p.selected==0); /* clamp deck beginning; never unsigned underflow */
    cs_finish(&p);
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
    assert(cs_card_rect(&p,1).y==b.y-150);
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
    return 56.0*(1-progress)+target.y*progress+
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
    struct cs_rect target=cs_card_rect(p,p->selected);
    assert(cs_entry_set_geometry(p,0,56,568,1176,
                                 target.x,target.y,target.width,target.height));
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

    /* Side start is not the central quick-switch region. */
    cs_leave(&p);
    assert(cs_begin_entry(&p,5,80,1220,1400,202).consumed);
    assert(!p.entry_quick_allowed);
    entry_geometry(&p);
    cs_entry_motion(&p,5,210,1220,1410);
    assert(cs_entry_up(&p,5).consumed && p.entry_reversing);
    cs_tick(&p,1420);assert(cs_tick(&p,1650).focus_id==202);
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
    cs_entry_motion(&p,10,420,1220,415);
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
    cs_entry_motion(&p,9,420,1220,806);
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
    cs_entry_motion(&p,4,434,1220,1010);
    cs_entry_motion(&p,4,364,1220,1020); /* reverse speed crosses source */
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
    struct cs_rect target=cs_card_rect(&p,p.selected);
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
    target=cs_card_rect(&p,p.selected);
    assert(cs_entry_set_geometry(&p,0,56,568,1176,target.x,target.y,target.width,target.height));
    cs_entry_motion(&p,5,200,1184,83);
    cs_entry_up(&p,5);
    assert(cs_down(&p,6,200,400,84).consumed && p.blocked_until_up);
    cs_up(&p,6,85);
    cs_tick(&p,90);cs_tick(&p,325);
    assert(p.mode==CS_NORMAL && !p.blocked_until_up);
    cs_begin_entry(&p,2,200,1220,190,101);
    target=cs_card_rect(&p,p.selected);
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
    target=cs_card_rect(&p,p.selected);
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
    target=cs_card_rect(&p,p.selected);
    assert(cs_entry_set_geometry(&p,0,56,568,1176,target.x,target.y,target.width,target.height));
    cs_entry_motion(&p,4,200,1130,245);
    const struct cs_card changed[]={{101,CS_PRIVATE,true,true},{202,CS_LIVE,true,true}};
    r=cs_set_cards(&p,changed,2);
    assert(r.actions&CS_RESTORE && p.mode==CS_NORMAL && p.blocked_until_up);
    assert(p.entry_id==0 && p.entry_travel==0 && !p.entry_settling);
    cs_up(&p,4,241);assert(!p.blocked_until_up);
    cs_set_cards(&p,restored,2);
    cs_begin_entry(&p,11,200,1220,250,101);
    target=cs_card_rect(&p,p.selected);
    assert(cs_entry_set_geometry(&p,0,56,568,1176,target.x,target.y,target.width,target.height));
    cs_entry_motion(&p,11,200,1120,260);
    const struct cs_card source_gone[]={{202,CS_LIVE,true,true}};
    r=cs_set_cards(&p,source_gone,1);
    assert(r.actions&CS_RESTORE && p.mode==CS_NORMAL && r.focus_id==202);
    assert(p.entry_id==0 && p.entry_progress==0 && p.entry_travel==0);
    assert(p.blocked_until_up && cs_up(&p,11,261).consumed);
    cs_set_cards(&p,restored,2);
    cs_begin_entry(&p,12,200,1220,270,101);
    target=cs_card_rect(&p,p.selected);
    assert(cs_entry_set_geometry(&p,0,56,568,1176,target.x,target.y,target.width,target.height));
    cs_entry_motion(&p,12,200,1160,280);
    r=cs_stream_cancel(&p);
    assert(r.actions&CS_RESTORE && p.mode==CS_NORMAL && p.entry_travel==0);
    assert(!p.blocked_until_up);
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
    c.card_height=300;cs_set_config(&p,&c);
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
    down(&p,200);cs_motion(&p,1,p.down_x-180,p.down_y,300);cs_up(&p,1,301);
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
    cs_motion(&p,1,p.down_x-180,p.down_y,110);cs_up(&p,1,111);
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
        {"enter-expand",enter_expand},{"horizontal",horizontal},{"adjacent-tap",adjacent_tap},
        {"adjacent-throw",adjacent_throw},{"privacy",privacy},{"privacy-transition",privacy_transition},
        {"close-recovery",close_recovery},{"slow-drag",slow_drag},{"source-loss",source_loss},
        {"repeated-timestamp-throw",repeated_timestamp_throw},
        {"repeated-timestamp-rejection",repeated_timestamp_rejection},
        {"restore-gesture",restore_gesture},{"multi-contact",multi_contact},{"edge",edge},
        {"tracked-entry",tracked_entry},
        {"two-axis-entry",two_axis_entry},
        {"two-axis-conflicts",two_axis_conflicts},
        {"direct-carousel",direct_carousel},
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
