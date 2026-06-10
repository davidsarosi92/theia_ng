import { Component, DestroyRef, Input, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl } from '@angular/forms';
import { Subject, debounceTime, distinctUntilChanged, switchMap } from 'rxjs';

import { ApiService } from './api.service';
import { Choice, FieldSpec, ListResponse, RelationValue } from './models';

interface Option {
  id: number | string;
  label: string;
}

@Component({
  selector: 'theia-relation-select',
  standalone: true,
  template: `
    <div class="rel">
      <div class="rel-trigger" (click)="toggle()">
        @if (multi) {
          @for (s of selected(); track s.id) {
            <span class="chip">
              {{ s.label }}
              <button type="button" (click)="removeChip(s.id, $event)">×</button>
            </span>
          }
          @if (!selected().length) { <span class="placeholder">Select…</span> }
        } @else {
          @if (selected()[0]; as s) {
            <span>{{ s.label }}</span>
          } @else {
            <span class="placeholder">Select…</span>
          }
        }
        <span class="caret">▾</span>
      </div>

      @if (open()) {
        <div class="rel-backdrop" (click)="close()"></div>
        <div class="rel-panel">
          <input
            class="rel-search"
            type="text"
            placeholder="Search…"
            [value]="searchTerm()"
            (input)="onSearch($any($event.target).value)"
          />
          <ul class="rel-options" (scroll)="onScroll($event)">
            @for (o of options(); track o.id) {
              <li [class.sel]="isSelected(o.id)" (click)="choose(o)">{{ o.label }}</li>
            } @empty {
              @if (!loading()) { <li class="muted">No matches.</li> }
            }
            @if (loading()) { <li class="muted">Loading…</li> }
          </ul>
          <div class="rel-foot">{{ options().length }} of {{ count() }}</div>
        </div>
      }
    </div>
  `,
})
export class RelationSelectComponent implements OnInit {
  @Input({ required: true }) field!: FieldSpec;
  @Input({ required: true }) control!: FormControl;
  /** Initial selection from the loaded record (carries labels). */
  @Input() initial: RelationValue | RelationValue[] | null = null;

  private api = inject(ApiService);
  private destroyRef = inject(DestroyRef);

  multi = false;
  open = signal(false);
  searchTerm = signal('');
  options = signal<Option[]>([]);
  selected = signal<Option[]>([]);
  page = signal(1);
  numPages = signal(1);
  count = signal(0);
  loading = signal(false);

  private search$ = new Subject<string>();

  ngOnInit(): void {
    this.multi = this.field.type === 'm2m';
    if (Array.isArray(this.initial)) {
      this.selected.set(this.initial.map((r) => ({ id: r.id, label: r.label })));
    } else if (this.initial) {
      this.selected.set([{ id: this.initial.id, label: this.initial.label }]);
    }

    this.search$
      .pipe(
        debounceTime(250),
        distinctUntilChanged(),
        switchMap((term) => {
          this.loading.set(true);
          return this.api.options(this.endpoint, term, 1);
        }),
        takeUntilDestroyed(this.destroyRef),
      )
      .subscribe((resp) => this.apply(resp, true));
  }

  private get endpoint(): string {
    return this.field.relation!.options_endpoint;
  }

  toggle(): void {
    this.open.update((v) => !v);
    if (this.open() && this.options().length === 0) {
      this.loadPage(1, true);
    }
  }

  close(): void {
    this.open.set(false);
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
    this.api.options(this.endpoint, this.searchTerm(), page).subscribe((resp) =>
      this.apply(resp, replace),
    );
  }

  private apply(resp: ListResponse, replace: boolean): void {
    const display = this.field.relation!.display_field;
    const mapped: Option[] = resp.results.map((r) => ({
      id: r['pk'] as number | string,
      label: this.displayOf(r, display),
    }));
    this.options.set(replace ? mapped : [...this.options(), ...mapped]);
    this.page.set(resp.page);
    this.numPages.set(resp.num_pages);
    this.count.set(resp.count);
    this.loading.set(false);
  }

  isSelected(id: number | string): boolean {
    return this.selected().some((s) => s.id === id);
  }

  choose(opt: Option): void {
    if (this.multi) {
      const next = this.isSelected(opt.id)
        ? this.selected().filter((s) => s.id !== opt.id)
        : [...this.selected(), opt];
      this.selected.set(next);
      this.control.setValue(next.map((s) => s.id));
      this.control.markAsDirty();
    } else {
      this.selected.set([opt]);
      this.control.setValue(opt.id);
      this.control.markAsDirty();
      this.close();
    }
  }

  removeChip(id: number | string, event: Event): void {
    event.stopPropagation();
    const next = this.selected().filter((s) => s.id !== id);
    this.selected.set(next);
    this.control.setValue(next.map((s) => s.id));
    this.control.markAsDirty();
  }

  private displayOf(row: Record<string, unknown>, displayField: string): string {
    const value = row[displayField];
    if (value && typeof value === 'object' && 'label' in (value as object)) {
      return String((value as Choice).label);
    }
    return value != null ? String(value) : String(row['pk']);
  }
}
