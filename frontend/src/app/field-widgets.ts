/** Pure type -> widget mapping for the 16 IR field types (unit-testable). */
import { FieldType } from './models';

export type WidgetKind = 'textarea' | 'checkbox' | 'select' | 'relation' | 'input';

export function widgetFor(type: FieldType): WidgetKind {
  switch (type) {
    case 'text':
    case 'json':
      return 'textarea';
    case 'boolean':
      return 'checkbox';
    case 'choice':
      return 'select';
    case 'fk':
    case 'm2m':
      return 'relation';
    default:
      return 'input';
  }
}

export function inputTypeFor(type: FieldType): string {
  switch (type) {
    case 'integer':
    case 'decimal':
      return 'number';
    case 'date':
      return 'date';
    case 'datetime':
      return 'datetime-local';
    case 'time':
      return 'time';
    case 'email':
      return 'email';
    case 'url':
      return 'url';
    default:
      return 'text';
  }
}
