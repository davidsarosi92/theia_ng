import { Component, Input, OnInit, WritableSignal, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { ButtonLabelComponent } from './button-label.component';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { I18nService } from './i18n.service';
import { ChildGroup, TreeNode } from './models';
import { ToastService } from './toast.service';
import { cap, keyToSlug } from './util';

/** Lazy-load state for one child group (one row of mini-table). Held in a
 *  signal (the app is zoneless) so async loads re-render; replaced immutably. */
interface GroupState {
  open: boolean;
  loading: boolean;
  rows: TreeNode[];
  page: number;
  numPages: number;
  count: number;
  search: string;
}

/** Renders one tree node and its child groups, each an expandable, searchable,
 *  paginated mini-table that loads on demand. Recurses for drilled-down rows. */
@Component({
  selector: 'theia-tree-node',
  standalone: true,
  imports: [RouterLink, ConfirmDialogComponent, ButtonLabelComponent],
  template: `
    <div class="tree-row" [class.tree-current]="isCurrent()" [style.paddingLeft.rem]="depth * 1.3">
      <span class="tree-type">{{ cap(node.model_label) }}</span>
      <span class="tree-name">{{ node.label }}</span>
      <span class="tree-acts">
        @if (node.perms.change) {
          <a class="btn small" [routerLink]="link()" [queryParams]="{ ret: ret }"><theia-blabel icon="edit" [text]="t('edit')" /></a>
        } @else if (node.perms.view) {
          <a class="btn small secondary" [routerLink]="link()" [queryParams]="{ mode: 'view', ret: ret }"><theia-blabel icon="view" [text]="t('view')" /></a>
        }
        @if (node.perms.delete) {
          <button type="button" class="btn small danger" (click)="remove()"><theia-blabel icon="delete" [text]="t('delete')" /></button>
        }
      </span>
    </div>

    @if (confirming()) {
      <theia-confirm-dialog
        [title]="t('deleteRecordTitle')"
        [message]="t('deleteRecordMsg')"
        [confirmLabel]="t('delete')"
        [danger]="true"
        (confirmed)="doRemove()"
        (cancelled)="confirming.set(false)"
      />
    }

    @for (g of node.child_groups; track g.accessor) {
      <div class="tree-group" [style.paddingLeft.rem]="(depth + 1) * 1.3">
        <button type="button" class="tree-toggle" (click)="toggle(g)">
          <span class="tree-caret">{{ state(g).open ? '▾' : '▸' }}</span>
          {{ cap(g.label) }} <span class="tree-count">({{ g.count }})</span>
        </button>

        @if (state(g).open) {
          <div class="tree-sub" [style.paddingLeft.rem]="0.6">
            @if (g.searchable) {
              <input
                class="tree-search"
                type="text"
                [placeholder]="t('search')"
                [value]="state(g).search"
                (input)="onSearch(g, $any($event.target).value)"
              />
            }
            @if (state(g).loading) {
              <div class="tree-muted">{{ t('loading') }}</div>
            } @else {
              @for (child of state(g).rows; track child.key + ':' + child.pk) {
                <theia-tree-node
                  [node]="child"
                  [depth]="depth + 2"
                  [pathKeys]="pathKeys"
                  [currentKey]="currentKey"
                  [ret]="ret"
                  [onChanged]="onChanged"
                />
              } @empty {
                <div class="tree-muted">{{ t('noRecords') }}</div>
              }
              @if (state(g).numPages > 1) {
                <div class="tree-pager">
                  <button [disabled]="state(g).page <= 1" (click)="goto(g, state(g).page - 1)">‹</button>
                  <span>{{ state(g).page }} / {{ state(g).numPages }}</span>
                  <button [disabled]="state(g).page >= state(g).numPages" (click)="goto(g, state(g).page + 1)">›</button>
                </div>
              }
            }
          </div>
        }
      </div>
    }
  `,
})
export class TreeNodeComponent implements OnInit {
  private api = inject(ApiService);
  private toast = inject(ToastService);
  private i18n = inject(I18nService);
  protected t = this.i18n.t;

  @Input({ required: true }) node!: TreeNode;
  @Input() depth = 0;
  /** Lineage keys (root→current) as `app.model:pk`, for auto-expanding the path. */
  @Input() pathKeys: string[] = [];
  @Input() currentKey = '';
  /** Return URL passed to detail pages so their Back returns to the tree. */
  @Input() ret = '';
  /** Called after a delete so the whole tree reloads (counts refresh). */
  @Input() onChanged: () => void = () => {};

  cap = cap;
  confirming = signal(false);
  private groups = new Map<string, WritableSignal<GroupState>>();
  private debounce = new Map<string, ReturnType<typeof setTimeout>>();

  ngOnInit(): void {
    // Auto-expand the child group that continues the lineage toward the current
    // record, jumping to the page that holds the next node.
    const idx = this.pathKeys.indexOf(this.nodeKey());
    if (idx >= 0 && idx < this.pathKeys.length - 1) {
      const [nextKey, nextPk] = this.pathKeys[idx + 1].split('::');
      const group = this.node.child_groups.find((g) => g.key === nextKey);
      if (group) {
        this.load(group, 1, nextPk);
      }
    }
  }

  nodeKey(): string {
    return `${this.node.key}::${this.node.pk}`;
  }

  isCurrent(): boolean {
    return this.node.is_current || this.nodeKey() === this.currentKey;
  }

  link(): unknown[] {
    return ['/', keyToSlug(this.node.key), this.node.pk];
  }

  /** Current state value for a group (reactive: reads the backing signal). */
  state(g: ChildGroup): GroupState {
    return this.sig(g)();
  }

  private sig(g: ChildGroup): WritableSignal<GroupState> {
    let s = this.groups.get(g.accessor);
    if (!s) {
      s = signal<GroupState>({
        open: false, loading: false, rows: [], page: 1, numPages: 1, count: g.count, search: '',
      });
      this.groups.set(g.accessor, s);
    }
    return s;
  }

  private patch(g: ChildGroup, changes: Partial<GroupState>): void {
    const s = this.sig(g);
    s.set({ ...s(), ...changes });
  }

  toggle(g: ChildGroup): void {
    const s = this.state(g);
    if (s.open) {
      this.patch(g, { open: false });
    } else if (s.rows.length) {
      this.patch(g, { open: true }); // already loaded once — just reveal
    } else {
      this.load(g, 1);
    }
  }

  onSearch(g: ChildGroup, term: string): void {
    this.patch(g, { search: term });
    clearTimeout(this.debounce.get(g.accessor));
    this.debounce.set(g.accessor, setTimeout(() => this.load(g, 1), 250));
  }

  goto(g: ChildGroup, page: number): void {
    this.load(g, page);
  }

  private load(g: ChildGroup, page: number, focus?: string): void {
    this.patch(g, { open: true, loading: true });
    const search = this.state(g).search;
    this.api
      .treeChildren(this.node.key, this.node.pk, g.accessor, { page, search, focus })
      .subscribe((resp) => {
        this.patch(g, {
          rows: resp.results,
          page: resp.page,
          numPages: resp.num_pages,
          count: resp.count,
          loading: false,
        });
      });
  }

  remove(): void {
    this.confirming.set(true);
  }

  doRemove(): void {
    this.confirming.set(false);
    this.api.remove(this.node.key, String(this.node.pk)).subscribe({
      next: () => {
        this.toast.success('Deleted.');
        this.onChanged();
      },
      error: () => this.toast.error('Could not delete.'),
    });
  }
}
