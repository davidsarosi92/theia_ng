import { Component, Input, OnInit, inject, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { I18nService } from './i18n.service';
import { FullTreeNode } from './models';
import { cap, keyToSlug } from './util';

/** One flattened line of the compact tree: a record row, or a relation-group
 *  sub-heading that labels the rows beneath it. */
interface Row {
  kind: 'node' | 'group';
  depth: number;
  label: string;
  modelLabel?: string;
  key?: string;
  pk?: number | string;
  perms?: { view: boolean; change: boolean; delete: boolean };
  isCurrent?: boolean;
}

/** Compact hierarchy for one record: fetches the whole subtree in a single
 *  request (no lazy per-node loading) and renders it as a flat, indented table.
 *  Each record offers a single permission-based action (Edit if you can change,
 *  else View); there is no delete here. */
@Component({
  selector: 'theia-compact-tree',
  standalone: true,
  imports: [RouterLink],
  template: `
    @if (loading()) {
      <div class="tree-muted">{{ t('loading') }}</div>
    } @else if (root()) {
      <div class="tree-grid compact-tree">
        @for (row of rows(); track $index) {
          @if (row.kind === 'group') {
            <div class="tree-group" [style.paddingLeft.rem]="row.depth * 1.2">
              {{ cap(row.label) }}
            </div>
          } @else {
            <div class="tree-row" [class.tree-current]="row.isCurrent" [style.paddingLeft.rem]="row.depth * 1.2">
              <span class="tree-type">{{ cap(row.modelLabel!) }}</span>
              <span class="tree-name">{{ row.label }}</span>
              <span class="tree-acts">
                @if (row.isCurrent) {
                  <span class="tree-here">{{ t('thisRecord') }}</span>
                } @else if (row.perms!.change) {
                  <a class="btn small" [routerLink]="['/', slug(row.key!), row.pk]" [queryParams]="{ ret: here() }">{{ t('edit') }}</a>
                } @else if (row.perms!.view) {
                  <a class="btn small secondary" [routerLink]="['/', slug(row.key!), row.pk]" [queryParams]="{ mode: 'view', ret: here() }">{{ t('view') }}</a>
                }
              </span>
            </div>
          }
        }
        @if (!rootHasChildren()) { <div class="tree-muted">{{ t('noDescendants') }}</div> }
        @if (truncated()) { <div class="tree-muted">{{ t('treeTruncated') }}</div> }
      </div>
    }
  `,
})
export class CompactTreeComponent implements OnInit {
  @Input({ required: true }) modelKey!: string;
  @Input({ required: true }) pk!: string;
  /** 'full' climbs to the topmost ancestor (page section); 'self' shows only
   *  this record's descendants (the placeable @compact_tree field). */
  @Input() scope: 'full' | 'self' = 'full';

  private api = inject(ApiService);
  private router = inject(Router);
  private i18n = inject(I18nService);
  protected t = this.i18n.t;
  cap = cap;
  slug = keyToSlug;

  loading = signal(true);
  root = signal<FullTreeNode | null>(null);
  truncated = signal(false);
  rows = signal<Row[]>([]);

  /** Current URL, passed as `ret` so a record's Back returns here. */
  here(): string {
    return this.router.url;
  }

  rootHasChildren(): boolean {
    return (this.root()?.children?.length ?? 0) > 0;
  }

  ngOnInit(): void {
    this.api.treeFull(this.modelKey, this.pk, this.scope).subscribe({
      next: (resp) => {
        this.root.set(resp.root);
        this.truncated.set(resp.truncated);
        const rows: Row[] = [];
        this.flatten(resp.root, 0, rows);
        this.rows.set(rows);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  /** Depth-first flatten: a node row, then for each relation group a sub-heading
   *  followed by that group's nodes (recursively), all one level deeper. */
  private flatten(node: FullTreeNode, depth: number, out: Row[]): void {
    out.push({
      kind: 'node',
      depth,
      label: node.label,
      modelLabel: node.model_label,
      key: node.key,
      pk: node.pk,
      perms: node.perms,
      isCurrent: node.is_current,
    });
    for (const group of node.children) {
      out.push({ kind: 'group', depth: depth + 1, label: group.label });
      for (const child of group.nodes) {
        this.flatten(child, depth + 1, out);
      }
    }
  }
}
