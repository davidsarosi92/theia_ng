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
import { FormControl } from '@angular/forms';
import { Subject, debounceTime, distinctUntilChanged, switchMap } from 'rxjs';

import { ApiService } from './api.service';
import { Choice, FieldSpec, ListResponse, RelationValue } from './models';

interface Option {
  id: number | string;
  label: string;
}

const key = (id: unknown): string => String(id);

@Component({
  selector: 'theia-relation-select',
  standalone: true,
  template: `
    <div class="rel">
      <div class="rel-trigger" (click)="toggle($event)">
        @if (multi) {
          @for (s of selectedItems(); track key(s.id)) {
            <span class="chip">{{ s.label }}</span>
          }
          @if (!selectedItems().length) { <span class="placeholder">Select…</span> }
        } @else {
          @if (selectedItems()[0]; as s) {
            <span>{{ s.label }}</span>
          } @else {
            <span class="placeholder">Select…</span>
          }
        }
        <span class="caret">▾</span>
      </div>

      @if (open()) {
        <div class="rel-panel">
          <input
            class="rel-search"
            type="text"
            placeholder="Search…"
            [value]="searchTerm()"
            (click)="$event.stopPropagation()"
            (input)="onSearch($any($event.target).value)"
          />
          <ul class="rel-options" (scroll)="onScroll($event)">
            @for (o of options(); track key(o.id)) {
              <li [class.sel]="isSelected(o.id)" (click)="choose(o, $event)">
                @if (multi) { <span class="check">{{ isSelected(o.id) ? '☑' : '☐' }}</span> }
                {{ o.label }}
              </li>
            } @empty {
              @if (!loading()) { <li class="muted">No matches.</li> }
            }
            @if (loading()) { <li class="muted">Loading…</li> }
          </ul>
          <div class="rel-foot">
            {{ multi ? selectedItems().length + ' selected · ' : '' }}{{ count() }} total
          </div>
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
  private host = inject(ElementRef<HTMLElement>);

  key = key;
  multi = false;
  open = signal(false);
  searchTerm = signal('');
  options = signal<Option[]>([]);
  page = signal(1);
  numPages = signal(1);
  count = signal(0);
  loading = signal(false);
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
    const seed = (r: RelationValue) => this.labels.set(key(r.id), r.label);
    if (Array.isArray(this.initial)) {
      this.initial.forEach(seed);
    } else if (this.initial) {
      seed(this.initial);
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

  // --- options list --------------------------------------------------------

  toggle(event: Event): void {
    event.stopPropagation();
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
    this.api.options(this.endpoint, this.searchTerm(), page).subscribe((resp) =>
      this.apply(resp, replace),
    );
  }

  private apply(resp: ListResponse, replace: boolean): void {
    const display = this.field.relation!.display_field;
    const mapped: Option[] = resp.results.map((r) => {
      const label = this.displayOf(r, display);
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

  private displayOf(row: Record<string, unknown>, displayField: string): string {
    const value = row[displayField];
    if (value && typeof value === 'object' && 'label' in (value as object)) {
      return String((value as Choice).label);
    }
    return value != null ? String(value) : String(row['pk']);
  }
}
