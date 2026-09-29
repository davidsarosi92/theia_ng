import { CdkDrag, CdkDragDrop, CdkDragHandle, CdkDropList, moveItemInArray } from '@angular/cdk/drag-drop';
import { Component, Input, OnInit, inject, output, signal } from '@angular/core';

import { ButtonLabelComponent } from './button-label.component';
import { I18nService } from './i18n.service';
import { IconComponent } from './icon.component';
import { ModelSchema } from './models';

interface ColumnEntry {
  name: string;
  label: string;
  shown: boolean;
}

/** Pick which list columns show, and in what order, for the signed-in user.
 *  Offers the model's column pool (`list.available`): the shown columns first in
 *  their current order, then the rest. Emits the ticked names in list order;
 *  "Reset" drops the user's choice so the code-defined default applies again. */
@Component({
  selector: 'theia-column-chooser-dialog',
  standalone: true,
  imports: [CdkDropList, CdkDrag, CdkDragHandle, ButtonLabelComponent, IconComponent],
  template: `
    <div class="dialog-backdrop" (click)="closed.emit()"></div>
    <div class="dialog">
      <button type="button" class="dialog-close" (click)="closed.emit()" [attr.aria-label]="t('close')"><theia-icon name="x" /></button>
      <h3>{{ t('columns') }}</h3>
      <p class="help col-hint">{{ t('columnsHint') }}</p>

      <div class="col-list" cdkDropList cdkDropListLockAxis="y" (cdkDropListDropped)="drop($event)">
        @for (e of entries(); track e.name) {
          <label class="col-item" cdkDrag cdkDragLockAxis="y" cdkDragBoundary=".col-list">
            <input type="checkbox" [checked]="e.shown" (change)="toggle(e.name, $any($event.target).checked)" />
            <span class="col-name">{{ e.label }}</span>
            <span
              class="col-drag"
              cdkDragHandle
              (click)="$event.preventDefault()"
              [title]="t('reorder')"
              aria-hidden="true"
            >⠿</span>
          </label>
        }
      </div>

      @if (!shownCount()) {
        <p class="errors">{{ t('columnsNeedOne') }}</p>
      }

      <div class="actions">
        @if (customized) {
          <button type="button" class="btn secondary" (click)="reset.emit()">{{ t('resetColumns') }}</button>
        }
        <button type="button" class="btn push-right" [disabled]="!shownCount()" (click)="apply()">
          <theia-blabel icon="apply" [text]="t('apply')" />
        </button>
      </div>
    </div>
  `,
})
export class ColumnChooserDialogComponent implements OnInit {
  private i18n = inject(I18nService);
  protected t = this.i18n.t;

  @Input({ required: true }) schema!: ModelSchema;
  /** Columns shown right now, in order. */
  @Input({ required: true }) current: string[] = [];
  /** Whether the user has a saved choice for this model (offers Reset). */
  @Input() customized = false;

  saved = output<string[]>();
  reset = output<void>();
  closed = output<void>();

  entries = signal<ColumnEntry[]>([]);

  ngOnInit(): void {
    const pool = this.schema.list.available ?? this.schema.list.display;
    const shown = this.current.filter((c) => pool.includes(c));
    const rest = pool.filter((c) => !shown.includes(c));
    this.entries.set([
      ...shown.map((name) => ({ name, label: this.label(name), shown: true })),
      ...rest.map((name) => ({ name, label: this.label(name), shown: false })),
    ]);
  }

  private label(name: string): string {
    return (
      this.schema.list.labels?.[name] ??
      this.schema.fields.find((f) => f.name === name)?.label ??
      name
    );
  }

  shownCount(): number {
    return this.entries().filter((e) => e.shown).length;
  }

  toggle(name: string, shown: boolean): void {
    this.entries.update((list) => list.map((e) => (e.name === name ? { ...e, shown } : e)));
  }

  drop(event: CdkDragDrop<ColumnEntry[]>): void {
    const list = [...this.entries()];
    moveItemInArray(list, event.previousIndex, event.currentIndex);
    this.entries.set(list);
  }

  apply(): void {
    const cols = this.entries().filter((e) => e.shown).map((e) => e.name);
    if (cols.length) {
      this.saved.emit(cols);
    }
  }
}
