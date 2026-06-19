import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { I18nService } from './i18n.service';
import { LogEntry, RegistryModel } from './models';
import { MessageKey } from './i18n/messages';
import { cap } from './util';

@Component({
  selector: 'theia-log',
  standalone: true,
  imports: [RouterLink],
  template: `
    <nav class="breadcrumb">
      <a routerLink="/">{{ t('home') }}</a>
      <span class="sep">/</span>
      <span>{{ t('activityLog') }}</span>
    </nav>

    <header class="list-header">
      <h2>{{ t('activityLog') }}</h2>
    </header>

    <div class="log-filters">
      <select [value]="action()" (change)="setAction($any($event.target).value)">
        <option value="">{{ t('allActions') }}</option>
        <option value="create">{{ t('actionCreate') }}</option>
        <option value="update">{{ t('actionUpdate') }}</option>
        <option value="delete">{{ t('actionDelete') }}</option>
        <option value="action">{{ t('actionAction') }}</option>
      </select>
      <select [value]="model()" (change)="setModel($any($event.target).value)">
        <option value="">{{ t('allModels') }}</option>
        @for (m of models(); track m.key) {
          <option [value]="m.key">{{ cap(m.verbose_name_plural) }}</option>
        }
      </select>
      @if (isSuper()) {
        <input
          class="search"
          type="text"
          [placeholder]="t('filterByUser')"
          [value]="userFilter()"
          (input)="setUser($any($event.target).value)"
        />
      }
    </div>

    <div class="table-wrap">
      <table class="grid">
        <thead>
          <tr>
            <th>{{ t('colTime') }}</th>
            @if (isSuper()) { <th>{{ t('colUser') }}</th> }
            <th>{{ t('colAction') }}</th>
            <th>{{ t('colModel') }}</th>
            <th>{{ t('colObject') }}</th>
            <th>{{ t('colChanges') }}</th>
          </tr>
        </thead>
        <tbody>
          @for (e of rows(); track e.id) {
            <tr>
              <td class="log-time">{{ fmtTime(e.timestamp) }}</td>
              @if (isSuper()) { <td>{{ e.username }}</td> }
              <td><span class="log-badge log-{{ e.action }}">{{ actionLabel(e.action) }}</span></td>
              <td>{{ cap(e.model_label) }}</td>
              <td>{{ e.object_repr }} <span class="log-pk">#{{ e.object_pk }}</span></td>
              <td class="log-changes">
                @for (line of changeLines(e); track line) {
                  <div>{{ line }}</div>
                }
              </td>
            </tr>
          } @empty {
            <tr><td [attr.colspan]="isSuper() ? 6 : 5">{{ t('noActivity') }}</td></tr>
          }
        </tbody>
      </table>
    </div>

    <footer class="pager">
      <button [disabled]="page() <= 1" (click)="go(page() - 1)">{{ t('prev') }}</button>
      <span>{{ t('pageInfo', { page: page(), pages: numPages(), count: count() }) }}</span>
      <button [disabled]="page() >= numPages()" (click)="go(page() + 1)">{{ t('next') }}</button>
    </footer>
  `,
})
export class LogComponent implements OnInit {
  private api = inject(ApiService);
  private i18n = inject(I18nService);
  protected t = this.i18n.t;
  cap = cap;

  rows = signal<LogEntry[]>([]);
  models = signal<RegistryModel[]>([]);
  isSuper = signal(false);
  count = signal(0);
  page = signal(1);
  numPages = signal(1);
  action = signal('');
  model = signal('');
  userFilter = signal('');
  private debounce?: ReturnType<typeof setTimeout>;

  ngOnInit(): void {
    this.api.getRegistry().subscribe((r) => this.models.set(r.models));
    this.load();
  }

  private load(): void {
    this.api
      .logs({
        page: this.page(),
        action: this.action(),
        model: this.model(),
        user: this.userFilter(),
      })
      .subscribe((resp) => {
        this.rows.set(resp.results);
        this.count.set(resp.count);
        this.page.set(resp.page);
        this.numPages.set(resp.num_pages);
        this.isSuper.set(resp.is_superuser);
      });
  }

  setAction(v: string): void {
    this.action.set(v);
    this.page.set(1);
    this.load();
  }

  setModel(v: string): void {
    this.model.set(v);
    this.page.set(1);
    this.load();
  }

  setUser(v: string): void {
    this.userFilter.set(v);
    this.page.set(1);
    clearTimeout(this.debounce);
    this.debounce = setTimeout(() => this.load(), 250);
  }

  go(page: number): void {
    this.page.set(page);
    this.load();
  }

  fmtTime(iso: string): string {
    return this.i18n.formatDate(iso, 'datetime') || iso;
  }

  /** Translated badge label for a log action code. */
  actionLabel(action: string): string {
    const key: Record<string, MessageKey> = {
      create: 'actionCreate',
      update: 'actionUpdate',
      delete: 'actionDelete',
      action: 'actionAction',
    };
    return key[action] ? this.t(key[action]) : action;
  }

  /** Human lines for the changes column. */
  changeLines(e: LogEntry): string[] {
    const c = e.changes ?? {};
    if (e.action === 'action') {
      // Prefer the authoritative `count` (covers select-all-matching, where the
      // server records no `ids`); fall back to the explicit id list for older
      // entries that predate `count`.
      const count =
        typeof c['count'] === 'number'
          ? (c['count'] as number)
          : Array.isArray(c['ids'])
            ? (c['ids'] as unknown[]).length
            : 0;
      const scope = c['all'] ? this.t('allMatchingSuffix') : '';
      return [`${c['action']} — ${this.t('objectsCount', { n: count })}${scope}`];
    }
    return Object.entries(c).map(([field, pair]) => {
      if (Array.isArray(pair) && pair.length === 2) {
        return `${field}: ${this.fmtVal(pair[0])} → ${this.fmtVal(pair[1])}`;
      }
      return `${field}: ${this.fmtVal(pair)}`;
    });
  }

  private fmtVal(v: unknown): string {
    if (v === null || v === undefined || v === '') {
      return '∅';
    }
    if (Array.isArray(v)) {
      return v.map((x) => this.fmtVal(x)).join(', ') || '∅';
    }
    if (typeof v === 'object' && 'label' in (v as object)) {
      return String((v as { label: unknown }).label);
    }
    return String(v);
  }
}
