import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, map, shareReplay } from 'rxjs';

import {
  AuthState,
  ListResponse,
  LogResponse,
  ModelSchema,
  Perms,
  Registry,
  TreeChildrenResponse,
  TreeResponse,
  UserSettings,
} from './models';
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

  // --- favorites (per-user, server-side) ---
  getFavorites(): Observable<{ favorites: string[] }> {
    return this.http.get<{ favorites: string[] }>(this.url('favorites/'));
  }

  saveFavorites(favorites: string[]): Observable<{ favorites: string[] }> {
    return this.http.put<{ favorites: string[] }>(this.url('favorites/'), { favorites });
  }

  // --- per-user settings (language, timezone, theme, nav order) ---
  getSettings(): Observable<UserSettings> {
    return this.http.get<UserSettings>(this.url('settings/'));
  }

  /** Persist a subset of settings; returns the merged settings. */
  saveSettings(patch: Partial<UserSettings>): Observable<UserSettings> {
    return this.http.patch<UserSettings>(this.url('settings/'), patch);
  }

  // --- audit log ---
  logs(params: Record<string, string | number>): Observable<LogResponse> {
    let httpParams = new HttpParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== '' && v !== null && v !== undefined) {
        httpParams = httpParams.set(k, String(v));
      }
    }
    return this.http.get<LogResponse>(this.url('logs/'), { params: httpParams });
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

  /** The hierarchy tree rooted at this record's topmost ancestor. */
  tree(key: string, pk: string): Observable<TreeResponse> {
    return this.http.get<TreeResponse>(this.url(`tree/${key}/${pk}/`));
  }

  /** One child group of a tree node: searched + paginated, `focus` jumps to the
   *  page holding that child pk (for auto-expanding the lineage). */
  treeChildren(
    key: string,
    pk: string | number,
    accessor: string,
    opts: { page?: number; search?: string; focus?: string | number } = {},
  ): Observable<TreeChildrenResponse> {
    let params = new HttpParams();
    if (opts.page) {
      params = params.set('page', String(opts.page));
    }
    if (opts.search) {
      params = params.set('search', opts.search);
    }
    if (opts.focus !== undefined && opts.focus !== null && !opts.search) {
      params = params.set('focus', String(opts.focus));
    }
    return this.http.get<TreeChildrenResponse>(
      this.url(`tree-children/${key}/${pk}/${accessor}/`),
      { params },
    );
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

  runAction(
    endpoint: string,
    body: {
      ids?: (number | string)[];
      all?: boolean;
      filters?: Record<string, string | number>;
      params?: Record<string, unknown>;
    },
  ): Observable<unknown> {
    return this.http.post(this.apiBase + endpoint, body);
  }
}
