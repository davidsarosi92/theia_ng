import { HttpInterceptorFn } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { finalize } from 'rxjs';

/**
 * Tracks how many HTTP requests are in flight, so the UI can show a global
 * "server is busy" indicator. A counter (not a boolean) so overlapping requests
 * keep it active until the last one finishes. Signal-based to fit the zoneless,
 * signal-driven change detection.
 */
@Injectable({ providedIn: 'root' })
export class LoadingService {
  private readonly count = signal(0);

  /** True while one or more HTTP requests are pending. */
  readonly active = computed(() => this.count() > 0);

  begin(): void {
    this.count.update((n) => n + 1);
  }

  end(): void {
    this.count.update((n) => Math.max(0, n - 1));
  }
}

/** Counts every HTTP request in/out, driving {@link LoadingService}. */
export const loadingInterceptor: HttpInterceptorFn = (req, next) => {
  const loading = inject(LoadingService);
  loading.begin();
  return next(req).pipe(finalize(() => loading.end()));
};
