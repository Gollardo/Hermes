import { EntityOption } from './entity-combobox';

export interface CategoryComboboxItem {
  id: string;
  name: string;
  archived: boolean;
  parent_id?: string | null;
}

interface CategoryComboboxOptions {
  allCategories?: CategoryComboboxItem[];
  archivedLabel?: string;
  disabled?: (category: CategoryComboboxItem) => boolean;
}

export function categoryComboboxOptions(
  categories: CategoryComboboxItem[],
  options: CategoryComboboxOptions = {},
): EntityOption[] {
  const allCategories = options.allCategories ?? categories;
  const byId = new Map(allCategories.map((category) => [category.id, category]));
  const selectedIds = new Set(categories.map((category) => category.id));
  const ordered = [
    ...categories.filter((category) => !category.parent_id),
    ...categories.filter((category) => category.parent_id && !selectedIds.has(category.parent_id)),
  ].flatMap((category) => [
    category,
    ...categories.filter((child) => child.parent_id === category.id),
  ]);

  return ordered.map((category) => {
    const parent = category.parent_id ? byId.get(category.parent_id) : undefined;
    const path = parent ? `${parent.name} → ${category.name}` : category.name;
    const archived = category.archived && options.archivedLabel ? options.archivedLabel : '';
    return {
      id: category.id,
      label: category.name,
      detail: parent ? `${path}${archived ? ` · ${archived}` : ''}` : archived || undefined,
      searchText: parent ? `${parent.name} ${category.name}` : category.name,
      disabled: options.disabled?.(category),
      level: parent ? 1 : 0,
    };
  });
}
