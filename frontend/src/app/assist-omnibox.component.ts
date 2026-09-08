import {
  Component,
  ElementRef,
  HostListener,
  computed,
  effect,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ApiService } from './api.service';
import { ButtonLabelComponent } from './button-label.component';
import { AppliedFilter, DATE_PRESETS } from './filter-dialog.component';
import { I18nService } from './i18n.service';
import { IconComponent } from './icon.component';
import { AssistState, FieldSpec, ModelSchema, RegistryModel } from './models';
import { cap, keyToSlug } from './util';

/**
 * Cmd/Ctrl+K from anywhere: type what you want, land on the filtered list.
 *
 * The panel on the list page needs you to be on that page first; this is what
 * delivers "just describe it" from wherever you are.
 *
 * **It only ever applies a filter.** If the model proposes a delete or a create,
 * the omnibox applies the filter and points you at the list's assistant panel
 * for the destructive step, rather than duplicating the confirmation flow. One
 * place owns the irreversible path, which is the one worth getting right.
 */
@Component({
  selector: 'theia-assist-omnibox',
  standalone: true,
  imports: [FormsModule, ButtonLabelComponent, IconComponent],
  template: `
    @if (open()) {
      <div class="dialog-backdrop omnibox-backdrop" (click)="close()"></div>
      <div class="omnibox" role="dialog" [attr.aria-label]="t('assistTitle')">
        <div class="omnibox-bar">
          <theia-icon name="search" />
          @if (target(); as m) {
            <button type="button" class="omnibox-chip" (click)="clearTarget()"
                    [title]="t('assistOmniboxChange')">
              {{ cap(m.verbose_name) }} <theia-icon name="x" />
            </button>
          }
          <input #box class="omnibox-input" type="text"
                 [ngModel]="draft()" (ngModelChange)="draft.set($event)"
                 [disabled]="busy()"
                 [placeholder]="target() ? t('assistPlaceholder') : t('assistOmniboxPickModel')"
                 (keydown.enter)="submit()" autocomplete="off" />
        </div>

        <div class="omnibox-body">
          @if (!target()) {
            @if (!candidates().length) {
              <p class="assist-hint">{{ t('assistOmniboxNoModels') }}</p>
            }
            @for (m of candidates(); track m.key) {
              <button type="button" class="omnibox-row" (click)="pick(m)">
                <span>{{ cap(m.verbose_name) }}</span>
                <span class="omnibox-app">{{ m.app_verbose_name }}</span>
              </button>
            }
          } @else if (busy()) {
            <p class="assist-hint">{{ t('loading') }}</p>
          } @else if (error()) {
            <p class="assist-error">{{ error() }}</p>
          } @else if (result(); as r) {
            <div class="assist-card">
              @if (r.state.search) {
                <div class="assist-chip"><span class="k">{{ t('search') }}</span>{{ r.state.search }}</div>
              }
              @for (f of r.filters; track f.field) {
                <div class="assist-chip"><span class="k">{{ f.label }}</span>{{ f.display }}</div>
              }
              @if (r.state.ordering) {
                <div class="assist-chip"><span class="k">{{ t('assistSort') }}</span>{{ r.state.ordering }}</div>
              }
            </div>
            @if (r.state.unsupported.length) {
              <p class="assist-warn">{{ t('assistUnsupported') }}
                <em>{{ r.state.unsupported.join('; ') }}</em></p>
            }
            @if (r.state.intent !== 'filter') {
              <p class="assist-warn">{{ t('assistOmniboxUseThePanel') }}</p>
            }
            <button type="button" class="btn" (click)="apply()">
              <theia-blabel icon="filter" [text]="t('assistOmniboxGo')" />
            </button>
          } @else {
            <p class="assist-hint">{{ t('assistHint') }}</p>
          }
        </div>
      </div>
    }
  `,
})
export class AssistOmniboxComponent {
  private api = inject(ApiService);
  private router = inject(Router);
  private i18n = inject(I18nService);
  protected t = this.i18n.t;
  protected cap = cap;

  open = signal(false);
  draft = signal('');
  private box = viewChild<ElementRef<HTMLInputElement>>('box');

  constructor() {
    // The whole point is "just type" — focus the box as soon as it exists.
    // The viewChild only resolves once `open()` renders it, so this effect runs
    // exactly then.
    effect(() => {
      const el = this.box()?.nativeElement;
      if (this.open() && el) {
        el.focus();
      }
    });
  }

  busy = signal(false);
  error = signal('');
  target = signal<RegistryModel | null>(null);
  models = signal<RegistryModel[]>([]);
  result = signal<{ state: AssistState; filters: AppliedFilter[] } | null>(null);
  private schema: ModelSchema | null = null;

  /** Only models the user may view *and* where the assistant is configured — an
   *  entry that would 404 on the first keystroke is worse than no entry. */
  candidates = computed(() => {
    const q = this.draft().trim().toLowerCase();
    const all = this.models().filter((m) => m.assist && m.perms.view);
    const hit = q
      ? all.filter((m) => (m.verbose_name + ' ' + m.app_verbose_name).toLowerCase().includes(q))
      : all;
    return hit.slice(0, 8);
  });

  @HostListener('document:keydown', ['$event'])
  onKey(event: KeyboardEvent): void {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      this.open() ? this.close() : this.launch();
      return;
    }
    if (event.key === 'Escape' && this.open()) {
      this.close();
    }
  }

  /** Public so the topbar button can open it — the shortcut alone is not
   *  discoverable, and a keyboard accelerator is no use to someone who has
   *  never been told it exists. */
  launch(): void {
    this.reset();
    this.open.set(true);
    this.api.getRegistry().subscribe((r) => {
      this.models.set(r.models);
      // Preselect the model of the page you are on, so the common case is pure
      // typing; the chip can be dismissed to search for another.
      const slug = this.router.url.split('?')[0].split('/').filter(Boolean)[0];
      const here = r.models.find((m) => keyToSlug(m.key) === slug);
      if (here?.assist && here.perms.view) {
        this.pick(here);
      }
    });
  }

  close(): void {
    this.open.set(false);
    this.reset();
  }

  private reset(): void {
    this.draft.set('');
    this.busy.set(false);
    this.error.set('');
    this.target.set(null);
    this.result.set(null);
    this.schema = null;
  }

  pick(model: RegistryModel): void {
    this.target.set(model);
    this.draft.set('');
    this.result.set(null);
    this.api.getSchema(model.key).subscribe((s) => (this.schema = s));
  }

  clearTarget(): void {
    this.target.set(null);
    this.result.set(null);
    this.schema = null;
  }

  submit(): void {
    const model = this.target();
    const prompt = this.draft().trim();
    if (!model) {
      const first = this.candidates()[0];
      if (first) {
        this.pick(first);
      }
      return;
    }
    if (!prompt || this.busy()) {
      return;
    }
    this.busy.set(true);
    this.error.set('');
    this.api.assist(model.key, prompt).subscribe({
      next: (res) => {
        this.result.set({ state: res.state, filters: this.toApplied(res.state) });
        this.busy.set(false);
      },
      error: (err: { status?: number; error?: { detail?: string } }) => {
        this.error.set(
          err?.status === 503 || err?.status === 0
            ? err?.error?.detail || this.t('assistUnreachable')
            : err?.error?.detail || this.t('assistFailed'),
        );
        this.busy.set(false);
      },
    });
  }

  /** Navigate to the list with the state in the query — the list restores
   *  search/filters/sort from there, so no extra plumbing is needed. */
  apply(): void {
    const model = this.target();
    const r = this.result();
    if (!model || !r) {
      return;
    }
    this.close();
    this.router.navigate(['/', keyToSlug(model.key)], {
      queryParams: {
        q: r.state.search || null,
        o: r.state.ordering || null,
        filters: r.filters.length ? JSON.stringify(r.filters) : null,
      },
    });
  }

  private toApplied(state: AssistState): AppliedFilter[] {
    const byName = new Map((this.schema?.fields ?? []).map((f) => [f.name, f]));
    return state.filters.map((f) => {
      const spec = byName.get(f.field);
      return {
        field: f.field,
        label: spec?.label ?? f.field,
        value: f.value,
        display: this.display(spec, f.value),
      };
    });
  }

  private display(spec: FieldSpec | undefined, value: string): string {
    if (spec?.type === 'choice') {
      const hit = spec.choices?.find((c) => String(c.value) === value);
      if (hit) {
        return hit.label;
      }
    }
    return DATE_PRESETS.find((p) => p.key === value)?.label ?? value;
  }
}
