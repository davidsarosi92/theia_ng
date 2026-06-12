import { RegistryModel } from './models';

export interface AppGroup {
  appLabel: string;
  appName: string;
  models: RegistryModel[];
}

/** Group models by Django app, apps sorted by name and models by name within. */
export function groupByApp(models: RegistryModel[]): AppGroup[] {
  const map = new Map<string, AppGroup>();
  for (const m of models) {
    let group = map.get(m.app_label);
    if (!group) {
      group = { appLabel: m.app_label, appName: m.app_verbose_name, models: [] };
      map.set(m.app_label, group);
    }
    group.models.push(m);
  }
  const groups = [...map.values()];
  groups.sort((a, b) => a.appName.localeCompare(b.appName));
  for (const group of groups) {
    group.models.sort((a, b) => a.verbose_name.localeCompare(b.verbose_name));
  }
  return groups;
}
