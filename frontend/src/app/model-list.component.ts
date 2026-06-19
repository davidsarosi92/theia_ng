import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';

import { ActionDialogComponent } from './action-dialog.component';
import { ApiService } from './api.service';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { AppliedFilter, FilterDialogComponent } from './filter-dialog.component';
import { ActionSpec, FieldSpec, ModelSchema } from './models';
import { ToastService } from './toast.service';
import { cap, formatDateValue, slugToKey } from './util';
import { ViewService } from './view.service';

@Component({
  selector: 'theia-model-list',
  standalone: true,
  imports: [RouterLink, FilterDialogComponent, ActionDialogComponent, ConfirmDialogComponent],
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
          @for (a of toolbarActions(); track a.key) {
            <button class="btn secondary" (click)="openAction(a)">{{ cap(a.label) }}</button>
          }
          @if (s.list.filters.length || s.list.custom_filters?.length) {
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

      @if (selectable() && bulkActions().length) {
        <div class="bulk-bar">
          <select
            class="bulk-select"
            [value]="selectedAction()"
            (change)="selectedAction.set($any($event.target).value)"
          >
            <option value="">— Bulk action —</option>
            @for (a of bulkActions(); track a.key) {
              <option [value]="a.key">{{ cap(a.label) }}</option>
            }
          </select>
          <button
            class="btn secondary small"
            [disabled]="!selectionCount() || !selectedAction()"
            (click)="runBulk(selectedAction())"
          >Apply</button>
          @if (selectionCount()) {
            <span class="bulk-count">{{ selectionCount() }} selected</span>
          }
          @if (selectAllAcross()) {
            <span class="bulk-across">
              All {{ count() }} selected. <button class="link-btn" (click)="clearSelection()">Clear</button>
            </span>
          } @else if (allOnPageSelected() && count() > rows().length) {
            <span class="bulk-across">
              All {{ rows().length }} on this page selected.
              <button class="link-btn" (click)="selectAllAcross.set(true)">Select all {{ count() }}</button>
            </span>
          }
        </div>
      }

      <div class="table-wrap" [class.is-loading]="loading()">
        @if (loading()) {
          <div class="loading-overlay">
            <span class="loading-pill"><span class="spinner"></span>Loading…</span>
          </div>
        }
        <table class="grid">
          <thead>
            <tr>
              @if (selectable()) {
                <th class="sel-col">
                  <input
                    type="checkbox"
                    [checked]="allOnPageSelected()"
                    [indeterminate]="someOnPageSelected()"
                    (change)="toggleAllOnPage($any($event.target).checked)"
                  />
                </th>
              }
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
              <tr class="clickable" [class.selected]="isSelected(row['pk'])" (click)="open(row['pk'])">
                @if (selectable()) {
                  <td class="sel-col" (click)="$event.stopPropagation()">
                    <input
                      type="checkbox"
                      [checked]="isSelected(row['pk'])"
                      (change)="toggleRow(row['pk'], $any($event.target).checked)"
                    />
                  </td>
                }
                @for (col of columns(); track col) {
                  <td>
                    @if (isBool(col)) {
                      @if (row[col] === true) {
                        <span class="bool bool-true">✓</span>
                      } @else if (row[col] === false) {
                        <span class="bool bool-false">✕</span>
                      }
                    } @else if (dateType(col); as dt) {
                      {{ formatDate(row[col], dt) }}
                    } @else {
                      {{ cell(row[col]) }}
                    }
                  </td>
                }
              </tr>
            } @empty {
              @if (!loading()) {
                <tr><td [attr.colspan]="columns().length + (selectable() ? 1 : 0)">No records.</td></tr>
              }
            }
          </tbody>
        </table>
      </div>

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

      @if (activeAction(); as a) {
        <theia-action-dialog
          [action]="a"
          (done)="onActionDone()"
          (closed)="activeAction.set(null)"
        />
      }

      @if (pendingBulk(); as pb) {
        <theia-confirm-dialog
          [title]="cap(pb.label)"
          [message]="'Run ' + pb.label.toLowerCase() + ' on ' + selectionCount() + ' record(s)? This cannot be undone.'"
          [confirmLabel]="cap(pb.label)"
          [danger]="true"
          (confirmed)="confirmBulk()"
          (cancelled)="pendingBulk.set(null)"
        />
      }
    }
  `,
})
export class ModelListComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private viewService = inject(ViewService);
  private toast = inject(ToastService);
  // In-flight requests, cancelled on navigation / re-load so a late response
  // from a previous model or page can't overwrite the current view.
  private schemaSub?: Subscription;
  private listSub?: Subscription;

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
  activeAction = signal<ActionSpec | null>(null);
  loading = signal(false);

  // --- row selection / bulk actions --------------------------------------
  selectable = computed(() => !!this.schema()?.list.selectable);
  /** Selected pks on the current page. */
  selected = signal<Set<unknown>>(new Set());
  /** "Select all matching" across every page (operates on the filtered queryset). */
  selectAllAcross = signal(false);
  /** A dangerous bulk action awaiting confirmation. */
  pendingBulk = signal<ActionSpec | null>(null);
  /** The bulk action chosen in the dropdown (a signal so the zoneless app
   *  re-evaluates the Apply button when the selection changes). */
  selectedAction = signal('');

  /** Selection-less actions ('none') run from the toolbar; selection-driven ones
   *  ('required'/'optional') run from the bulk bar. */
  toolbarActions(): ActionSpec[] {
    return (this.schema()?.actions ?? []).filter((a) => a.selection === 'none');
  }

  openAction(action: ActionSpec): void {
    this.activeAction.set(action);
  }

  onActionDone(): void {
    this.activeAction.set(null);
    this.load();
  }

  /** Selection-driven actions for the bulk bar, gated on the needed permission. */
  bulkActions(): ActionSpec[] {
    const perms = this.schema()?.perms;
    return (this.schema()?.actions ?? []).filter(
      (a) => a.selection !== 'none' && (!a.requires || !!perms?.[a.requires]),
    );
  }

  selectionCount(): number {
    return this.selectAllAcross() ? this.count() : this.selected().size;
  }

  isSelected(pk: unknown): boolean {
    return this.selected().has(pk);
  }

  allOnPageSelected(): boolean {
    const r = this.rows();
    return r.length > 0 && r.every((row) => this.selected().has(row['pk']));
  }

  someOnPageSelected(): boolean {
    return this.selected().size > 0 && !this.allOnPageSelected();
  }

  toggleRow(pk: unknown, checked: boolean): void {
    const next = new Set(this.selected());
    checked ? next.add(pk) : next.delete(pk);
    this.selected.set(next);
    this.selectAllAcross.set(false);
  }

  toggleAllOnPage(checked: boolean): void {
    const next = new Set(this.selected());
    for (const row of this.rows()) {
      checked ? next.add(row['pk']) : next.delete(row['pk']);
    }
    this.selected.set(next);
    this.selectAllAcross.set(false);
  }

  clearSelection(): void {
    this.selected.set(new Set());
    this.selectAllAcross.set(false);
  }

  runBulk(key: string): void {
    const action = this.bulkActions().find((a) => a.key === key);
    if (!action || !this.selectionCount()) {
      return;
    }
    if (action.dangerous) {
      this.pendingBulk.set(action);
      return;
    }
    this.execBulk(action);
  }

  confirmBulk(): void {
    const action = this.pendingBulk();
    this.pendingBulk.set(null);
    if (action) {
      this.execBulk(action);
    }
  }

  /** Filter/search params identifying the listed rows, for "select all matching". */
  private filterParams(): Record<string, string | number> {
    const params: Record<string, string | number> = {};
    if (this.searchTerm()) {
      params['search'] = this.searchTerm();
    }
    for (const f of this.filters()) {
      params[f.field] = f.value as string | number;
    }
    return params;
  }

  private execBulk(action: ActionSpec): void {
    const body = this.selectAllAcross()
      ? { all: true, filters: this.filterParams() }
      : { ids: [...this.selected()] as (number | string)[] };
    this.api.runAction(action.endpoint, body).subscribe({
      next: () => {
        this.toast.success(cap(action.label) + ' — done.');
        this.clearSelection();
        this.load();
      },
      error: () => this.toast.error('Action failed.'),
    });
  }

  ngOnInit(): void {
    this.route.paramMap.subscribe((params) => {
      this.slug = params.get('modelKey') ?? '';
      this.modelKey = slugToKey(this.slug);
      this.restoreFromUrl();
      // Drop any pending request from the previous model so its late response
      // can't land on (and overwrite) the new page.
      this.schemaSub?.unsubscribe();
      this.listSub?.unsubscribe();
      this.schemaSub = this.api.getSchema(this.modelKey).subscribe((s) => {
        this.schema.set(s);
        this.load();
      });
    });
  }

  ngOnDestroy(): void {
    this.schemaSub?.unsubscribe();
    this.listSub?.unsubscribe();
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
    // The active view, if any, defines the visible columns; else list_display.
    const viewFields = this.viewService.fieldsFor(this.modelKey);
    if (viewFields) {
      return viewFields;
    }
    const display = this.schema()?.list.display ?? [];
    return display.length ? display : ['pk'];
  }

  private fieldByName(col: string): FieldSpec | undefined {
    return this.schema()?.fields.find((f) => f.name === col);
  }

  isSortable(col: string): boolean {
    if (col === 'pk') return true; // the primary key is always sortable (order_by pk)
    const f = this.fieldByName(col);
    return !!f && f.type !== 'fk' && f.type !== 'm2m';
  }

  isBool(col: string): boolean {
    return this.fieldByName(col)?.type === 'boolean';
  }

  /** The date/datetime/time type of a column, if it is one (else null). */
  dateType(col: string): 'date' | 'datetime' | 'time' | null {
    const t = this.fieldByName(col)?.type;
    return t === 'date' || t === 'datetime' || t === 'time' ? t : null;
  }

  formatDate = formatDateValue;

  colLabel(col: string): string {
    return this.schema()?.list.labels?.[col] ?? this.fieldByName(col)?.label ?? col;
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
    // Row selection is per result set — drop it when the rows change (page,
    // search, filter, sort, reload).
    this.clearSelection();
    // Tell the server which columns are shown so it serializes only those (a much
    // narrower query) instead of every field. Re-fetched when columns/view change.
    const params: Record<string, string | number> = {
      page: this.page(),
      columns: this.columns().join(','),
    };
    if (this.searchTerm()) {
      params['search'] = this.searchTerm();
    }
    if (this.ordering()) {
      params['ordering'] = this.ordering()!;
    }
    for (const f of this.filters()) {
      params[f.field] = f.value as string | number;
    }
    this.loading.set(true);
    this.listSub?.unsubscribe(); // supersede any in-flight list request
    this.listSub = this.api.list(this.modelKey, params).subscribe({
      next: (resp) => {
        this.rows.set(resp.results);
        this.count.set(resp.count);
        this.numPages.set(resp.num_pages);
        this.page.set(resp.page);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
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
