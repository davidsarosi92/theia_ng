import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { ListResponse, ModelSchema, Registry } from './models';
import { getConfig } from './theia-config';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
  private apiBase = getConfig().apiBase;

  private url(path: string): string {
    return this.apiBase + path;
  }

  getRegistry(): Observable<Registry> {
    return this.http.get<Registry>(this.url('schema/'));
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

  /** Fetch relation options. `endpoint` is the IR's options_endpoint (relative to apiBase). */
  options(endpoint: string, search: string): Observable<ListResponse> {
    let params = new HttpParams();
    if (search) {
      params = params.set('search', search);
    }
    return this.http.get<ListResponse>(this.apiBase + endpoint, { params });
  }

  runAction(endpoint: string, ids: (number | string)[]): Observable<unknown> {
    return this.http.post(this.apiBase + endpoint, { ids });
  }
}
