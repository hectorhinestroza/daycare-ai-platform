/**
 * Parse a datetime string from the API as UTC.
 *
 * The backend stores naive UTC datetimes (no timezone suffix). Without the
 * trailing 'Z', JavaScript's Date constructor treats the string as local time,
 * which makes every timestamp wrong by the UTC offset. This helper appends 'Z'
 * when no timezone info is present so the browser always interprets it as UTC
 * and converts correctly to local time for display.
 */
export function fromApi(dateStr) {
  if (!dateStr) return null;
  if (dateStr.endsWith('Z') || dateStr.match(/[+-]\d{2}:?\d{2}$/)) {
    return new Date(dateStr);
  }
  return new Date(dateStr + 'Z');
}
