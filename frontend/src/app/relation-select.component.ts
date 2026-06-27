import {
  Component,
  DestroyRef,
  ElementRef,
  HostListener,
  Input,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup } from '@angular/forms';
import { Router } from '@angular/router';
import { Subject, debounceTime, distinctUntilChanged, map, switchMap } from 'rxjs';

import { ApiService } from './api.service';
import { ButtonLabelComponent } from './button-label.component';
import { IconComponent } from './icon.component';
import { I18nService } from './i18n.service';
import { Choice, FieldSpec, ListResponse, Perms, RelationValue } from './models';
import { keyToSlug } from './util';

interface Option {
  id: number | string;
  label: string;
}

const key = (id: unknown): string => String(id);

@Component({
  selector: 'theia-relation-select',
  standalone: true,
  imports: [ButtonLabelComponent, IconComponent],
  template: `
    <div class="rel">
      <!-- M2M: selected rows shown as a table above the picker. -->
      @if (multi && selectedItems().length) {
        <table class="rel-table">
          <tbody>
            @for (s of selectedItems(); track key(s.id)) {
              <tr>
                <td class="rel-table-label">{{ s.label }}</td>
                <td class="rel-table-actions">
                  @if (!isReadonly()) {
                    @if (targetPerms()?.change) {
                      <button type="button" class="rel-act" (click)="openEdit(s, $event)"><theia-blabel icon="edit" [text]="t('edit')" /></button>
                    } @else if (targetPerms()?.view) {
                      <button type="button" class="rel-act" (click)="openView(s, $event)"><theia-blabel icon="view" [text]="t('view')" /></button>
                    }
                    <button type="button" class="rel-act danger" (click)="askDelete(s, $event)"><theia-blabel icon="delete" [text]="t('delete')" /></button>
                  }
                </td>
              </tr>
            }
          </tbody>
        </table>
      }

      @if (isReadonly()) {
        <!-- Read-only FK: just the value (M2M shows its table above). -->
        @if (!multi) {
          <div class="rel-readonly">{{ selectedItems().length ? selectedItems()[0].label : '—' }}</div>
        }
      } @else {
        <div class="rel-row">
          <!-- The selected value lives in the (clickable) trigger, like a combobox. -->
          <div class="rel-trigger" (click)="toggle($event)">
            @if (multi) {
              <span class="placeholder">{{ t('addPlaceholder') }}</span>
            } @else if (selectedItems()[0]; as s) {
              <span>{{ s.label }}</span>
            } @else {
              <span class="placeholder">{{ t('selectPlaceholder') }}</span>
            }
            <span class="caret">▾</span>
          </div>
          <!-- FK actions sit beside the trigger (M2M actions are per table row). -->
          @if (!multi && selectedItems()[0]; as s) {
            <div class="rel-fk-actions">
              @if (targetPerms()?.change) {
                <button type="button" class="rel-act" (click)="openEdit(s, $event)"><theia-blabel icon="edit" [text]="t('edit')" /></button>
              } @else if (targetPerms()?.view) {
                <button type="button" class="rel-act" (click)="openView(s, $event)"><theia-blabel icon="view" [text]="t('view')" /></button>
              }
              <button type="button" class="rel-act danger" (click)="askDelete(s, $event)"><theia-blabel icon="delete" [text]="t('delete')" /></button>
            </div>
          }
        </div>
      }

      @if (open()) {
        <div class="rel-panel">
          <input
            class="rel-search"
            type="text"
            [placeholder]="t('search')"
            [value]="searchTerm()"
            (click)="$event.stopPropagation()"
            (input)="onSearch($any($event.target).value)"
          />
          <ul class="rel-options" (scroll)="onScroll($event)">
            @for (o of visibleOptions(); track key(o.id)) {
              <li [class.sel]="isSelected(o.id)" (click)="choose(o, $event)">
                @if (multi) { <span class="check">{{ isSelected(o.id) ? '☑' : '☐' }}</span> }
                {{ o.label }}
              </li>
            } @empty {
              @if (!loading()) { <li class="muted">{{ t('noMatches') }}</li> }
            }
            @if (loading()) { <li class="muted">{{ t('loading') }}</li> }
          </ul>
          <div class="rel-foot">
            {{ multi ? t('selectedCount', { n: selectedItems().length }) + ' · ' : '' }}{{ t('totalCount', { count: count() }) }}
          </div>
        </div>
      }

      @if (pendingDelete(); as item) {
        <div class="confirm-backdrop" (click)="cancelDelete()">
          <div class="confirm-card" (click)="$event.stopPropagation()">
            <button type="button" class="dialog-close" (click)="cancelDelete()" [attr.aria-label]="t('close')"><theia-icon name="x" /></button>
            <p>{{ t('relRemovePrompt', { label: item.label }) }}</p>
            <ul class="confirm-help section-desc">
              <li><strong>{{ t('removeLink') }}</strong> — {{ t('removeLinkHelp') }}</li>
              @if (targetPerms()?.delete) {
                <li><strong>{{ t('deleteEntity') }}</strong> — {{ t('deleteEntityHelp') }}</li>
              }
            </ul>
            <div class="confirm-actions">
              <button type="button" class="btn secondary" (click)="unlink(item)"><theia-blabel icon="removeLink" [text]="t('removeLink')" /></button>
              @if (targetPerms()?.delete) {
                <button type="button" class="btn danger push-right" (click)="deleteEntity(item)"><theia-blabel icon="deleteEntity" [text]="t('deleteEntity')" /></button>
              }
            </div>
          </div>
        </div>
      }
    </div>
  `,
})
export class RelationSelectComponent implements OnInit {
  @Input({ required: true }) field!: FieldSpec;
  @Input({ required: true }) control!: FormControl;
  /** Initial selection from the loaded record (carries labels). The record loads
   *  asynchronously (after this component is created), so seed labels via the
   *  setter on every assignment — not once in ngOnInit, which would miss it. */
  @Input() set initial(value: RelationValue | RelationValue[] | null) {
    const seed = (r: RelationValue | null) => {
      if (r) {
        this.labels.set(key(r.id), r.label);
      }
    };
    if (Array.isArray(value)) {
      value.forEach(seed);
    } else {
      seed(value);
    }
    this.rev.update((n) => n + 1);
  }
  /** Parent form, used to read sibling values for dependent options. */
  @Input() form?: FormGroup;
  /** Option ids to hide from the dropdown — values already chosen elsewhere
   *  (e.g. sibling inline rows), so the same relation can't be assigned twice.
   *  This row's own current selection is never hidden. */
  @Input() exclude: (number | string)[] = [];
  /** Forbid interaction (unregistered M2M target): show items read-only, no add. */
  @Input() locked = false;

  private api = inject(ApiService);
  private router = inject(Router);
  private destroyRef = inject(DestroyRef);
  private host = inject(ElementRef<HTMLElement>);
  private i18n = inject(I18nService);
  protected t = this.i18n.t;

  key = key;
  multi = false;
  open = signal(false);
  searchTerm = signal('');
  options = signal<Option[]>([]);
  page = signal(1);
  numPages = signal(1);
  count = signal(0);
  loading = signal(false);
  /** Current user's permissions on the relation's target model. */
  targetPerms = signal<Perms | undefined>(undefined);
  /** The row awaiting a remove-link / delete-entity / cancel choice. */
  pendingDelete = signal<Option | null>(null);
  /** Bumped when the control value / label cache changes, to drive CD. */
  private rev = signal(0);

  /** id -> label cache (seeded from `initial`, grown as options load / are picked). */
  private labels = new Map<string, string>();

  private search$ = new Subject<string>();

  /** Close when clicking outside this component (no overlay/backdrop, so option
   *  clicks always reach the option, not a covering layer). */
  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (this.open() && !this.host.nativeElement.contains(event.target as Node)) {
      this.open.set(false);
    }
  }

  ngOnInit(): void {
    this.multi = this.field.type === 'm2m';

    // Target perms drive the per-row View/Edit/Delete buttons (FK and M2M alike).
    const target = this.field.relation?.target;
    if (target && this.field.relation?.registered !== false) {
      this.api
        .permsFor(target)
        .pipe(takeUntilDestroyed(this.destroyRef))
        .subscribe((perms) => this.targetPerms.set(perms));
    }

    this.search$
      .pipe(
        debounceTime(250),
        distinctUntilChanged(),
        switchMap((term) => {
          this.loading.set(true);
          return this.api.options(this.endpoint, term, 1, this.extraParams());
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((resp) => this.apply(resp, true));

    // Reload options when a dependency (sibling field) changes.
    const deps = this.field.relation?.depends_on ?? [];
    if (deps.length && this.form) {
      this.form.valueChanges
        .pipe(
          map(() => JSON.stringify(this.extraParams())),
          distinctUntilChanged(),
          takeUntilDestroyed(this.destroyRef),
        )
        .subscribe(() => {
          this.options.set([]);
          this.page.set(1);
          if (this.open()) {
            this.loadPage(1, true);
          }
        });
    }
  }

  /** Sibling values that narrow this relation's options (depends_on). */
  private extraParams(): Record<string, string> {
    const out: Record<string, string> = {};
    for (const dep of this.field.relation?.depends_on ?? []) {
      const v = this.form?.get(dep)?.value;
      out[dep] = v === null || v === undefined ? '' : String(v);
    }
    return out;
  }

  private get endpoint(): string {
    return this.field.relation!.options_endpoint;
  }

  // --- selection state: the FormControl is the source of truth -------------

  private selectedIds(): (number | string)[] {
    this.rev(); // track
    const v = this.control.value;
    if (this.multi) {
      return Array.isArray(v) ? v : [];
    }
    return v === null || v === undefined ? [] : [v];
  }

  selectedItems(): Option[] {
    return this.selectedIds().map((id) => ({ id, label: this.labels.get(key(id)) ?? String(id) }));
  }

  isSelected(id: number | string): boolean {
    return this.selectedIds().some((v) => key(v) === key(id));
  }

  /** Options to render: the loaded options minus any ``exclude`` ids, except the
   *  current selection (which must stay visible/selected). */
  visibleOptions(): Option[] {
    if (!this.exclude.length) {
      return this.options();
    }
    const blocked = new Set(this.exclude.map((id) => key(id)));
    const mine = new Set(this.selectedIds().map((id) => key(id)));
    return this.options().filter((o) => mine.has(key(o.id)) || !blocked.has(key(o.id)));
  }

  /** No interaction: view mode (disabled control) or a locked (unregistered) field. */
  isReadonly(): boolean {
    return this.control.disabled || this.locked;
  }

  /** Toggle an option. For M2M the panel stays open so you can pick several. */
  choose(opt: Option, event: Event): void {
    event.stopPropagation();
    this.labels.set(key(opt.id), opt.label);
    if (this.multi) {
      const ids = this.selectedIds();
      const next = this.isSelected(opt.id)
        ? ids.filter((v) => key(v) !== key(opt.id))
        : [...ids, opt.id];
      this.control.setValue(next);
    } else {
      this.control.setValue(opt.id);
      this.open.set(false);
    }
    this.control.markAsDirty();
    this.rev.update((n) => n + 1);
  }

  // --- M2M row actions -----------------------------------------------------

  private get target(): string {
    return this.field.relation!.target;
  }

  /** Navigate to the related record's page (read-only); remember where to return. */
  openView(item: Option, event: Event): void {
    event.stopPropagation();
    this.navigateToTarget(item, 'view');
  }

  openEdit(item: Option, event: Event): void {
    event.stopPropagation();
    this.navigateToTarget(item, 'edit');
  }

  private navigateToTarget(item: Option, mode: 'view' | 'edit'): void {
    const queryParams: Record<string, string> = { ret: this.router.url };
    if (mode === 'view') {
      queryParams['mode'] = 'view';
    }
    this.router.navigate(['/', keyToSlug(this.target), item.id], { queryParams });
    window.scrollTo({ top: 0 });
  }

  askDelete(item: Option, event: Event): void {
    event.stopPropagation();
    this.pendingDelete.set(item);
  }

  cancelDelete(): void {
    this.pendingDelete.set(null);
  }

  /** Remove the row from this relation only; the target record is untouched. */
  unlink(item: Option): void {
    if (this.multi) {
      this.control.setValue(this.selectedIds().filter((v) => key(v) !== key(item.id)));
    } else {
      this.control.setValue(null);
    }
    this.control.markAsDirty();
    this.rev.update((n) => n + 1);
    this.pendingDelete.set(null);
  }

  /** Delete the target record, then drop it from the selection. */
  deleteEntity(item: Option): void {
    this.api.remove(this.target, key(item.id)).subscribe({
      next: () => this.unlink(item),
      error: () => {
        alert('Could not delete this record.');
        this.pendingDelete.set(null);
      },
    });
  }

  // --- options list --------------------------------------------------------

  toggle(event: Event): void {
    event.stopPropagation();
    if (this.isReadonly()) {
      return;
    }
    this.open.update((v) => !v);
    if (this.open() && this.options().length === 0) {
      this.loadPage(1, true);
    }
  }

  onSearch(term: string): void {
    this.searchTerm.set(term);
    this.search$.next(term);
  }

  onScroll(event: Event): void {
    const el = event.target as HTMLElement;
    const nearBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 24;
    if (nearBottom && !this.loading() && this.page() < this.numPages()) {
      this.loadPage(this.page() + 1, false);
    }
  }

  private loadPage(page: number, replace: boolean): void {
    this.loading.set(true);
    this.api.options(this.endpoint, this.searchTerm(), page, this.extraParams()).subscribe((resp) =>
      this.apply(resp, replace),
    );
  }

  private apply(resp: ListResponse, replace: boolean): void {
    const mapped: Option[] = resp.results.map((r) => {
      const label = this.labelOf(r);
      const id = r['pk'] as number | string;
      this.labels.set(key(id), label);
      return { id, label };
    });
    this.options.set(replace ? mapped : [...this.options(), ...mapped]);
    this.page.set(resp.page);
    this.numPages.set(resp.num_pages);
    this.count.set(resp.count);
    this.loading.set(false);
    this.rev.update((n) => n + 1);
  }

  /** Pull the configured display value out of a result/record row. */
  private labelOf(row: Record<string, unknown>): string {
    const value = row[this.field.relation!.display_field];
    if (value && typeof value === 'object' && 'label' in (value as object)) {
      return String((value as Choice).label);
    }
    return value != null ? String(value) : String(row['pk']);
  }
}
