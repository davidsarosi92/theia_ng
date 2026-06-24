import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { I18nService } from './i18n.service';
import { TreeNode } from './models';
import { TreeNodeComponent } from './tree-node.component';
import { cap, slugToKey } from './util';

@Component({
  selector: 'theia-model-tree',
  standalone: true,
  imports: [RouterLink, TreeNodeComponent],
  template: `
    <nav class="breadcrumb">
      <a routerLink="/">{{ t('home') }}</a>
      <span class="sep">/</span>
      <a [routerLink]="['/', slug]">{{ cap(rootLabel()) }}</a>
      <span class="sep">/</span>
      <span>{{ t('hierarchy') }}</span>
    </nav>

    <header class="list-header">
      <h2>{{ t('hierarchy') }}</h2>
      <button type="button" class="btn secondary" (click)="back()">{{ t('backArrow') }}</button>
    </header>

    @if (root(); as r) {
      <div class="tree-grid">
        <theia-tree-node
          [node]="r"
          [depth]="0"
          [pathKeys]="pathKeys()"
          [currentKey]="currentKey()"
          [ret]="here()"
          [onChanged]="reload"
        />
      </div>
    } @else {
      <p>{{ t('noRecords') }}</p>
    }
  `,
})
export class ModelTreeComponent implements OnInit {
  private api = inject(ApiService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private i18n = inject(I18nService);
  protected t = this.i18n.t;

  cap = cap;
  modelKey = '';
  slug = '';
  pk = '';
  root = signal<TreeNode | null>(null);
  rootLabel = signal('');
  pathKeys = signal<string[]>([]);
  currentKey = signal('');

  // Bound as an @Input callback into the recursive nodes (stable reference).
  reload = (): void => this.load();

  ngOnInit(): void {
    this.route.paramMap.subscribe((params) => {
      this.slug = params.get('modelKey') ?? '';
      this.modelKey = slugToKey(this.slug);
      this.pk = params.get('pk') ?? '';
      this.load();
    });
  }

  here(): string {
    return this.router.url;
  }

  private load(): void {
    this.api.tree(this.modelKey, this.pk).subscribe({
      next: (resp) => {
        this.rootLabel.set(resp.root.model_label);
        this.pathKeys.set(resp.path.map((p) => `${p.key}::${p.pk}`));
        this.currentKey.set(`${resp.current.key}::${resp.current.pk}`);
        this.root.set(resp.root);
      },
      // The opened record is gone (e.g. just deleted) — fall back to its list.
      error: () => this.router.navigate(['/', this.slug]),
    });
  }

  back(): void {
    const ret = this.route.snapshot.queryParamMap.get('ret');
    if (ret) {
      this.router.navigateByUrl(ret);
    } else {
      this.router.navigate(['/', this.slug, this.pk]);
    }
  }
}
