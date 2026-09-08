import { Component, Input, computed, inject, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { ApiService } from './api.service';
import { ButtonLabelComponent } from './button-label.component';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { AppliedFilter, DATE_PRESETS } from './filter-dialog.component';
import { I18nService } from './i18n.service';
import { IconComponent } from './icon.component';
import { AssistPreview, AssistState, FieldSpec, ModelSchema } from './models';

/** One exchange in the panel. The interpretation is shown inside the turn, not
 *  in a separate pane: at the moment that matters (checking what the model
 *  understood before acting on it) the user must not look in two places. */
interface Turn {
  prompt: string;
  /** True until the answer lands: the turn is on screen from the moment you ask. */
  pending?: boolean;
  state?: AssistState;
  filters?: AppliedFilter[];
  rejected?: string[];
  preview?: AssistPreview | null;
  error?: string;
  applied?: boolean;
  done?: boolean;
}

@Component({
  selector: 'theia-assist-panel',
  standalone: true,
  imports: [FormsModule, ButtonLabelComponent, ConfirmDialogComponent, IconComponent],
  template: `
    <div class="dialog-backdrop" (click)="closed.emit()"></div>
    <aside class="assist-panel" role="dialog" [attr.aria-label]="t('assistTitle')">
      <header class="assist-head">
        <h3>{{ t('assistTitle') }}</h3>
        @if (turns().length) {
          <button type="button" class="assist-clear" (click)="clearing.set(true)"
                  [title]="t('assistClear')" [attr.aria-label]="t('assistClear')">
            <theia-icon name="trash" />
          </button>
        }
        <button type="button" class="dialog-close" (click)="closed.emit()"
                [attr.aria-label]="t('close')"><theia-icon name="x" /></button>
      </header>

      @if (unavailable()) {
        <p class="assist-down">{{ t('assistUnreachable') }}</p>
      }

      <div class="assist-turns">
        @if (!turns().length) {
          <p class="assist-hint">{{ t('assistHint') }}</p>
        }
        @for (turn of turns(); track $index) {
          <div class="assist-turn">
            <p class="assist-prompt">{{ turn.prompt }}</p>

            @if (turn.pending) {
              <p class="assist-hint">{{ t('loading') }}</p>
            } @else if (turn.error) {
              <p class="assist-error">{{ turn.error }}</p>
            } @else if (turn.state; as st) {
              @if (!turn.filters?.length && !st.search && !st.ordering && !createPairs(st).length) {
                <p class="assist-error">{{ t('assistNothing') }}</p>
              } @else {
                <div class="assist-card">
                  @if (st.search) {
                    <div class="assist-chip"><span class="k">{{ t('search') }}</span>{{ st.search }}</div>
                  }
                  @for (f of turn.filters; track f.field) {
                    <div class="assist-chip"><span class="k">{{ f.label }}</span>{{ f.display }}</div>
                  }
                  @if (st.ordering) {
                    <div class="assist-chip"><span class="k">{{ t('assistSort') }}</span>{{ st.ordering }}</div>
                  }
                  @for (kv of createPairs(st); track kv[0]) {
                    <div class="assist-chip"><span class="k">{{ kv[0] }}</span>{{ kv[1] }}</div>
                  }
                </div>
              }

              <!-- Never let a dropped or unexpressible part pass silently: the
                   user would act on a filter narrower than what they asked for. -->
              @if (st.unsupported.length) {
                <p class="assist-warn">{{ t('assistUnsupported') }}
                  <em>{{ st.unsupported.join('; ') }}</em></p>
              }
              @if (turn.rejected?.length) {
                <p class="assist-warn">{{ t('assistRejected') }}</p>
              }

              @if (st.intent === 'delete') {
                <button type="button" class="btn danger" [disabled]="turn.done"
                        (click)="confirming.set(turn)">
                  <theia-blabel icon="delete"
                    [text]="turn.done ? t('assistDone') : t('assistReviewDelete')" />
                </button>
              } @else if (st.intent === 'create') {
                <button type="button" class="btn" [disabled]="turn.done"
                        (click)="confirming.set(turn)">
                  <theia-blabel icon="add"
                    [text]="turn.done ? t('assistDone') : t('assistReviewCreate')" />
                </button>
              } @else if (turn.filters?.length || st.search || st.ordering) {
                <button type="button" class="btn" [disabled]="turn.applied"
                        (click)="applyTurn(turn)">
                  <theia-blabel icon="filter"
                    [text]="turn.applied ? t('assistApplied') : t('assistApply')" />
                </button>
              }
            }
          </div>
        }
      </div>

      <form class="assist-form" (submit)="submit($event)">
        <input class="search" type="text" [(ngModel)]="draft" name="prompt"
               [disabled]="busy()" [placeholder]="t('assistPlaceholder')" autocomplete="off" />
        <button type="submit" class="btn" [disabled]="busy() || !draft.trim()">
          <theia-blabel icon="ok" [text]="t('assistSend')" />
        </button>
      </form>
    </aside>

    @if (clearing()) {
      <theia-confirm-dialog
        [title]="t('assistClear')"
        [message]="t('assistClearConfirm')"
        [hint]="t('assistClearHint')"
        [confirmLabel]="t('assistClear')"
        [cancelLabel]="t('cancel')"
        [danger]="true"
        (confirmed)="clearTurns()"
        (cancelled)="clearing.set(false)"
      />
    }

    <!-- Irreversible proposals get their own modal showing the REAL queryset
         (exact count + sample rows), because that is the only thing worth
         checking before a delete. -->
    @if (confirming(); as turn) {
      <div class="dialog-backdrop assist-confirm-backdrop" (click)="confirming.set(null)"></div>
      <div class="assist-confirm dialog">
        <h3>{{ turn.state?.intent === 'delete' ? t('assistConfirmDelete') : t('assistConfirmCreate') }}</h3>

        <p class="assist-final">{{ t('assistFinalWarning') }}</p>

        @if (turn.state?.intent === 'delete') {
          <p class="assist-count">{{ t('assistDeleteCount', { count: turn.preview?.count ?? 0 }) }}</p>
          <div class="assist-rows">
            <ul>
              @for (row of turn.preview?.rows ?? []; track $index) {
                <li>{{ rowLabel(row) }}</li>
              }
            </ul>
            @if ((turn.preview?.count ?? 0) > (turn.preview?.shown ?? 0)) {
              <p class="assist-more">{{ t('assistAndMore', {
                count: (turn.preview?.count ?? 0) - (turn.preview?.shown ?? 0) }) }}</p>
            }
          </div>
          <table class="filters-table">
            <tbody>
              @if (turn.state?.search) {
                <tr><td class="f-key">{{ t('search') }}</td><td>{{ turn.state?.search }}</td></tr>
              }
              @for (f of turn.filters; track f.field) {
                <tr><td class="f-key">{{ f.label }}</td><td>{{ f.display }}</td></tr>
              }
            </tbody>
          </table>
        } @else {
          <table class="filters-table">
            <tbody>
              @for (kv of createPairs(turn.state!); track kv[0]) {
                <tr><td class="f-key">{{ kv[0] }}</td><td>{{ kv[1] }}</td></tr>
              }
            </tbody>
          </table>
        }

        <div class="actions">
          <button type="button" class="btn secondary" (click)="confirming.set(null)">
            {{ t('assistNo') }}
          </button>
          <button type="button" class="btn push-right"
                  [class.danger]="turn.state?.intent === 'delete'"
                  [disabled]="running()" (click)="runProposal(turn)">
            {{ t('assistYes') }}
          </button>
        </div>
      </div>
    }
  `,
})
export class AssistPanelComponent {
  private api = inject(ApiService);
  private i18n = inject(I18nService);
  protected t = this.i18n.t;

  @Input({ required: true }) schema!: ModelSchema;
  @Input({ required: true }) modelKey!: string;

  /** Emitted only when the user presses Apply — never on interpretation alone. */
  applied = output<{ search: string; filters: AppliedFilter[]; ordering: string | null }>();
  /** A confirmed delete/create, handed to the list to run through the normal
   *  endpoints. `done(ok)` reports back so the turn can be marked finished. */
  executed = output<{
    kind: 'delete' | 'create';
    turn: AssistState;
    filters: AppliedFilter[];
    done: (ok: boolean) => void;
  }>();
  closed = output<void>();

  draft = '';
  turns = signal<Turn[]>([]);
  busy = signal(false);
  /** The proposal awaiting an explicit Yes. Nothing runs while this is null. */
  confirming = signal<Turn | null>(null);
  running = signal(false);
  clearing = signal(false);
  /** Sticky: an unreachable model is a state, not a one-off message — otherwise
   *  each retry costs another timeout before the user learns anything new. */
  unavailable = signal(false);

  submit(event: Event): void {
    event.preventDefault();
    const prompt = this.draft.trim();
    if (!prompt || this.busy()) {
      return;
    }
    this.draft = '';
    this.busy.set(true);
    const turn: Turn = { prompt, pending: true };
    this.turns.update((ts) => [...ts, turn]);
    this.api.assist(this.modelKey, prompt).subscribe({
      next: (res) => {
        this.unavailable.set(false);   // a successful answer clears the "down" state
        this.resolve(turn, {
          pending: false,
          state: res.state,
          filters: this.toApplied(res.state),
          rejected: res.rejected,
          preview: res.preview,
        });
      },
      error: (err) => {
        if (err?.status === 503 || err?.status === 0) {
          this.unavailable.set(true);
        }
        this.resolve(turn, { pending: false, error: this.errorText(err) });
      },
    });
  }

  /** Replace the pending turn in place, by identity, so a slow answer cannot
   *  land on the wrong bubble if the user asked again meanwhile. */
  private resolve(turn: Turn, patch: Partial<Turn>): void {
    this.turns.update((ts) => ts.map((x) => (x === turn ? { ...x, ...patch } : x)));
    this.busy.set(false);
  }

  /** Carry out a confirmed proposal — through the ordinary endpoints, which do
   *  their own permission checks and write the audit entry. */
  runProposal(turn: Turn): void {
    if (!turn.state || this.running()) {
      return;
    }
    this.running.set(true);
    const finish = (ok: boolean) => {
      this.running.set(false);
      this.confirming.set(null);
      if (ok) {
        this.turns.update((ts) => ts.map((x) => (x === turn ? { ...x, done: true } : x)));
      }
    };
    if (turn.state.intent === 'delete') {
      this.executed.emit({ kind: 'delete', turn: turn.state, filters: turn.filters ?? [],
                           done: finish });
    } else {
      this.executed.emit({ kind: 'create', turn: turn.state, filters: [], done: finish });
    }
  }

  /** Drop this session's conversation. Local only — the audit trail of what was
   *  asked lives on the server and is deliberately not affected. */
  clearTurns(): void {
    this.turns.set([]);
    this.confirming.set(null);
    this.clearing.set(false);
  }

  createPairs(state: AssistState): [string, string][] {
    const byName = new Map((this.schema.fields ?? []).map((f) => [f.name, f]));
    return Object.entries(state.create ?? {}).map(
      ([k, v]) => [byName.get(k)?.label ?? k, v] as [string, string],
    );
  }

  /** The list already labels rows by __str__; reuse it so the modal shows the
   *  same identity the user sees in the table. */
  rowLabel(row: Record<string, unknown>): string {
    return String(row['__str__'] ?? row['pk'] ?? row['id'] ?? '');
  }

  private errorText(err: { status?: number; error?: { detail?: string } }): string {
    if (err?.status === 503) {
      // The server's own text names the actual cause (bad URL, refused, timeout),
      // which is what a deployer needs; fall back to the generic line.
      return err?.error?.detail || this.t('assistUnreachable');
    }
    if (err?.status === 0) {
      return this.t('assistUnreachable');
    }
    if (err?.status === 404) {
      return this.t('assistNotHere');
    }
    return err?.error?.detail || this.t('assistFailed');
  }

  applyTurn(turn: Turn): void {
    if (!turn.state) {
      return;
    }
    this.applied.emit({
      search: turn.state.search,
      filters: turn.filters ?? [],
      ordering: turn.state.ordering,
    });
    this.turns.update((ts) => ts.map((x) => (x === turn ? { ...x, applied: true } : x)));
  }

  /** The server commits only to {field, value}; labels and human-readable values
   *  come from the schema the SPA already has, so the card reads like the
   *  filter table it will become. */
  private toApplied(state: AssistState): AppliedFilter[] {
    const byName = new Map<string, FieldSpec>();
    for (const f of this.schema.fields ?? []) {
      byName.set(f.name, f);
    }
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
