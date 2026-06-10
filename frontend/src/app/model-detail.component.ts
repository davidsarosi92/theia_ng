import { Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { ApiService } from './api.service';
import { FieldInputComponent } from './field-input.component';
import { FieldSpec, ModelSchema, RelationValue } from './models';

@Component({
  selector: 'theia-model-detail',
  standalone: true,
  imports: [ReactiveFormsModule, FieldInputComponent],
  template: `
    @if (schema(); as s) {
      <header class="list-header">
        <h2>{{ isNew ? 'New ' + s.verbose_name : 'Edit ' + s.verbose_name }}</h2>
      </header>

      @if (errors()['__all__']; as nonField) {
        <div class="errors">{{ nonField.join(' ') }}</div>
      }

      <form [formGroup]="form" (ngSubmit)="save()">
        @for (field of editableFields(); track field.name) {
          <theia-field [field]="field" [control]="controlFor(field.name)" />
          @if (errors()[field.name]; as fieldErrors) {
            <div class="errors">{{ fieldErrors.join(' ') }}</div>
          }
        }

        <div class="actions">
          <button type="submit" class="btn" [disabled]="saving()">Save</button>
          @if (!isNew && s.perms.delete) {
            <button type="button" class="btn danger" (click)="remove()">Delete</button>
          }
          <button type="button" (click)="back()">Cancel</button>
        </div>
      </form>
    }
  `,
})
export class ModelDetailComponent implements OnInit {
  private api = inject(ApiService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  modelKey = '';
  pk = '';
  isNew = true;
  schema = signal<ModelSchema | null>(null);
  form = new FormGroup({});
  errors = signal<Record<string, string[]>>({});
  saving = signal(false);

  ngOnInit(): void {
    this.route.paramMap.subscribe((params) => {
      this.modelKey = params.get('modelKey') ?? '';
      this.pk = params.get('pk') ?? 'new';
      this.isNew = this.pk === 'new';
      this.api.getSchema(this.modelKey).subscribe((s) => {
        this.schema.set(s);
        this.buildForm(s);
        if (!this.isNew) {
          this.api.retrieve(this.modelKey, this.pk).subscribe((data) => this.populate(data));
        }
      });
    });
  }

  editableFields(): FieldSpec[] {
    return (this.schema()?.fields ?? []).filter((f) => f.editable && !f.read_only);
  }

  controlFor(name: string): FormControl {
    return this.form.get(name) as FormControl;
  }

  private buildForm(s: ModelSchema): void {
    const group: Record<string, FormControl> = {};
    for (const field of s.fields) {
      if (field.editable && !field.read_only) {
        const initial = field.type === 'm2m' ? [] : field.default ?? null;
        group[field.name] = new FormControl(initial);
      }
    }
    this.form = new FormGroup(group);
  }

  private populate(data: Record<string, unknown>): void {
    for (const field of this.editableFields()) {
      const raw = data[field.name];
      let value: unknown = raw;
      if (field.type === 'fk') {
        value = (raw as RelationValue | null)?.id ?? null;
      } else if (field.type === 'm2m') {
        value = ((raw as RelationValue[]) ?? []).map((r) => r.id);
      } else if (field.type === 'datetime' && typeof raw === 'string') {
        value = raw.slice(0, 16); // ISO -> datetime-local
      }
      this.controlFor(field.name)?.setValue(value);
    }
  }

  save(): void {
    this.saving.set(true);
    this.errors.set({});
    const body = this.form.value;
    const obs = this.isNew
      ? this.api.create(this.modelKey, body)
      : this.api.update(this.modelKey, this.pk, body);
    obs.subscribe({
      next: () => {
        this.saving.set(false);
        this.back();
      },
      error: (err) => {
        this.saving.set(false);
        this.errors.set(err?.error?.errors ?? { __all__: ['Save failed.'] });
      },
    });
  }

  remove(): void {
    if (!confirm('Delete this record?')) {
      return;
    }
    this.api.remove(this.modelKey, this.pk).subscribe(() => this.back());
  }

  back(): void {
    this.router.navigate(['/', this.modelKey]);
  }
}
