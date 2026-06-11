import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map, shareReplay } from 'rxjs';

import { AuthState, ListResponse, ModelSchema, Perms, Registry } from './models';
import { getConfig } from './theia-config';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private apiBase = getConfig().apiBase;
  /** Cached registry, shared by every relation widget that needs target perms. */
  private registry$?: Observable<Registry>;

  private url(path: string): string {
    return this.apiBase + path;
  }

  // --- auth ---
  me(): Observable<AuthState> {
    return this.http.get<AuthState>(this.url('me/'));
  }

  login(username: string, password: string): Observable<AuthState> {
    return this.http.post<AuthState>(this.url('login/'), { username, password });
  }

  logout(): Observable<AuthState> {
    return this.http.post<AuthState>(this.url('logout/'), {});
  }

  getRegistry(): Observable<Registry> {
    return this.http.get<Registry>(this.url('schema/'));
  }

  /** Registry fetched once and replayed — used to resolve a relation target's perms. */
  private registry(): Observable<Registry> {
    this.registry$ ??= this.getRegistry().pipe(shareReplay(1));
    return this.registry$;
  }

  /** Permissions the current user has on a model (by registry key). */
  permsFor(modelKey: string): Observable<Perms | undefined> {
    return this.registry().pipe(map((r) => r.models.find((m) => m.key === modelKey)?.perms));
  }

  getSchema(key: string): Observable<ModelSchema> {
    return this.http.get<ModelSchema>(this.url(`schema/${key}/`));
  }

  list(key: string, params: Record<string, string | number>): Observable<ListResponse> {
    let httpParams = new HttpParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== '' && v !== null && v !== undefined) {
        httpParams = httpParams.set(k, String(v));
      }
    }
    return this.http.get<ListResponse>(this.url(`data/${key}/`), { params: httpParams });
  }

  retrieve(key: string, pk: string): Observable<Record<string, unknown>> {
    return this.http.get<Record<string, unknown>>(this.url(`data/${key}/${pk}/`));
  }

  create(key: string, body: unknown): Observable<Record<string, unknown>> {
    return this.http.post<Record<string, unknown>>(this.url(`data/${key}/`), body);
  }

  update(key: string, pk: string, body: unknown): Observable<Record<string, unknown>> {
    return this.http.patch<Record<string, unknown>>(this.url(`data/${key}/${pk}/`), body);
  }

  remove(key: string, pk: string): Observable<unknown> {
    return this.http.delete(this.url(`data/${key}/${pk}/`));
  }

  /** Fetch a page of relation options. `endpoint` is the IR's options_endpoint.
   *  `extra` carries dependent-filter sibling values (depends_on). */
  options(
    endpoint: string,
    search: string,
    page = 1,
    extra: Record<string, string> = {},
  ): Observable<ListResponse> {
    let params = new HttpParams().set('page', String(page));
    if (search) {
      params = params.set('search', search);
    }
    for (const [k, v] of Object.entries(extra)) {
      params = params.set(k, v);
    }
    return this.http.get<ListResponse>(this.apiBase + endpoint, { params });
  }

  runAction(endpoint: string, ids: (number | string)[]): Observable<unknown> {
    return this.http.post(this.apiBase + endpoint, { ids });
  }
}
