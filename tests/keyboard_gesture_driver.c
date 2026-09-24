#include "keyboard-gesture.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
static void near(double a, double b) { assert(fabs(a-b)<.005); }
static void init(struct kg_policy *p) { kg_init(p,420,false); }
static void chord(struct kg_policy *p) {
	assert(kg_down(p,1,100,1200,100,1232,false,false,false)==KG_NONE);
	unsigned a=kg_down(p,2,180,1198,150,1232,false,false,false);
	assert((a & (KG_CANCEL_CARD|KG_CONSUME)) == (KG_CANCEL_CARD|KG_CONSUME));
	assert(p->mode==KG_WAIT_SURFACE);
	assert(!(kg_motion(p,1,100,1196,160)&KG_SHOW));
	assert(kg_motion(p,2,180,1166,165)&KG_SHOW);
	kg_surface(p,true); assert(p->mode==KG_SHOW_DRAG);
}
static void settle(struct kg_policy *p, uint64_t start) {
	for (uint64_t t=start+16;t<start+3000;t+=16) {
		unsigned a=kg_tick(p,t);
		if (a&KG_HIDE) break;
		if (p->mode==KG_SHOWN) break;
	}
}
int main(int argc,char **argv) {
	assert(argc==2); struct kg_policy p; init(&p);
	if (!strcmp(argv[1],"early-chord")) {
		chord(&p); kg_motion(&p,1,100,990,170); kg_motion(&p,2,180,988,170);
		near(p.progress,210.0/476); double held=p.progress;
		kg_motion(&p,1,100,990,190); kg_motion(&p,2,180,988,190); near(p.progress,held);
		kg_motion(&p,1,100,1032,210); kg_motion(&p,2,180,1030,210); near(p.progress,168.0/476);
		kg_up(&p,1,230); kg_up(&p,2,232); settle(&p,232);
		assert(p.mode==KG_WAIT_UNMAP || p.mode==KG_SHOWN);
	} else if (!strcmp(argv[1],"late-second")) {
		kg_down(&p,1,100,1200,100,1232,false,false,false);
		assert(!(kg_down(&p,2,180,1198,300,1232,false,true,false)&KG_SHOW));
		assert(p.mode==KG_IDLE);
	} else if (!strcmp(argv[1],"horizontal-first")) {
		kg_down(&p,1,100,1200,100,1232,false,false,false);
		kg_motion(&p,1,350,1200,130);
		assert(p.mode==KG_IDLE);
		assert(!(kg_down(&p,2,180,1198,140,1232,false,true,false)&KG_SHOW));
	} else if (!strcmp(argv[1],"stationary-chord")) {
		kg_down(&p,1,100,1200,100,1232,false,false,false);
		assert(!(kg_down(&p,2,180,1198,130,1232,false,false,false)&KG_SHOW));
		assert(!(kg_motion(&p,1,100,1196,150)&KG_SHOW));
		kg_up(&p,1,180);kg_up(&p,2,181);
		assert(p.mode==KG_IDLE);
	} else if (!strcmp(argv[1],"grip-keys")) {
		p.mode=KG_SHOWN;p.progress=1;
		assert(kg_down(&p,3,100,900,100,1232,true,false,false)==KG_NONE);
		assert(kg_down(&p,3,100,780,110,1232,true,false,false)&KG_CONSUME);
		kg_motion(&p,3,100,990,130); near(p.progress,1-210.0/476);
		kg_motion(&p,3,100,990,150); near(p.progress,1-210.0/476);
		kg_motion(&p,3,100,906,170);near(p.progress,1-126.0/476);
		kg_up(&p,3,180);settle(&p,180);assert(p.mode==KG_SHOWN);
	} else if (!strcmp(argv[1],"settle-interrupt")) {
		p.mode=KG_SETTLE;p.progress=.95;p.target_shown=true;p.last_ms=100;
		assert(kg_down(&p,3,100,800,110,1232,true,false,false)&KG_CONSUME);
		assert(p.mode==KG_GRIP_DRAG);
		near(p.start_progress,.95);
		kg_motion(&p,3,100,900,130);
		near(p.progress,.95-100.0/476);
		assert(kg_tick(&p,180)==KG_NONE);
		kg_motion(&p,3,100,850,200);
		near(p.progress,.95-50.0/476);
		kg_up(&p,3,500);settle(&p,500);assert(p.mode==KG_SHOWN);
	} else if (!strcmp(argv[1],"stale-velocity")) {
		p.mode=KG_SHOWN;p.progress=1;
		kg_down(&p,3,100,780,100,1232,true,false,false);
		kg_motion(&p,3,100,1050,120);
		kg_up(&p,3,400);assert(p.velocity==0);
		settle(&p,400);assert(p.mode==KG_WAIT_UNMAP);
	} else if (!strcmp(argv[1],"surface-loss")) {
		chord(&p);kg_motion(&p,1,100,990,170);
		assert(kg_surface(&p,false)&KG_DIRTY);assert(p.mode==KG_IDLE);
	} else if (!strcmp(argv[1],"overlay-isolation")) {
		assert(kg_down(&p,1,100,1200,100,1232,false,false,true)==KG_NONE);
		assert(p.mode==KG_IDLE);
	} else if (!strcmp(argv[1],"reduced")) {
		kg_init(&p,420,true);p.mode=KG_SHOWN;p.progress=1;
		kg_down(&p,3,100,780,100,1232,true,false,false);
		kg_motion(&p,3,100,1050,120);kg_up(&p,3,140);
		settle(&p,140);assert(p.mode==KG_WAIT_UNMAP);
	} else if (!strcmp(argv[1],"elapsed-cadence")) {
		p.mode=KG_SETTLE;p.progress=.3;p.velocity=.6;p.target_shown=true;p.last_ms=100;
		struct kg_policy q=p;
		kg_tick(&p,116);kg_tick(&p,166);kg_tick(&p,200);
		kg_tick(&q,200);
		near(p.progress,q.progress);near(p.velocity,q.velocity);
	} else if (!strcmp(argv[1],"contact-drain")) {
		chord(&p);
		assert(kg_down(&p,3,250,900,180,1232,true,false,false)&KG_CONSUME);
		assert(p.owned_count==3);
		assert(kg_up(&p,1,190)&KG_CONSUME);
		assert(kg_up(&p,2,191)&KG_CONSUME);
		assert(kg_motion(&p,3,250,920,192)&KG_CONSUME);
		assert(kg_up(&p,3,193)&KG_CONSUME);
		assert(p.owned_count==0);
		init(&p);chord(&p);kg_cancel(&p);
		assert(kg_up(&p,1,200)&KG_CONSUME);
		assert(kg_up(&p,2,201)&KG_CONSUME);
	} else if (!strcmp(argv[1],"map-timeout")) {
		kg_down(&p,1,100,1200,100,1232,false,false,false);
		kg_down(&p,2,180,1198,130,1232,false,false,false);
		assert(kg_motion(&p,1,100,1140,150)&KG_SHOW);
		assert(kg_tick(&p,3200)&KG_HIDE);
		assert(p.mode==KG_IDLE);
		assert(kg_up(&p,1,1010)&KG_CONSUME);
		assert(kg_up(&p,2,1011)&KG_CONSUME);
	} else if (!strcmp(argv[1],"many-contacts")) {
		chord(&p);
		for(int id=3;id<22;id++) assert(kg_down(&p,id,300,950,200+id,1232,true,false,false)&KG_CONSUME);
		assert(p.overflow_contacts==5);
		for(int id=1;id<22;id++) assert(kg_up(&p,id,300+id)&KG_CONSUME);
		assert(p.owned_count==0 && p.overflow_contacts==0);
	} else if (!strcmp(argv[1],"end-stream")) {
		chord(&p);
		assert(p.owned_count==2);
		assert(kg_end_stream(&p,true)&KG_DIRTY);
		assert(p.mode==KG_SHOWN && p.owned_count==0);
		assert(kg_up(&p,1,300)==KG_NONE);
		assert(kg_down(&p,8,100,900,310,1232,true,false,false)==KG_NONE);
		kg_end_stream(&p,false);
		assert(p.mode==KG_IDLE);
	} else if (!strcmp(argv[1],"hide-timeout")) {
		p.mode=KG_WAIT_UNMAP;p.progress=0;p.last_ms=100;
		assert(kg_tick(&p,851)&KG_DIRTY);
		assert(p.mode==KG_SHOWN && p.progress==1);
		assert(kg_down(&p,8,100,900,860,1232,true,false,false)==KG_NONE);
	} else assert(0);
	printf("PASS %s\n",argv[1]);
}
