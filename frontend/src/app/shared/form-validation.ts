import { AbstractControl, FormGroup } from '@angular/forms';

export function revealInvalidFields(form: FormGroup, root: ParentNode = document): boolean {
  form.markAllAsTouched();
  if (form.valid) return false;
  queueMicrotask(() => {
    const firstInvalidName = findFirstInvalidControl(form);
    const target = firstInvalidName
      ? root.querySelector<HTMLElement>(
          `[formControlName="${firstInvalidName.replaceAll('"', '\\"')}"]`,
        )
      : root.querySelector<HTMLElement>('[aria-invalid="true"], :invalid');
    target?.focus();
  });
  return true;
}

function findFirstInvalidControl(control: AbstractControl, path = ''): string | null {
  if (control instanceof FormGroup) {
    for (const [name, child] of Object.entries(control.controls)) {
      const invalid = findFirstInvalidControl(child, name);
      if (invalid) return invalid;
    }
    return null;
  }
  return control.invalid ? path : null;
}
