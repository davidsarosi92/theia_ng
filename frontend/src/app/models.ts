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

export interface Registry {
  schema_version: string;
  site: { title: string };
  models: RegistryModel[];
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
}

export interface ListConfig {
  display: string[];
  filters: string[];
  search_fields: string[];
  ordering: string[];
  per_page: number;
}

export interface ModelSchema {
  schema_version: string;
  key: string;
  verbose_name: string;
  perms: Perms;
  endpoints: { list: string; detail: string };
  list: ListConfig;
  fields: FieldSpec[];
  actions: { key: string; label: string; endpoint: string }[];
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
  can_access: boolean;
}
