import { locale } from '../i18n/i18n';
import { Pipe, PipeTransform } from '@angular/core';

/** Formats an ISO calendar date without timezone conversion. */
export function formatTextDate(value: string | null | undefined): string {
  if (!value) return '—';
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value;
  const month =
    new Intl.DateTimeFormat(locale(), { month: 'long', day: 'numeric', timeZone: 'UTC' })
      .formatToParts(new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]))))
      .find((part) => part.type === 'month')?.value ?? '';
  return `${Number(match[3])} ${month} ${match[1]}`;
}

export function formatTextTimestamp(value: string): string {
  const instant = new Date(value);
  if (Number.isNaN(instant.getTime())) return value;
  const parts = new Intl.DateTimeFormat(locale(), {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(instant);
  const part = (type: Intl.DateTimeFormatPartTypes): string =>
    parts.find((item) => item.type === type)?.value ?? '';
  return `${part('day')} ${part('month')} ${part('year')}, ${part('hour')}:${part('minute')}`;
}

@Pipe({ name: 'textDate', standalone: true, pure: false })
export class DateTextPipe implements PipeTransform {
  transform(value: string | null | undefined): string {
    return formatTextDate(value);
  }
}
