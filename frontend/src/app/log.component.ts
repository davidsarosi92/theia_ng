import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { LogEntry, RegistryModel } from './models';
import { cap } from './util';

@Component({
  selector: 'theia-log',
  standalone: true,
  imports: [RouterLink],
  template: `
    <nav class="breadcrumb">
      <a routerLink="/">Home</a>
      <span class="sep">/</span>
      <span>Activity log</span>
    </nav>

    <header class="list-header">
      <h2>Activity log</h2>
    </header>

    <div class="log-filters">
      <select [value]="action()" (change)="setAction($any($event.target).value)">
        <option value="">All actions</option>
        <option value="create">Create</option>
        <option value="update">Update</option>
        <option value="delete">Delete</option>
        <option value="action">Action</option>
      </select>
      <select [value]="model()" (change)="setModel($any($event.target).value)">
        <option value="">All models</option>
        @for (m of models(); track m.key) {
          <option [value]="m.key">{{ cap(m.verbose_name_plural) }}</option>
        }
      </select>
      @if (isSuper()) {
        <input
          class="search"
          type="text"
          placeholder="Filter by user…"
          [value]="userFilter()"
          (input)="setUser($any($event.target).value)"
        />
      }
    </div>

    <div class="table-wrap">
      <table class="grid">
        <thead>
          <tr>
            <th>Time</th>
            @if (isSuper()) { <th>User</th> }
            <th>Action</th>
            <th>Model</th>
            <th>Object</th>
            <th>Changes</th>
          </tr>
        </thead>
        <tbody>
          @for (e of rows(); track e.id) {
            <tr>
              <td class="log-time">{{ fmtTime(e.timestamp) }}</td>
              @if (isSuper()) { <td>{{ e.username }}</td> }
              <td><span class="log-badge log-{{ e.action }}">{{ e.action }}</span></td>
              <td>{{ cap(e.model_label) }}</td>
              <td>{{ e.object_repr }} <span class="log-pk">#{{ e.object_pk }}</span></td>
              <td class="log-changes">
                @for (line of changeLines(e); track line) {
                  <div>{{ line }}</div>
                }
              </td>
            </tr>
          } @empty {
            <tr><td [attr.colspan]="isSuper() ? 6 : 5">No activity.</td></tr>
          }
        </tbody>
      </table>
    </div>

    <footer class="pager">
      <button [disabled]="page() <= 1" (click)="go(page() - 1)">‹ Prev</button>
      <span>Page {{ page() }} / {{ numPages() }} ({{ count() }} total)</span>
      <button [disabled]="page() >= numPages()" (click)="go(page() + 1)">Next ›</button>
    </footer>
  `,
})
export class LogComponent implements OnInit {
  private api = inject(ApiService);
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
    const d = new Date(iso);
    return isNaN(d.getTime()) ? iso : d.toLocaleString();
  }

  /** Human lines for the changes column. */
  changeLines(e: LogEntry): string[] {
    const c = e.changes ?? {};
    if (e.action === 'action') {
      const ids = Array.isArray(c['ids']) ? (c['ids'] as unknown[]).length : 0;
      return [`${c['action']} — ${ids} object(s)`];
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
