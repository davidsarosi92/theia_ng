import {
  Component,
  OnDestroy,
  OnInit,
  QueryList,
  ViewChildren,
  inject,
  signal,
} from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';

import { ActionDialogComponent } from './action-dialog.component';
import { ApiService } from './api.service';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { FieldInputComponent } from './field-input.component';
import { I18nService } from './i18n.service';
import { CompactTreeComponent } from './compact-tree.component';
import { InlineEditorComponent } from './inline-editor.component';
import { ActionSpec, FieldSpec, InlineConfig, ModelSchema, RelationValue } from './models';
import { ToastService } from './toast.service';
import { cap, slugToKey } from './util';
import { ViewService } from './view.service';

/** A resolved form section: its heading + the FieldSpecs it contains. */
interface FieldsetGroup {
  title: string | null;
  description: string | null;
  collapsible: boolean;
  fields: FieldSpec[];
}

@Component({
  selector: 'theia-model-detail',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    FieldInputComponent,
    ConfirmDialogComponent,
    InlineEditorComponent,
    ActionDialogComponent,
    CompactTreeComponent,
  ],
  template: `
    @if (loading()) {
      <div class="detail-loading"><span class="loading-pill"><span class="spinner"></span>{{ t('loading') }}</span></div>
    } @else if (schema(); as s) {
      <nav class="breadcrumb">
        <a routerLink="/">{{ t('home') }}</a>
        <span class="sep">/</span>
        <a [routerLink]="['/', slug]">{{ cap(s.verbose_name) }}</a>
        <span class="sep">/</span>
        <span>{{ leaf }}</span>
      </nav>

      <header class="list-header">
        <h2>{{ leaf }} {{ cap(s.verbose_name) }}</h2>
        <div class="list-actions">
          @if (s.tree && !isNew) {
            <a class="btn secondary" [routerLink]="['/', slug, pk, 'tree']" [queryParams]="{ ret: here() }">{{ t('hierarchy') }}</a>
          }
          <button type="button" class="btn secondary" (click)="back()">{{ t('backArrow') }}</button>
        </div>
      </header>

      <!-- custom object actions below the title, wrapping onto new rows -->
      @if (!isNew && detailActions().length) {
        <div class="detail-toolbar">
          @for (a of detailActions(); track a.key) {
            <button type="button" class="btn secondary" [disabled]="runningAction()" (click)="runDetailAction(a)">{{ cap(a.label) }}</button>
          }
        </div>
      }

      @if (errors()['__all__']; as nonField) {
        <div class="errors">{{ nonField.join(' ') }}</div>
      }

      <form [formGroup]="form" (ngSubmit)="save()">
        @for (g of fieldsetGroups(); track $index) {
          <fieldset class="form-section" [class.titled]="!!g.title" [class.collapsed]="isCollapsed(g, $index)">
            @if (g.title || g.collapsible) {
              <legend
                class="section-title"
                [class.toggle]="g.collapsible"
                (click)="g.collapsible && toggleGroup(g, $index)"
              >
                @if (g.collapsible) { <span class="section-caret">{{ isCollapsed(g, $index) ? '▸' : '▾' }}</span> }
                {{ g.title }}
              </legend>
            }
            @if (g.description) { <p class="section-desc">{{ g.description }}</p> }
            @if (!isCollapsed(g, $index)) {
              @for (field of g.fields; track field.name) {
                @if (field.type === 'compact_tree') {
                  <div class="field compact-tree-field">
                    <span class="field-label">{{ field.label }}</span>
                    @if (field.help_text) { <small class="help">{{ field.help_text }}</small> }
                    @if (compactTreeRef(field); as ref) {
                      <theia-compact-tree [modelKey]="ref.key" [pk]="ref.pk" [scope]="'self'" />
                    } @else {
                      <p class="section-desc">{{ t('noDescendants') }}</p>
                    }
                  </div>
                } @else {
                  <theia-field [field]="field" [control]="controlFor(field.name)" [initial]="relationInitial(field)" [form]="form" />
                  @if (errors()[field.name]; as fieldErrors) {
                    <div class="errors">{{ fieldErrors.join(' ') }}</div>
                  }
                }
              }
            }
          </fieldset>
        }

        @if (!viewMode) {
          @for (inl of inlines(); track inl.key) {
            <theia-inline-editor [inline]="inl" [initialRows]="inlineRows(inl)" />
          }
        }

        <div class="actions">
          @if (viewMode) {
            <div class="actions-left">
              @if (s.perms.change) {
                <button type="button" class="btn" (click)="editThis()">{{ t('edit') }}</button>
              }
              <button type="button" (click)="back()">{{ t('back') }}</button>
            </div>
          } @else {
            <div class="actions-left">
              <button type="submit" class="btn" [disabled]="saving()">{{ t('save') }}</button>
              <button type="button" class="btn secondary" [disabled]="saving()" (click)="save(true)">
                {{ t('saveContinue') }}
              </button>
              <button type="button" (click)="back()">{{ t('cancel') }}</button>
            </div>
            @if (!isNew && s.perms.delete) {
              <button type="button" class="btn danger" (click)="remove()">{{ t('delete') }}</button>
            }
          }
        </div>
      </form>

      @if (s.tree && !isNew) {
        <section class="detail-hierarchy">
          <h3
            class="section-title toggle"
            (click)="showHierarchy.set(!showHierarchy())"
          >
            <span class="section-caret">{{ showHierarchy() ? '▾' : '▸' }}</span>
            {{ t('hierarchy') }}
          </h3>
          @if (showHierarchy()) {
            <theia-compact-tree [modelKey]="modelKey" [pk]="pk" />
          }
        </section>
      }

      @if (confirmingDelete()) {
        <theia-confirm-dialog
          [title]="t('deleteRecordTitle')"
          [message]="t('deleteRecordMsg')"
          [confirmLabel]="t('delete')"
          [cancelLabel]="t('cancel')"
          [danger]="true"
          (confirmed)="doRemove()"
          (cancelled)="confirmingDelete.set(false)"
        />
      }

      <!-- detail (object) action with a parameter form, run on this record -->
      @if (activeDetailAction(); as a) {
        <theia-action-dialog
          [action]="a"
          [ids]="[pk]"
          (done)="onDetailActionDone()"
          (closed)="activeDetailAction.set(null)"
        />
      }
      <!-- dangerous, no-parameter detail action: confirm then run -->
      @if (pendingDetailAction(); as a) {
        <theia-confirm-dialog
          [title]="cap(a.label)"
          [message]="cap(a.label) + '?'"
          [confirmLabel]="cap(a.label)"
          [cancelLabel]="t('cancel')"
          [danger]="true"
          (confirmed)="execDetailAction(a)"
          (cancelled)="pendingDetailAction.set(null)"
        />
      }
    }
  `,
})
export class ModelDetailComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private viewService = inject(ViewService);
  private toast = inject(ToastService);
  private i18n = inject(I18nService);
  protected t = this.i18n.t;
  // In-flight loads, cancelled on navigation so a slow record's late response
  // can't land on a record you've already navigated away from.
  private schemaSub?: Subscription;
  private retrieveSub?: Subscription;

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
  /** Whether the compact hierarchy section is expanded (loads on first open). */
  showHierarchy = signal(false);
  loading = signal(false);
  // Object actions run on this single record (from buttons in the header).
  activeDetailAction = signal<ActionSpec | null>(null);   // parameterized -> dialog
  pendingDetailAction = signal<ActionSpec | null>(null);  // dangerous, no fields -> confirm
  runningAction = signal(false);
  @ViewChildren(InlineEditorComponent) private inlineEditors!: QueryList<InlineEditorComponent>;

  inlines(): InlineConfig[] {
    return this.schema()?.inlines ?? [];
  }

  /** Object actions for this model, gated on their required permission. */
  detailActions(): ActionSpec[] {
    const perms = this.schema()?.perms;
    return (this.schema()?.actions ?? []).filter(
      (a) => a.detail && (!a.requires || !!perms?.[a.requires as keyof typeof perms]),
    );
  }

  /** Run an object action on this record: parameterized ones pop a form,
   *  dangerous ones confirm, the rest run immediately. */
  runDetailAction(a: ActionSpec): void {
    if (a.fields?.length) {
      this.activeDetailAction.set(a);
    } else if (a.dangerous) {
      this.pendingDetailAction.set(a);
    } else {
      this.execDetailAction(a);
    }
  }

  /** POST the (no-form) action over just this record, then reload it. */
  execDetailAction(a: ActionSpec): void {
    this.pendingDetailAction.set(null);
    this.runningAction.set(true);
    this.api.runAction(a.endpoint, { ids: [this.pk] }).subscribe({
      next: () => {
        this.runningAction.set(false);
        this.toast.success(this.t('actionDoneToast', { action: cap(a.label) }));
        this.reload();
      },
      error: () => {
        this.runningAction.set(false);
        this.toast.error(this.t('actionFailed'));
      },
    });
  }

  /** A parameterized object action finished (the dialog already toasted). */
  onDetailActionDone(): void {
    this.activeDetailAction.set(null);
    this.reload();
  }

  private reload(): void {
    if (!this.isNew) {
      this.api.retrieve(this.modelKey, this.pk).subscribe((data) => this.populate(data));
    }
  }

  /** Existing child rows for an inline, from the loaded record's `inlines` blob. */
  inlineRows(inline: InlineConfig): Record<string, unknown>[] {
    const all = (this.record()?.['inlines'] ?? {}) as Record<string, Record<string, unknown>[]>;
    return all[inline.key] ?? [];
  }

  ngOnInit(): void {
    this.route.paramMap.subscribe((params) => {
      this.slug = params.get('modelKey') ?? '';
      this.modelKey = slugToKey(this.slug);
      this.pk = params.get('pk') ?? 'new';
      this.isNew = this.pk === 'new';
      this.loading.set(true);
      // Cancel a pending load from the previous record/model.
      this.schemaSub?.unsubscribe();
      this.retrieveSub?.unsubscribe();
      this.schemaSub = this.api.getSchema(this.modelKey).subscribe({
        next: (s) => {
          this.schema.set(s);
          this.buildForm(s);
          if (this.isNew) {
            this.applyMode();
            this.loading.set(false);
          } else {
            this.retrieveSub = this.api.retrieve(this.modelKey, this.pk).subscribe({
              next: (data) => {
                this.populate(data);
                this.loading.set(false);
              },
              error: () => this.loading.set(false),
            });
          }
        },
        error: () => this.loading.set(false),
      });
    });

    // ?mode=view toggles read-only without reloading (e.g. Edit -> back to view).
    this.route.queryParamMap.subscribe((q) => {
      this.viewMode = q.get('mode') === 'view';
      this.applyMode();
    });
  }

  ngOnDestroy(): void {
    this.schemaSub?.unsubscribe();
    this.retrieveSub?.unsubscribe();
  }

  get leaf(): string {
    return this.isNew ? this.t('leafNew') : this.viewMode ? this.t('leafView') : this.t('edit');
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

  /** Form fields grouped into sections per ``fieldsets``. With no fieldsets, a
   *  single untitled group holds every field. Any form field not named in a
   *  fieldset (e.g. a required field on create) is appended in a trailing group
   *  so it's never hidden. */
  fieldsetGroups(): FieldsetGroup[] {
    const all = this.formFields();
    const fs = this.schema()?.fieldsets;
    if (!fs || !fs.length) {
      return [{ title: null, description: null, collapsible: false, fields: all }];
    }
    const byName = new Map(all.map((f) => [f.name, f]));
    const used = new Set<string>();
    const groups: FieldsetGroup[] = fs.map((g) => {
      const fields = g.fields
        .map((n) => byName.get(n))
        .filter((f): f is FieldSpec => !!f);
      fields.forEach((f) => used.add(f.name));
      return {
        title: g.title,
        description: g.description ?? null,
        collapsible: !!g.collapsible,
        fields,
      };
    });
    const rest = all.filter((f) => !used.has(f.name));
    if (rest.length) {
      groups.push({ title: null, description: null, collapsible: false, fields: rest });
    }
    return groups.filter((g) => g.fields.length);
  }

  /** Collapsible sections start collapsed; track which the user has expanded. */
  private expanded = signal<Set<string>>(new Set());
  private groupKey(g: FieldsetGroup, i: number): string {
    return g.title ?? `__${i}`;
  }
  isCollapsed(g: FieldsetGroup, i: number): boolean {
    return g.collapsible && !this.expanded().has(this.groupKey(g, i));
  }
  toggleGroup(g: FieldsetGroup, i: number): void {
    const key = this.groupKey(g, i);
    const next = new Set(this.expanded());
    next.has(key) ? next.delete(key) : next.add(key);
    this.expanded.set(next);
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

  /** The { key, pk } root the backend resolved for a compact_tree field on this
   *  record (null hides it). pk is stringified for the routerLink/endpoint. */
  compactTreeRef(field: FieldSpec): { key: string; pk: string } | null {
    const ref = this.record()?.[field.name] as { key: string; pk: number | string } | null;
    return ref ? { key: ref.key, pk: String(ref.pk) } : null;
  }

  private buildForm(s: ModelSchema): void {
    const group: Record<string, FormControl> = {};
    for (const field of s.fields) {
      // compact_tree is a synthetic display element, not a form control — it
      // must stay out of the FormGroup (and thus the save payload).
      if (field.type === 'compact_tree') {
        continue;
      }
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
    const body: Record<string, unknown> = { ...this.form.value };
    // Collect related child rows from each inline editor.
    if (this.inlineEditors?.length) {
      const inlines: Record<string, unknown> = {};
      for (const editor of this.inlineEditors) {
        inlines[editor.inline.key] = editor.getPayload();
      }
      body['inlines'] = inlines;
    }
    const obs = this.isNew
      ? this.api.create(this.modelKey, body)
      : this.api.update(this.modelKey, this.pk, body);
    obs.subscribe({
      next: (record) => {
        this.saving.set(false);
        this.toast.success(this.isNew ? this.t('created') : this.t('saved'));
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
        this.errors.set(err?.error?.errors ?? { __all__: [this.t('saveFailed')] });
        this.toast.error(this.t('couldNotSave'));
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
        this.toast.success(this.t('deleted'));
        this.refreshViewsIfNeeded();
        this.back();
      },
      error: () => this.toast.error(this.t('couldNotDelete')),
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
