#include <sys/timex.h>
#include <stdio.h>
int main(void) { struct timex t = {0}; int r = adjtimex(&t); if(r < 0) return 1; printf("{\"read_only_modes\":0,\"return_state\":%d,\"frequency_scaled_ppm\":%ld,\"tolerance_scaled_ppm\":%ld,\"tick_us\":%ld,\"status\":%d}\n",r,t.freq,t.tolerance,t.tick,t.status); return 0; }
