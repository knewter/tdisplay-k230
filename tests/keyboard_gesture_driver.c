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
	assert((a & (KG_SHOW|KG_CANCEL_CARD|KG_CONSUME)) == (KG_SHOW|KG_CANCEL_CARD|KG_CONSUME));
	assert(p->mode==KG_WAIT_SURFACE);
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
		near(p.progress,.5); double held=p.progress;
		kg_motion(&p,1,100,990,190); kg_motion(&p,2,180,988,190); near(p.progress,held);
		kg_motion(&p,1,100,1032,210); kg_motion(&p,2,180,1030,210); near(p.progress,.4);
		kg_up(&p,1,230); kg_up(&p,2,232); settle(&p,232);
		assert(p.mode==KG_WAIT_UNMAP || p.mode==KG_SHOWN);
	} else if (!strcmp(argv[1],"late-second")) {
		kg_down(&p,1,100,1200,100,1232,false,false,false);
		assert(!(kg_down(&p,2,180,1198,300,1232,false,true,false)&KG_SHOW));
		assert(p.mode==KG_IDLE);
	} else if (!strcmp(argv[1],"grip-keys")) {
		p.mode=KG_SHOWN;p.progress=1;
		assert(kg_down(&p,3,100,900,100,1232,true,false,false)==KG_NONE);
		assert(kg_down(&p,3,100,780,110,1232,true,false,false)&KG_CONSUME);
		kg_motion(&p,3,100,990,130); near(p.progress,.5);
		kg_motion(&p,3,100,990,150); near(p.progress,.5);
		kg_motion(&p,3,100,906,170);near(p.progress,.7);
		kg_up(&p,3,180);settle(&p,180);assert(p.mode==KG_SHOWN);
	} else if (!strcmp(argv[1],"stale-velocity")) {
		p.mode=KG_SHOWN;p.progress=1;
		kg_down(&p,3,100,780,100,1232,true,false,false);
		kg_motion(&p,3,100,1000,120);
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
		kg_motion(&p,3,100,990,120);kg_up(&p,3,140);
		settle(&p,140);assert(p.mode==KG_WAIT_UNMAP);
	} else assert(0);
	printf("PASS %s\n",argv[1]);
}
