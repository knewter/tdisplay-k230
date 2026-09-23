#ifndef CARD_SHELL_TEST_INPUT_H
#define CARD_SHELL_TEST_INPUT_H
#include <stdbool.h>
struct sway_output;
bool card_shell_test_input(struct sway_output *output, int argc, char **argv);
void card_shell_test_input_finish(void);
#endif
