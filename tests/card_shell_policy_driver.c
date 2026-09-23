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
        {"restore-gesture",restore_gesture},{"multi-contact",multi_contact},{"edge",edge},
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
