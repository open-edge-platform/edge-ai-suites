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

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <string.h>
#include <errno.h>
#include <glob.h>

#include "cpu-top.h"

int cpu_top_init(struct cpu_top *cpu)
{
	memset(cpu, 0, sizeof(*cpu));

	cpu->nr_cpu = sysconf(_SC_NPROCESSORS_ONLN);

	return 0;
}

int cpu_top_update(struct cpu_top *cpu, pid_t pid)
{
	struct cpu_stat *s = &cpu->stat[cpu->count++&1];
	struct cpu_stat *d = &cpu->stat[cpu->count&1];
	uint64_t d_total, d_idle;
	char buf[4096], *b;
	int fd, len = -1;

	fd = open("/proc/stat", 0);
	if (fd < 0)
		return errno;

	len = read(fd, buf, sizeof(buf)-1);
	close(fd);

	if (len < 0)
		return EIO;
	buf[len] = '\0';

// cpu user，nice, system, idle, iowait, irq, softirq
#ifdef __x86_64__
	sscanf(buf, "cpu %lu %lu %lu %lu",
	       &s->user, &s->nice, &s->sys, &s->idle);
#else
	sscanf(buf, "cpu %llu %llu %llu %llu",
	       &s->user, &s->nice, &s->sys, &s->idle);
#endif

	b = strstr(buf, "procs_running");
	if (b)
		cpu->nr_running = atoi(b+sizeof("procs_running")) - 1;

	s->total = s->user + s->nice + s->sys + s->idle;
	if (cpu->count == 1)
		return EAGAIN;

	d_total = s->total - d->total;
	d_idle = s->idle - d->idle;
	// if (d_total)
	// 	cpu->busy = 100 - 100 * d_idle / d_total;
	// else
	// 	cpu->busy = 0;
	if (d_total == 0) {
		cpu->busy = 0;
		return 0;
	}
	
	if (pid <= 0) {
		cpu->busy = 100 - 100 * d_idle / d_total;
	}
	else {
		char proc_file[128];
		char proc_buf[4096];
		sprintf(proc_file, "/proc/%d/stat", pid);
		fd = open(proc_file, 0);
		if (fd < 0) {
			printf("invalid pid: %d\n", pid);
			return errno;
		}
		len = read(fd, proc_buf, sizeof(proc_buf)-1);
		close(fd);
		if (len < 0)
			return EIO;
		proc_buf[len] = '\0';
		uint64_t proc_user, proc_sys;
		sscanf(proc_buf,
			"%*d %*s %*c %*d" //pid,command,state,ppid
			"%*d %*d %*d %*d %*u %*lu %*lu %*lu %*lu"
			"%lu %lu" //usertime,systemtime
			"%*ld %*ld %*ld %*ld %*ld %*ld %*llu"
			"%*lu", //virtual memory size in bytes
			&proc_user, &proc_sys);
		// (proc_times2 - proc_times1) * 100 / (float) (total_cpu_usage2 - total_cpu_usage1)
		s->proc_time = proc_user + proc_sys;
		d->proc_time = s->proc_time - d->proc_time;
		if (d_total)
			cpu->busy = 100 * d->proc_time / d_total;
		else
			cpu->busy = 0;
	}

	return 0;
}


int cpu_model_name(char *model_name) {
	FILE *fp = fopen("/proc/cpuinfo", "r");
    if(NULL == fp) {
        printf("failed to open cpuinfo\n");
		return -1;
	}
    char cpu_model[100] = {0};
 
    while(!feof(fp))
    {
        memset(cpu_model, 0, sizeof(cpu_model));
        fgets(cpu_model, sizeof(cpu_model) - 1, fp); // leave out \n
        
        char* pch = strstr(cpu_model,"model name");
        if (pch)
        {
            char* pch2 = strchr(cpu_model, ':');
            if (pch2)
            {	
                memmove(model_name, pch2 + 2, strlen(cpu_model));
                break;
            } 
            else
            {
				return -1;
            }
        }
    }
    fclose(fp);

	return 0;
}

pid_t find_pid(const char *process_name)
{
    pid_t pid = -1;
    glob_t pglob;
    char *procname, *readbuf;
    int buflen = strlen(process_name) + 2;
    unsigned i;

    /* Get a list of all comm files. man 5 proc */
    if (glob("/proc/*/comm", 0, NULL, &pglob) != 0)
        return pid;

    /* The comm files include trailing newlines, so... */
    procname = malloc(buflen);
    strcpy(procname, process_name);
    procname[buflen - 2] = '\n';
    procname[buflen - 1] = 0;

    /* readbuff will hold the contents of the comm files. */
    readbuf = malloc(buflen);

    for (i = 0; i < pglob.gl_pathc; ++i) {
        FILE *comm;
        char *ret;

        /* Read the contents of the file. */
        if ((comm = fopen(pglob.gl_pathv[i], "r")) == NULL)
            continue;
        ret = fgets(readbuf, buflen, comm);
        fclose(comm);
        if (ret == NULL)
            continue;

        /*
        If comm matches our process name, extract the process ID from the
        path, convert it to a pid_t, and return it.
        */
        if (strcmp(readbuf, procname) == 0) {
            pid = (pid_t)atoi(pglob.gl_pathv[i] + strlen("/proc/"));
            break;
        }
    }

    /* Clean up. */
    free(procname);
    free(readbuf);
    globfree(&pglob);

    return pid;
}
