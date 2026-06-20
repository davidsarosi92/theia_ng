import { Component, Input, OnInit, WritableSignal, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';

import { FieldInputComponent } from './field-input.component';
import { I18nService } from './i18n.service';
import { FieldSpec, InlineConfig, RelationValue } from './models';

/** One editable child row: its form group, the local id (for tracking), the
 *  server pk (null for a new row), the relation initials (labels) for pickers,
 *  and a delete flag. */
interface InlineRow {
  uid: number;
  pk: unknown;
  group: FormGroup;
  initial: Record<string, unknown>;
  deleted: WritableSignal<boolean>;
}

let _uid = 0;

/** Edits a parent's related child rows (an inline). Reuses ``theia-field`` for
 *  each cell, so child FK/choice/scalar editors work exactly like the main form.
 *  ``tabular`` lays rows out as a grid (labels become column headers); ``stacked``
 *  renders each row as a labelled block. Call ``getPayload()`` to read the rows
 *  for submission (new rows have no ``pk``; deleted existing rows carry
 *  ``_delete``). */
@Component({
  selector: 'theia-inline-editor',
  standalone: true,
  imports: [ReactiveFormsModule, FieldInputComponent],
  template: `
    <section class="inline" [class.inline-stacked]="inline.style === 'stacked'">
      <h3 class="inline-title">{{ inline.title }}</h3>

      @if (inline.style === 'tabular') {
        <div class="table-wrap inline-table-wrap">
          <table class="grid inline-grid">
            <thead>
              <tr>
                @for (f of inline.fields; track f.name) {
                  <th>{{ f.label }}@if (f.required) {<em class="req">*</em>}</th>
                }
                @if (inline.can_delete) { <th class="inline-del-col"></th> }
              </tr>
            </thead>
            <tbody>
              @for (row of rows(); track row.uid) {
                <tr [class.row-deleted]="row.deleted()">
                  @for (f of inline.fields; track f.name) {
                    <td>
                      <theia-field
                        [field]="f"
                        [control]="ctrl(row, f.name)"
                        [initial]="initialRel(row, f)"
                        [form]="row.group"
                      />
                    </td>
                  }
                  @if (inline.can_delete) {
                    <td class="inline-del-col">
                      <button type="button" class="rel-act danger" (click)="toggleDelete(row)">
                        {{ row.deleted() ? '↩' : '✕' }}
                      </button>
                    </td>
                  }
                </tr>
              }
            </tbody>
          </table>
        </div>
      } @else {
        @for (row of rows(); track row.uid) {
          <div class="inline-block" [class.row-deleted]="row.deleted()">
            @for (f of inline.fields; track f.name) {
              <theia-field
                [field]="f"
                [control]="ctrl(row, f.name)"
                [initial]="initialRel(row, f)"
                [form]="row.group"
              />
            }
            @if (inline.can_delete) {
              <button type="button" class="btn small danger" (click)="toggleDelete(row)">
                {{ row.deleted() ? t('back') : t('delete') }}
              </button>
            }
          </div>
        }
      }

      <button type="button" class="btn small secondary inline-add" (click)="addRow()">
        + {{ t('add') }}
      </button>
    </section>
  `,
})
export class InlineEditorComponent implements OnInit {
  @Input({ required: true }) inline!: InlineConfig;
  /** Existing child rows (serialized like a detail record: pk + values, with
   *  relations as {id,label}). */
  @Input() initialRows: Record<string, unknown>[] = [];

  private i18n = inject(I18nService);
  protected t = this.i18n.t;
  rows = signal<InlineRow[]>([]);

  ngOnInit(): void {
    const existing = this.initialRows.map((r) => this.buildRow(r));
    const blanks = Array.from({ length: this.inline.extra }, () => this.buildRow({}));
    this.rows.set([...existing, ...blanks]);
  }

  ctrl(row: InlineRow, name: string): FormControl {
    return row.group.get(name) as FormControl;
  }

  /** Relation initial (labels) for a row's FK/M2M picker. */
  initialRel(row: InlineRow, field: FieldSpec): RelationValue | RelationValue[] | null {
    if (field.type !== 'fk' && field.type !== 'm2m') {
      return null;
    }
    return (row.initial[field.name] as RelationValue | RelationValue[] | null) ?? null;
  }

  addRow(): void {
    this.rows.update((rs) => [...rs, this.buildRow({})]);
  }

  toggleDelete(row: InlineRow): void {
    row.deleted.update((d) => !d);
  }

  /** Build a row form group from the inline's fields, seeded from ``data``. */
  private buildRow(data: Record<string, unknown>): InlineRow {
    const group: Record<string, FormControl> = {};
    for (const field of this.inline.fields) {
      if (!(field.editable || field.read_only)) {
        continue;
      }
      const isArray = field.type === 'm2m' || field.widget === 'multiselect';
      let value: unknown = data[field.name];
      if (field.type === 'fk') {
        value = (value as RelationValue | null)?.id ?? null;
      } else if (field.type === 'm2m') {
        value = ((value as RelationValue[]) ?? []).map((r) => r.id);
      } else if (field.type === 'datetime' && typeof value === 'string') {
        value = value.slice(0, 16);
      } else if (value === undefined) {
        value = isArray ? [] : field.default ?? null;
      }
      const control = new FormControl(value);
      if (field.read_only) {
        control.disable({ emitEvent: false });
      }
      group[field.name] = control;
    }
    return {
      uid: _uid++,
      pk: data['pk'] ?? null,
      group: new FormGroup(group),
      initial: data,
      deleted: signal(false),
    };
  }

  /** Rows to submit. New blank-and-untouched rows are skipped; deleted existing
   *  rows are sent with ``_delete``; deleted new rows are dropped entirely. */
  getPayload(): Record<string, unknown>[] {
    const out: Record<string, unknown>[] = [];
    for (const row of this.rows()) {
      const deleted = row.deleted();
      if (deleted && row.pk == null) {
        continue; // a new row marked deleted never existed
      }
      if (deleted) {
        out.push({ pk: row.pk, _delete: true });
        continue;
      }
      const value = row.group.getRawValue();
      if (row.pk == null && this.isBlank(value)) {
        continue; // untouched extra row
      }
      out.push(row.pk != null ? { pk: row.pk, ...value } : value);
    }
    return out;
  }

  private isBlank(value: Record<string, unknown>): boolean {
    return Object.values(value).every(
      (v) => v === null || v === '' || v === undefined || (Array.isArray(v) && v.length === 0),
    );
  }
}
