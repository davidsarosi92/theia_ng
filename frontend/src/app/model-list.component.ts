import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { AppliedFilter, FilterDialogComponent } from './filter-dialog.component';
import { FieldSpec, ModelSchema } from './models';
import { cap, slugToKey } from './util';

@Component({
  selector: 'theia-model-list',
  standalone: true,
  imports: [RouterLink, FilterDialogComponent],
  template: `
    @if (schema(); as s) {
      <nav class="breadcrumb">
        <a routerLink="/">Home</a>
        <span class="sep">/</span>
        <span>{{ cap(s.verbose_name) }}</span>
      </nav>

      <header class="list-header">
        <h2>{{ cap(s.verbose_name) }}</h2>
        <div class="list-actions">
          @if (s.list.filters.length) {
            <button class="btn secondary" (click)="showFilter.set(true)">+ Filter</button>
          }
          @if (s.perms.add) {
            <a class="btn" [routerLink]="['/', slug, 'new']">+ Add</a>
          }
        </div>
      </header>

      @if (s.list.search_fields.length) {
        <input
          class="search"
          type="text"
          placeholder="Search…"
          [value]="searchTerm()"
          (input)="onSearch($any($event.target).value)"
        />
      }

      @if (filters().length) {
        <table class="filters-table">
          <tbody>
            @for (f of filters(); track f.field) {
              <tr>
                <td class="f-key">{{ f.label }}</td>
                <td>{{ f.display }}</td>
                <td class="f-remove"><button (click)="removeFilter(f.field)">×</button></td>
              </tr>
            }
          </tbody>
        </table>
      }

      <table class="grid">
        <thead>
          <tr>
            @for (col of columns(); track col) {
              <th
                [class.sortable]="isSortable(col)"
                (click)="onSort(col)"
              >
                {{ colLabel(col) }}<span class="sort">{{ sortIndicator(col) }}</span>
              </th>
            }
          </tr>
        </thead>
        <tbody>
          @for (row of rows(); track row['pk']) {
            <tr class="clickable" (click)="open(row['pk'])">
              @for (col of columns(); track col) {
                <td>
                  @if (isBool(col)) {
                    @if (row[col] === true) {
                      <span class="bool bool-true">✓</span>
                    } @else if (row[col] === false) {
                      <span class="bool bool-false">✕</span>
                    }
                  } @else {
                    {{ cell(row[col]) }}
                  }
                </td>
              }
            </tr>
          } @empty {
            <tr><td [attr.colspan]="columns().length">No records.</td></tr>
          }
        </tbody>
      </table>

      <footer class="pager">
        <button [disabled]="page() <= 1" (click)="go(page() - 1)">‹ Prev</button>
        <span>Page {{ page() }} / {{ numPages() }} ({{ count() }} total)</span>
        <button [disabled]="page() >= numPages()" (click)="go(page() + 1)">Next ›</button>
      </footer>

      @if (showFilter()) {
        <theia-filter-dialog
          [schema]="s"
          (applied)="addFilter($event)"
          (closed)="showFilter.set(false)"
        />
      }
    }
  `,
})
export class ModelListComponent implements OnInit {
  private api = inject(ApiService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  modelKey = '';
  /** URL slug form of modelKey (`goods-stock`), for routerLinks. */
  slug = '';
  cap = cap;
  schema = signal<ModelSchema | null>(null);
  rows = signal<Record<string, unknown>[]>([]);
  count = signal(0);
  page = signal(1);
  numPages = signal(1);
  searchTerm = signal('');
  ordering = signal<string | null>(null);
  filters = signal<AppliedFilter[]>([]);
  showFilter = signal(false);

  ngOnInit(): void {
    this.route.paramMap.subscribe((params) => {
      this.slug = params.get('modelKey') ?? '';
      this.modelKey = slugToKey(this.slug);
      this.restoreFromUrl();
      this.api.getSchema(this.modelKey).subscribe((s) => {
        this.schema.set(s);
        this.load();
      });
    });
  }

  /** Restore list view state (search/sort/page/filters) from the URL query, so
   *  returning from a detail page shows the same filtered view. */
  private restoreFromUrl(): void {
    const q = this.route.snapshot.queryParamMap;
    this.searchTerm.set(q.get('q') ?? '');
    this.ordering.set(q.get('o'));
    this.page.set(Number(q.get('p')) || 1);
    const raw = q.get('filters');
    this.filters.set(raw ? (JSON.parse(raw) as AppliedFilter[]) : []);
  }

  /** Mirror the current state into the URL (replaceUrl: no extra history entry). */
  private syncUrl(): void {
    const queryParams: Record<string, string | null> = {
      q: this.searchTerm() || null,
      o: this.ordering() || null,
      p: this.page() > 1 ? String(this.page()) : null,
      filters: this.filters().length ? JSON.stringify(this.filters()) : null,
    };
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams,
      replaceUrl: true,
    });
  }

  columns(): string[] {
    const display = this.schema()?.list.display ?? [];
    return display.length ? display : ['pk'];
  }

  private fieldByName(col: string): FieldSpec | undefined {
    return this.schema()?.fields.find((f) => f.name === col);
  }

  isSortable(col: string): boolean {
    const f = this.fieldByName(col);
    return !!f && f.type !== 'fk' && f.type !== 'm2m';
  }

  isBool(col: string): boolean {
    return this.fieldByName(col)?.type === 'boolean';
  }

  colLabel(col: string): string {
    return this.schema()?.list.labels?.[col] ?? col;
  }

  sortIndicator(col: string): string {
    const o = this.ordering();
    if (o === col) return ' ▲';
    if (o === '-' + col) return ' ▼';
    return '';
  }

  onSort(col: string): void {
    if (!this.isSortable(col)) {
      return;
    }
    const o = this.ordering();
    this.ordering.set(o === col ? '-' + col : o === '-' + col ? null : col);
    this.page.set(1);
    this.load();
  }

  private load(): void {
    this.syncUrl();
    const params: Record<string, string | number> = { page: this.page() };
    if (this.searchTerm()) {
      params['search'] = this.searchTerm();
    }
    if (this.ordering()) {
      params['ordering'] = this.ordering()!;
    }
    for (const f of this.filters()) {
      params[f.field] = f.value as string | number;
    }
    this.api.list(this.modelKey, params).subscribe((resp) => {
      this.rows.set(resp.results);
      this.count.set(resp.count);
      this.numPages.set(resp.num_pages);
      this.page.set(resp.page);
    });
  }

  onSearch(term: string): void {
    this.searchTerm.set(term);
    this.page.set(1);
    this.load();
  }

  addFilter(filter: AppliedFilter): void {
    const others = this.filters().filter((f) => f.field !== filter.field);
    this.filters.set([...others, filter]);
    this.page.set(1);
    this.load();
  }

  removeFilter(field: string): void {
    this.filters.set(this.filters().filter((f) => f.field !== field));
    this.page.set(1);
    this.load();
  }

  go(page: number): void {
    this.page.set(page);
    this.load();
  }

  open(pk: unknown): void {
    // Carry the current (filtered) list URL so the detail's Back returns here.
    this.router.navigate(['/', this.slug, pk], { queryParams: { ret: this.router.url } });
  }

  cell(value: unknown): string {
    if (value == null) {
      return '';
    }
    if (Array.isArray(value)) {
      return value.map((v) => this.cell(v)).join(', ');
    }
    if (typeof value === 'object' && 'label' in (value as object)) {
      return String((value as { label: unknown }).label);
    }
    return String(value);
  }
}
