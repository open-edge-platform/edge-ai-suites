/*
 * Copyright © 2013 Intel Corporation
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense,
 * and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice (including the next
 * paragraph) shall be included in all copies or substantial portions of the
 * Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
 * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 *
 */

#ifndef CPU_TOP_H
#define CPU_TOP_H

#include <stdint.h>

#if defined(__cplusplus)
extern "C" {
#endif

struct cpu_top {
	uint8_t busy;
	int nr_cpu;
	int nr_running;

	int count;
	struct cpu_stat {
		uint64_t user, nice, sys, idle;
		uint64_t total;

		// proc_time = usertime and systemtime for specific pid
		uint64_t proc_time;
	} stat[2];
};

int cpu_top_init(struct cpu_top *cpu);
int cpu_top_update(struct cpu_top *cpu, pid_t pid);
int cpu_model_name(char *name);
pid_t find_pid(const char *process_name);

#if defined(__cplusplus)
} // extern "C"
#endif // __cplusplus

#endif /* CPU_TOP_H */
