import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { AppliedFilter, FilterDialogComponent } from './filter-dialog.component';
import { FieldSpec, ModelSchema } from './models';

@Component({
  selector: 'theia-model-list',
  standalone: true,
  imports: [RouterLink, FilterDialogComponent],
  template: `
    @if (schema(); as s) {
      <header class="list-header">
        <h2>{{ s.verbose_name }}</h2>
        <div class="list-actions">
          @if (s.list.filters.length) {
            <button class="btn secondary" (click)="showFilter.set(true)">+ Filter</button>
          }
          @if (s.perms.add) {
            <a class="btn" [routerLink]="['/', modelKey, 'new']">+ Add</a>
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
                {{ col }}<span class="sort">{{ sortIndicator(col) }}</span>
              </th>
            }
          </tr>
        </thead>
        <tbody>
          @for (row of rows(); track row['pk']) {
            <tr class="clickable" (click)="open(row['pk'])">
              @for (col of columns(); track col) {
                <td>{{ cell(row[col]) }}</td>
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
      this.modelKey = params.get('modelKey') ?? '';
      this.page.set(1);
      this.searchTerm.set('');
      this.ordering.set(null);
      this.filters.set([]);
      this.api.getSchema(this.modelKey).subscribe((s) => {
        this.schema.set(s);
        this.load();
      });
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
    this.router.navigate(['/', this.modelKey, pk]);
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
