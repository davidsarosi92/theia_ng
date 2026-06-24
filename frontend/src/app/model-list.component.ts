import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subscription, forkJoin } from 'rxjs';

import { ActionDialogComponent } from './action-dialog.component';
import { ApiService } from './api.service';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { AppliedFilter, FilterDialogComponent } from './filter-dialog.component';
import { I18nService } from './i18n.service';
import { MessageKey } from './i18n/messages';
import { inputTypeFor } from './field-widgets';
import { ActionSpec, FieldSpec, ModelSchema } from './models';
import { ToastService } from './toast.service';
import { cap, slugToKey } from './util';

/** Built-in (theia-shipped) bulk action keys → i18n key. Lets us translate their
 *  server-provided English labels in the UI; unlisted (custom) actions fall back
 *  to their own label. */
const BUILTIN_ACTION_LABELS: Record<string, MessageKey> = {
  delete_selected: 'deleteSelected',
};
import { ViewService } from './view.service';

@Component({
  selector: 'theia-model-list',
  standalone: true,
  imports: [
    RouterLink,
    FormsModule,
    FilterDialogComponent,
    ActionDialogComponent,
    ConfirmDialogComponent,
  ],
  template: `
    @if (schema(); as s) {
      <nav class="breadcrumb">
        <a routerLink="/">{{ t('home') }}</a>
        <span class="sep">/</span>
        <span>{{ cap(s.verbose_name) }}</span>
      </nav>

      <header class="list-header">
        <h2>{{ cap(s.verbose_name) }}</h2>
        <div class="list-actions">
          @for (a of toolbarActions(); track a.key) {
            <button class="btn secondary" (click)="openAction(a)">{{ actionLabel(a) }}</button>
          }
          @if (s.list.filters.length || s.list.custom_filters?.length) {
            <button class="btn secondary" (click)="showFilter.set(true)">+ {{ t('filter') }}</button>
          }
          @if (s.perms.add) {
            <a class="btn" [routerLink]="['/', slug, 'new']">+ {{ t('add') }}</a>
          }
        </div>
      </header>

      @if (s.list.search_fields.length) {
        <input
          class="search"
          type="text"
          [placeholder]="t('search')"
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
            <option value="">{{ t('bulkActionPlaceholder') }}</option>
            @for (a of bulkActions(); track a.key) {
              <option [value]="a.key">{{ actionLabel(a) }}</option>
            }
          </select>
          <button
            class="btn secondary small"
            [disabled]="!selectionCount() || !selectedAction()"
            (click)="runBulk(selectedAction())"
          >{{ t('apply') }}</button>
          @if (selectionCount()) {
            <span class="bulk-count">{{ t('selectedCount', { n: selectionCount() }) }}</span>
          }
          @if (selectAllAcross()) {
            <span class="bulk-across">
              {{ t('allNSelected', { n: count() }) }}
              <button class="link-btn" (click)="clearSelection()">{{ t('clear') }}</button>
            </span>
          } @else if (allOnPageSelected() && count() > rows().length) {
            <span class="bulk-across">
              {{ t('allOnPageSelected', { n: rows().length }) }}
              <button class="link-btn" (click)="selectAllAcross.set(true)">{{ t('selectAllN', { n: count() }) }}</button>
            </span>
          }
        </div>
      }

      <div class="table-wrap">
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
            @if (loading()) {
              @for (i of skeletonRows; track i) {
                <tr class="skel-row">
                  <td class="skel-cell" [attr.colspan]="colSpan()"><span class="skeleton skel-line"></span></td>
                </tr>
              }
            } @else {
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
                    @if (editorKind(row, col); as kind) {
                      <span class="cell-edit" (click)="$event.stopPropagation()">
                        @switch (kind) {
                          @case ('checkbox') {
                            <input
                              type="checkbox"
                              [ngModel]="cellValue(row, col)"
                              (ngModelChange)="setEdit(row, col, $event)"
                            />
                          }
                          @case ('select') {
                            <select
                              [ngModel]="cellValue(row, col)"
                              (ngModelChange)="setEdit(row, col, $event)"
                            >
                              <option [ngValue]="null">—</option>
                              @for (c of colChoices(col); track c.value) {
                                <option [ngValue]="c.value">{{ c.label }}</option>
                              }
                            </select>
                          }
                          @default {
                            <input
                              [type]="kind"
                              [ngModel]="cellValue(row, col)"
                              (ngModelChange)="setEdit(row, col, $event)"
                            />
                          }
                        }
                      </span>
                    } @else if (isBool(col)) {
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
              <tr><td [attr.colspan]="colSpan()">{{ t('noRecords') }}</td></tr>
            }
            }
          </tbody>
        </table>
      </div>

      @if (editCount()) {
        <div class="edit-bar">
          <span>{{ t('selectedCount', { n: editCount() }) }}</span>
          <button class="btn small" [disabled]="savingEdits()" (click)="saveEdits()">{{ t('save') }}</button>
          <button class="btn small secondary" [disabled]="savingEdits()" (click)="discardEdits()">{{ t('cancel') }}</button>
        </div>
      }

      <footer class="pager">
        <button [disabled]="page() <= 1" (click)="go(page() - 1)">{{ t('prev') }}</button>
        <span>{{ t('pageInfo', { page: page(), pages: numPages(), count: count() }) }}</span>
        <button [disabled]="page() >= numPages()" (click)="go(page() + 1)">{{ t('next') }}</button>
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
          [title]="actionLabel(pb)"
          [message]="t('bulkConfirmMsg', { action: actionLabel(pb), n: selectionCount() })"
          [confirmLabel]="actionLabel(pb)"
          [cancelLabel]="t('cancel')"
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
  private i18n = inject(I18nService);
  protected t = this.i18n.t;
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
  /** Placeholder rows shown while a page loads (skeleton). */
  skeletonRows = [0, 1, 2, 3, 4, 5, 6, 7];
  /** Total column count, for full-width skeleton / empty rows. */
  colSpan = computed(() => this.columns().length + (this.selectable() ? 1 : 0));

  // --- inline list editing (list_editable) -------------------------------
  /** Pending cell edits: pk -> {field: newValue}. */
  edits = signal<Map<unknown, Record<string, unknown>>>(new Map());
  savingEdits = signal(false);
  editCount = computed(() => this.edits().size);

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
    return (this.schema()?.actions ?? []).filter((a) => a.selection === 'none' && !a.detail);
  }

  openAction(action: ActionSpec): void {
    this.activeAction.set(action);
  }

  /** Display label for an action. Theia's built-in actions (e.g. delete_selected)
   *  carry an English server label, so translate those client-side by key; custom
   *  app-defined actions keep their own label. */
  actionLabel(action: ActionSpec): string {
    const key = BUILTIN_ACTION_LABELS[action.key];
    return key ? this.t(key) : this.cap(action.label);
  }

  onActionDone(): void {
    this.activeAction.set(null);
    this.load();
  }

  /** Selection-driven actions for the bulk bar, gated on the needed permission. */
  bulkActions(): ActionSpec[] {
    const perms = this.schema()?.perms;
    return (this.schema()?.actions ?? []).filter(
      (a) => a.selection !== 'none' && !a.detail && (!a.requires || !!perms?.[a.requires]),
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
        this.toast.success(this.t('actionDoneToast', { action: this.actionLabel(action) }));
        this.clearSelection();
        this.load();
      },
      error: () => this.toast.error(this.t('actionFailed')),
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

  formatDate = this.i18n.formatDate;

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
    // Row selection + pending cell edits are per result set — drop them when the
    // rows change (page, search, filter, sort, reload).
    this.clearSelection();
    this.edits.set(new Map());
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

  // --- inline list editing -----------------------------------------------
  private editableCols(): string[] {
    return this.schema()?.list.editable ?? [];
  }

  /** The inline editor kind for a cell, or null if the column isn't editable in
   *  place. Relations/json/textareas stay read-only in the list. The return value
   *  doubles as the input `type` for the default (text-like) case. */
  editorKind(_row: Record<string, unknown>, col: string): string | null {
    if (!this.editableCols().includes(col) || !this.schema()?.perms.change) {
      return null;
    }
    const f = this.fieldByName(col);
    if (!f || !f.editable) {
      return null;
    }
    switch (f.type) {
      case 'boolean':
        return 'checkbox';
      case 'choice':
        return 'select';
      case 'fk':
      case 'm2m':
      case 'json':
      case 'text':
      case 'image':
      case 'file':
        return null;
      default:
        return inputTypeFor(f.type);
    }
  }

  colChoices(col: string) {
    return this.fieldByName(col)?.choices ?? [];
  }

  cellValue(row: Record<string, unknown>, col: string): unknown {
    const edit = this.edits().get(row['pk']);
    if (edit && col in edit) {
      return edit[col];
    }
    let v = row[col];
    if (this.fieldByName(col)?.type === 'datetime' && typeof v === 'string') {
      v = v.slice(0, 16); // ISO -> datetime-local
    }
    return v;
  }

  setEdit(row: Record<string, unknown>, col: string, value: unknown): void {
    const pk = row['pk'];
    const next = new Map(this.edits());
    next.set(pk, { ...(next.get(pk) ?? {}), [col]: value });
    this.edits.set(next);
  }

  discardEdits(): void {
    this.edits.set(new Map());
  }

  saveEdits(): void {
    const entries = [...this.edits().entries()];
    if (!entries.length) {
      return;
    }
    this.savingEdits.set(true);
    forkJoin(
      entries.map(([pk, changes]) => this.api.update(this.modelKey, String(pk), changes)),
    ).subscribe({
      next: () => {
        this.savingEdits.set(false);
        this.toast.success(this.t('saved'));
        this.edits.set(new Map());
        this.load();
      },
      error: () => {
        this.savingEdits.set(false);
        this.toast.error(this.t('couldNotSave'));
      },
    });
  }
}
