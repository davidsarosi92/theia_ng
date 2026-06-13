import { Component, OnInit, inject, signal } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { ApiService } from './api.service';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { FieldInputComponent } from './field-input.component';
import { FieldSpec, ModelSchema, RelationValue } from './models';
import { ToastService } from './toast.service';
import { cap, slugToKey } from './util';
import { ViewService } from './view.service';

@Component({
  selector: 'theia-model-detail',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, FieldInputComponent, ConfirmDialogComponent],
  template: `
    @if (schema(); as s) {
      <nav class="breadcrumb">
        <a routerLink="/">Home</a>
        <span class="sep">/</span>
        <a [routerLink]="['/', slug]">{{ cap(s.verbose_name) }}</a>
        <span class="sep">/</span>
        <span>{{ leaf }}</span>
      </nav>

      <header class="list-header">
        <h2>{{ leaf }} {{ cap(s.verbose_name) }}</h2>
        <div class="list-actions">
          @if (s.tree && !isNew) {
            <a class="btn secondary" [routerLink]="['/', slug, pk, 'tree']" [queryParams]="{ ret: here() }">Hierarchy</a>
          }
          <button type="button" class="btn secondary" (click)="back()">← Back</button>
        </div>
      </header>

      @if (errors()['__all__']; as nonField) {
        <div class="errors">{{ nonField.join(' ') }}</div>
      }

      <form [formGroup]="form" (ngSubmit)="save()">
        @for (field of formFields(); track field.name) {
          <theia-field [field]="field" [control]="controlFor(field.name)" [initial]="relationInitial(field)" [form]="form" />
          @if (errors()[field.name]; as fieldErrors) {
            <div class="errors">{{ fieldErrors.join(' ') }}</div>
          }
        }

        <div class="actions">
          @if (viewMode) {
            <div class="actions-left">
              @if (s.perms.change) {
                <button type="button" class="btn" (click)="editThis()">Edit</button>
              }
              <button type="button" (click)="back()">Back</button>
            </div>
          } @else {
            <div class="actions-left">
              <button type="submit" class="btn" [disabled]="saving()">Save</button>
              <button type="button" class="btn secondary" [disabled]="saving()" (click)="save(true)">
                Save and continue
              </button>
              <button type="button" (click)="back()">Cancel</button>
            </div>
            @if (!isNew && s.perms.delete) {
              <button type="button" class="btn danger" (click)="remove()">Delete</button>
            }
          }
        </div>
      </form>

      @if (confirmingDelete()) {
        <theia-confirm-dialog
          title="Delete record"
          message="Delete this record? This cannot be undone."
          confirmLabel="Delete"
          [danger]="true"
          (confirmed)="doRemove()"
          (cancelled)="confirmingDelete.set(false)"
        />
      }
    }
  `,
})
export class ModelDetailComponent implements OnInit {
  private api = inject(ApiService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private viewService = inject(ViewService);
  private toast = inject(ToastService);

  modelKey = '';
  /** URL slug form of modelKey (`goods-stock`), for routerLinks. */
  slug = '';
  pk = '';
  isNew = true;
  /** Read-only mode (?mode=view): form disabled, no Save/Delete. */
  viewMode = false;
  cap = cap;
  schema = signal<ModelSchema | null>(null);
  record = signal<Record<string, unknown> | null>(null);
  form = new FormGroup({});
  errors = signal<Record<string, string[]>>({});
  saving = signal(false);
  confirmingDelete = signal(false);

  ngOnInit(): void {
    this.route.paramMap.subscribe((params) => {
      this.slug = params.get('modelKey') ?? '';
      this.modelKey = slugToKey(this.slug);
      this.pk = params.get('pk') ?? 'new';
      this.isNew = this.pk === 'new';
      this.api.getSchema(this.modelKey).subscribe((s) => {
        this.schema.set(s);
        this.buildForm(s);
        if (this.isNew) {
          this.applyMode();
        } else {
          this.api.retrieve(this.modelKey, this.pk).subscribe((data) => this.populate(data));
        }
      });
    });

    // ?mode=view toggles read-only without reloading (e.g. Edit -> back to view).
    this.route.queryParamMap.subscribe((q) => {
      this.viewMode = q.get('mode') === 'view';
      this.applyMode();
    });
  }

  get leaf(): string {
    return this.isNew ? 'New' : this.viewMode ? 'View' : 'Edit';
  }

  /** This page's URL, passed to the tree as `ret` so its Back returns here. */
  here(): string {
    return this.router.url;
  }

  /** Disable the form in view mode, enable it otherwise. Read-only fields stay
   *  disabled in both modes (shown but never editable). */
  private applyMode(): void {
    if (this.viewMode) {
      this.form.disable({ emitEvent: false });
    } else {
      this.form.enable({ emitEvent: false });
    }
    // Read-only fields stay disabled regardless of view filtering.
    for (const field of this.schema()?.fields ?? []) {
      if (field.read_only) {
        this.controlFor(field.name)?.disable({ emitEvent: false });
      }
    }
  }

  editThis(): void {
    // Drop ?mode=view but keep the return target so Back still works.
    const ret = this.route.snapshot.queryParamMap.get('ret');
    this.router.navigate(['/', this.slug, this.pk], {
      queryParams: ret ? { ret } : {},
    });
  }

  /** Fields shown in the form: editable ones, plus read-only fields (shown
   *  disabled, e.g. audit fields). Plain non-editable fields stay hidden.
   *  The active view narrows this further; hidden fields keep their value (not
   *  edited). On create, required fields are always shown so saving works. */
  formFields(): FieldSpec[] {
    const base = (this.schema()?.fields ?? []).filter((f) => f.editable || f.read_only);
    const viewFields = this.viewService.fieldsFor(this.modelKey);
    if (!viewFields) {
      return base;
    }
    const allowed = new Set(viewFields);
    return base.filter((f) => allowed.has(f.name) || (this.isNew && f.required));
  }

  controlFor(name: string): FormControl {
    return this.form.get(name) as FormControl;
  }

  /** The loaded record's relation value (with labels) for the combobox. */
  relationInitial(field: FieldSpec): RelationValue | RelationValue[] | null {
    if (field.type !== 'fk' && field.type !== 'm2m') {
      return null;
    }
    return (this.record()?.[field.name] as RelationValue | RelationValue[] | null) ?? null;
  }

  private buildForm(s: ModelSchema): void {
    const group: Record<string, FormControl> = {};
    for (const field of s.fields) {
      if (field.editable || field.read_only) {
        const isArray = field.type === 'm2m' || field.widget === 'multiselect';
        const isObject = field.widget === 'model_field_select';
        const initial = isArray ? [] : isObject ? {} : field.default ?? null;
        group[field.name] = new FormControl(initial);
      }
    }
    this.form = new FormGroup(group);
  }

  private populate(data: Record<string, unknown>): void {
    this.record.set(data);
    for (const field of this.formFields()) {
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
    this.applyMode();
  }

  /** Save the form. ``continueEditing`` keeps you on the record afterwards
   *  (Django's "Save and continue editing"); otherwise it returns to the list. */
  save(continueEditing = false): void {
    this.saving.set(true);
    this.errors.set({});
    const body = this.form.value;
    const obs = this.isNew
      ? this.api.create(this.modelKey, body)
      : this.api.update(this.modelKey, this.pk, body);
    obs.subscribe({
      next: (record) => {
        this.saving.set(false);
        this.toast.success(this.isNew ? 'Created.' : 'Saved.');
        this.refreshViewsIfNeeded();
        if (!continueEditing) {
          this.back();
          return;
        }
        if (this.isNew) {
          // Move to the created record's edit URL so editing continues on it.
          const newPk = String((record as { pk?: unknown })?.pk ?? '');
          const ret = this.route.snapshot.queryParamMap.get('ret');
          this.router.navigate(['/', this.slug, newPk], { queryParams: ret ? { ret } : {} });
        } else {
          // Reload so derived/audit fields (modified, etc.) refresh.
          this.api.retrieve(this.modelKey, this.pk).subscribe((data) => this.populate(data));
        }
      },
      error: (err) => {
        this.saving.set(false);
        this.errors.set(err?.error?.errors ?? { __all__: ['Save failed.'] });
        this.toast.error('Could not save — check the form.');
      },
    });
  }

  remove(): void {
    this.confirmingDelete.set(true);
  }

  doRemove(): void {
    this.confirmingDelete.set(false);
    this.api.remove(this.modelKey, this.pk).subscribe({
      next: () => {
        this.toast.success('Deleted.');
        this.refreshViewsIfNeeded();
        this.back();
      },
      error: () => this.toast.error('Could not delete.'),
    });
  }

  /** Editing the MenuView model changes the sidebar views — refresh them. */
  private refreshViewsIfNeeded(): void {
    if (this.modelKey === 'theia_ng.menuview') {
      this.viewService.reload();
    }
  }

  back(): void {
    // Return to where we came from (filtered list, or the parent record), else
    // fall back to this model's list.
    const ret = this.route.snapshot.queryParamMap.get('ret');
    if (ret) {
      this.router.navigateByUrl(ret);
    } else {
      this.router.navigate(['/', this.slug]);
    }
  }
}
