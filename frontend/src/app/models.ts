/** TypeScript mirror of the IR produced by theia_ng.introspection.builder. */

export type FieldType =
  | 'string' | 'text' | 'integer' | 'decimal' | 'boolean'
  | 'date' | 'datetime' | 'time' | 'email' | 'url' | 'uuid'
  | 'json' | 'choice' | 'fk' | 'm2m' | 'file' | 'image';

export interface Perms {
  view: boolean;
  add: boolean;
  change: boolean;
  delete: boolean;
}

export interface RegistryModel {
  key: string;
  verbose_name: string;
  verbose_name_plural: string;
  app_label: string;
  app_verbose_name: string;
  perms: Perms;
}

/** An admin-defined sidebar view: a named subset of model keys (already
 *  intersected server-side with what the user may see), plus optional per-model
 *  visible-field lists ({model key -> field names}; missing/empty = all). */
export interface MenuView {
  name: string;
  models: string[];
  fields?: Record<string, string[]>;
}

export interface Registry {
  schema_version: string;
  site: { title: string; version?: string };
  models: RegistryModel[];
  views: MenuView[];
}

export interface Choice {
  value: string | number;
  label: string;
}

export interface Relation {
  kind: 'fk' | 'm2m';
  target: string;
  display_field: string;
  options_endpoint: string;
  searchable: boolean;
  /** Whether the target model is registered with Theia (has picker/CRUD endpoints). */
  registered: boolean;
  /** raw_id_fields: render as a plain id input instead of a picker. */
  raw?: boolean;
  /** Sibling field names whose values narrow this relation's options. */
  depends_on?: string[];
}

export interface FieldSpec {
  name: string;
  label: string;
  type: FieldType;
  required: boolean;
  editable: boolean;
  read_only: boolean;
  help_text: string;
  default: unknown;
  widget: string | null;
  choices?: Choice[];
  relation?: Relation;
  constraints?: { max_length?: number };
  /** model_field_select widget: {model key -> {label, fields}} of selectable fields. */
  field_choices?: Record<string, { label: string; fields: Choice[] }>;
  /** model_field_select widget: sibling field name holding the selected model keys. */
  models_field?: string;
}

/** A custom list filter (theia_ng.ListFilter): a labelled choice dropdown whose
 *  value is sent as `param` and applied server-side. */
export interface CustomFilter {
  param: string;
  label: string;
  choices: Choice[];
}

export interface ListConfig {
  display: string[];
  /** Column name -> header label (fields humanized, computed columns' short_description). */
  labels: Record<string, string>;
  filters: string[];
  custom_filters?: CustomFilter[];
  search_fields: string[];
  ordering: string[];
  per_page: number;
  /** Row checkboxes + bulk actions are available for this model. */
  selectable?: boolean;
}

/** A custom action. Parameterized actions carry form ``fields``; ``selection``
 *  says whether it needs selected rows ('required'), may use them ('optional'),
 *  or ignores them ('none', e.g. a broadcast). */
export interface ActionSpec {
  key: string;
  label: string;
  endpoint: string;
  selection: 'none' | 'optional' | 'required';
  fields: FieldSpec[];
  /** Needs a confirm step (e.g. delete). */
  dangerous?: boolean;
  /** Permission the action needs; the SPA hides it unless perms[requires] is true. */
  requires?: keyof Perms;
}

export interface ModelSchema {
  schema_version: string;
  key: string;
  verbose_name: string;
  perms: Perms;
  endpoints: { list: string; detail: string };
  list: ListConfig;
  fields: FieldSpec[];
  actions: ActionSpec[];
  /** Whether this model participates in a hierarchy tree (offers a Hierarchy view). */
  tree?: boolean;
}

/** One child relation of a tree node: its target + a count (records load lazily). */
export interface ChildGroup {
  /** Reverse accessor name on the parent (e.g. "space_set"). */
  accessor: string;
  /** Child model key (app.model). */
  key: string;
  /** Plural verbose name, e.g. "spaces". */
  label: string;
  count: number;
  searchable: boolean;
}

/** A node in the hierarchy tree (theia_ng.introspection.tree). Children are not
 *  inlined — each child group loads on demand via the tree-children endpoint. */
export interface TreeNode {
  key: string;
  /** Model verbose_name, e.g. "house". */
  model_label: string;
  pk: number | string;
  /** Human label for the record (the target's display()). */
  label: string;
  perms: { view: boolean; change: boolean; delete: boolean };
  /** True for the record the tree was opened from. */
  is_current: boolean;
  child_groups: ChildGroup[];
}

export interface TreeResponse {
  schema_version: string;
  root: TreeNode;
  /** The lineage from root → opened record ({key, pk} each), for auto-expansion. */
  path: { key: string; pk: number | string }[];
  current: { key: string; pk: number | string };
}

/** A page of one child group (searched + paginated). */
export interface TreeChildrenResponse {
  key: string;
  accessor: string;
  count: number;
  page: number;
  num_pages: number;
  results: TreeNode[];
}

/** Relation values serialize as { id, label }; lists for m2m. */
export interface RelationValue {
  id: number | string;
  label: string;
}

export interface ListResponse {
  count: number;
  page: number;
  num_pages: number;
  results: Record<string, unknown>[];
}

export interface AuthState {
  authenticated: boolean;
  username: string | null;
  /** First name for the greeting, if the user model has one. */
  first_name?: string | null;
  /** Superusers can view everyone's audit log, not just their own. */
  is_superuser?: boolean;
  can_access: boolean;
}

/** One audit-log row (theia_ng.models.LogEntry). */
export interface LogEntry {
  id: number;
  timestamp: string;
  username: string;
  action: 'create' | 'update' | 'delete' | 'action';
  model_key: string;
  model_label: string;
  object_pk: string;
  object_repr: string;
  /** Field diff {field: [old, new]} for create/update, or action metadata. */
  changes: Record<string, unknown>;
}

export interface LogResponse {
  count: number;
  page: number;
  num_pages: number;
  results: LogEntry[];
  is_superuser: boolean;
}
