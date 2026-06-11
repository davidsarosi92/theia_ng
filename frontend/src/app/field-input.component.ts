import { Component, Input } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';

import { FieldSpec, RelationValue } from './models';
import { RelationSelectComponent } from './relation-select.component';
import { WidgetKind, inputTypeFor, widgetFor } from './field-widgets';

@Component({
  selector: 'theia-field',
  standalone: true,
  imports: [ReactiveFormsModule, RelationSelectComponent],
  template: `
    <label class="field">
      <span class="field-label">
        {{ field.label }}@if (field.required) {<em class="req">*</em>}
      </span>

      @switch (widgetType()) {
        @case ('textarea') {
          <textarea [formControl]="control" rows="4"></textarea>
        }
        @case ('checkbox') {
          <input type="checkbox" [formControl]="control" />
        }
        @case ('select') {
          <select [formControl]="control">
            <option [ngValue]="null">—</option>
            @for (c of field.choices ?? []; track c.value) {
              <option [ngValue]="c.value">{{ c.label }}</option>
            }
          </select>
        }
        @case ('relation') {
          <theia-relation-select [field]="field" [control]="control" [initial]="initial" [form]="form" />
        }
        @default {
          <input [type]="inputType()" [formControl]="control" />
        }
      }

      @if (field.help_text) {
        <small class="help">{{ field.help_text }}</small>
      }
    </label>
  `,
})
export class FieldInputComponent {
  @Input({ required: true }) field!: FieldSpec;
  @Input({ required: true }) control!: FormControl;
  @Input() initial: RelationValue | RelationValue[] | null = null;
  @Input() form?: FormGroup;

  widgetType(): WidgetKind {
    return widgetFor(this.field.type);
  }

  inputType(): string {
    return inputTypeFor(this.field.type);
  }
}
