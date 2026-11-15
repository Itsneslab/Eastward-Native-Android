// Darwin stand-in (dm/android/compat): dispatch semaphores and dispatch_time only (POSIX semaphores, monotonic deadlines)
#pragma once
#include <stdint.h>
#include <stdlib.h>
#include <pthread.h>
#include <errno.h>
#include <time.h>
#include <mach/mach_time.h>
typedef uint64_t dispatch_time_t;
#define DISPATCH_TIME_NOW 0ull
#define DISPATCH_TIME_FOREVER (~0ull)
#define NSEC_PER_SEC 1000000000ull
#define NSEC_PER_MSEC 1000000ull
#define NSEC_PER_USEC 1000ull
static inline dispatch_time_t dispatch_time(dispatch_time_t when, int64_t delta) {
    if (when == DISPATCH_TIME_FOREVER) return when;
    uint64_t base = when == DISPATCH_TIME_NOW ? mach_absolute_time() : when;
    return delta < 0 && (uint64_t)-delta > base ? 1 : base + (uint64_t)delta;
}
// Use pthread_cond_timedwait_monotonic_np so dispatch semaphores work on API 29+ (sem_clockwait requires API 30).
typedef struct { pthread_mutex_t mu; pthread_cond_t cv; long v; } *dispatch_semaphore_t;
static inline dispatch_semaphore_t dispatch_semaphore_create(long v) {
    dispatch_semaphore_t d = (dispatch_semaphore_t)malloc(sizeof *d);
    if (!d) return NULL;
    pthread_mutex_init(&d->mu, NULL);
    pthread_cond_init(&d->cv, NULL);
    d->v = v;
    return d;
}
static inline long dispatch_semaphore_signal(dispatch_semaphore_t d) {
    pthread_mutex_lock(&d->mu);
    d->v++;
    pthread_cond_signal(&d->cv);
    pthread_mutex_unlock(&d->mu);
    return 0;
}
static inline long dispatch_semaphore_wait(dispatch_semaphore_t d, dispatch_time_t t) {
    pthread_mutex_lock(&d->mu);
    if (t == DISPATCH_TIME_FOREVER) {
        while (d->v <= 0) pthread_cond_wait(&d->cv, &d->mu);
        d->v--;
        pthread_mutex_unlock(&d->mu);
        return 0;
    }
    struct timespec ts = { (time_t)(t / NSEC_PER_SEC), (long)(t % NSEC_PER_SEC) };
    while (d->v <= 0) {
        int rc = pthread_cond_timedwait_monotonic_np(&d->cv, &d->mu, &ts);
        if (rc == ETIMEDOUT || (rc != 0 && rc != EINTR)) {
            if (d->v > 0) break;
            pthread_mutex_unlock(&d->mu);
            return 1;
        }
    }
    d->v--;
    pthread_mutex_unlock(&d->mu);
    return 0;
}
static inline void dispatch_release(void *o) {
    if (o) {
        dispatch_semaphore_t d = (dispatch_semaphore_t)o;
        pthread_cond_destroy(&d->cv);
        pthread_mutex_destroy(&d->mu);
        free(d);
    }
}
