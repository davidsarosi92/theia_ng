import { Component, Input, OnInit, inject, output, signal } from '@angular/core';

import { ApiService } from './api.service';

type Id = number | string;

/** A modal table picker for raw_id relation fields: searchable + paginated, and
 *  it only hits the backend when opened (and as you search / page). Works purely
 *  by pk: already-assigned ids come in pre-selected and are kept even if they're
 *  on another page (or wouldn't match a normal filter — e.g. a bad assignment).
 *  FK emits one pk on click; M2M toggles and emits the full pk set on Apply. */
@Component({
  selector: 'theia-relation-picker-dialog',
  standalone: true,
  template: `
    <div class="dialog-backdrop" (click)="closed.emit()"></div>
    <div class="dialog picker-dialog">
      <h3>Choose @if (multi) { <span class="picker-count">({{ selected().size }} selected)</span> }</h3>

      <input
        class="search"
        type="text"
        placeholder="Search…"
        [value]="search()"
        (input)="onSearch($any($event.target).value)"
      />

      <div class="table-wrap picker-table">
        <table class="grid">
          <tbody>
            @for (row of rows(); track row['pk']) {
              <tr
                class="clickable"
                [class.selected]="isSelected(asId(row['pk']))"
                (click)="multi ? toggle(row) : pick(row)"
              >
                @if (multi) {
                  <td class="picker-check">
                    <input
                      type="checkbox"
                      [checked]="isSelected(asId(row['pk']))"
                      (click)="$event.stopPropagation(); toggle(row)"
                    />
                  </td>
                }
                <td class="picker-pk">{{ row['pk'] }}</td>
                <td>{{ label(row) }}</td>
              </tr>
            } @empty {
              <tr><td [attr.colspan]="multi ? 3 : 2">No records.</td></tr>
            }
          </tbody>
        </table>
      </div>

      <footer class="pager">
        <button [disabled]="page() <= 1" (click)="go(page() - 1)">‹</button>
        <span>{{ page() }} / {{ numPages() }} ({{ count() }})</span>
        <button [disabled]="page() >= numPages()" (click)="go(page() + 1)">›</button>
      </footer>

      @if (multi) {
        <div class="actions">
          <button type="button" class="btn" (click)="apply()">Apply</button>
          <button type="button" (click)="closed.emit()">Cancel</button>
        </div>
      }
    </div>
  `,
})
export class RelationPickerDialogComponent implements OnInit {
  private api = inject(ApiService);

  /** The relation's options endpoint (e.g. ``data/app.model/``). */
  @Input({ required: true }) endpoint!: string;
  @Input() multi = false;
  /** Currently-assigned pks, pre-selected (kept even if off-page / unmatched). */
  @Input() selectedIds: Id[] = [];
  /** FK emits one pk; M2M emits the full pk array. */
  picked = output<Id | Id[]>();
  closed = output<void>();

  rows = signal<Record<string, unknown>[]>([]);
  count = signal(0);
  page = signal(1);
  numPages = signal(1);
  search = signal('');
  selected = signal<Set<Id>>(new Set());
  private debounce?: ReturnType<typeof setTimeout>;

  ngOnInit(): void {
    this.selected.set(new Set(this.selectedIds));
    this.load();
  }

  asId(v: unknown): Id {
    return v as Id;
  }

  label(row: Record<string, unknown>): string {
    return String(row['__str__'] ?? row['pk']);
  }

  private load(): void {
    this.api.options(this.endpoint, this.search(), this.page()).subscribe((resp) => {
      this.rows.set(resp.results);
      this.count.set(resp.count);
      this.page.set(resp.page);
      this.numPages.set(resp.num_pages);
    });
  }

  onSearch(term: string): void {
    this.search.set(term);
    this.page.set(1);
    clearTimeout(this.debounce);
    this.debounce = setTimeout(() => this.load(), 250);
  }

  go(page: number): void {
    this.page.set(page);
    this.load();
  }

  isSelected(pk: Id): boolean {
    return this.selected().has(pk);
  }

  // --- FK: pick one ---
  pick(row: Record<string, unknown>): void {
    this.picked.emit(this.asId(row['pk']));
    this.closed.emit();
  }

  // --- M2M: toggle, then apply the whole set ---
  toggle(row: Record<string, unknown>): void {
    const pk = this.asId(row['pk']);
    const next = new Set(this.selected());
    next.has(pk) ? next.delete(pk) : next.add(pk);
    this.selected.set(next);
  }

  apply(): void {
    this.picked.emit([...this.selected()]);
    this.closed.emit();
  }
}
