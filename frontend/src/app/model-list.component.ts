import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { ModelSchema } from './models';

@Component({
  selector: 'theia-model-list',
  standalone: true,
  imports: [RouterLink],
  template: `
    @if (schema(); as s) {
      <header class="list-header">
        <h2>{{ s.verbose_name }}</h2>
        @if (s.perms.add) {
          <a class="btn" [routerLink]="['/', modelKey, 'new']">+ Add</a>
        }
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

      <table class="grid">
        <thead>
          <tr>
            @for (col of columns(); track col) {
              <th>{{ col }}</th>
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

  ngOnInit(): void {
    this.route.paramMap.subscribe((params) => {
      this.modelKey = params.get('modelKey') ?? '';
      this.page.set(1);
      this.searchTerm.set('');
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

  private load(): void {
    this.api
      .list(this.modelKey, { page: this.page(), search: this.searchTerm() })
      .subscribe((resp) => {
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
