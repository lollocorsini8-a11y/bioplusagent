import type { DailyHealthSummary, TimedValue } from './types';

export function getDateWindow(days: number) {
  const end = new Date();
  const start = new Date(end);
  start.setDate(start.getDate() - days);
  return { start, end };
}

export function toLocalDateKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function latestValuesPerDay(values: TimedValue[]) {
  const latest = new Map<string, { timestamp: number; value: number }>();
  for (const sample of values) {
    const date = toLocalDateKey(sample.date);
    const current = latest.get(date);
    const timestamp = sample.date.getTime();
    if (current === undefined || timestamp >= current.timestamp) {
      latest.set(date, { timestamp, value: sample.value });
    }
  }
  return new Map(
    Array.from(latest, ([date, sample]) => [date, sample.value] as const),
  );
}

export function longestValuesPerDay(values: TimedValue[]) {
  const longest = new Map<string, number>();
  for (const sample of values) {
    const date = toLocalDateKey(sample.date);
    longest.set(date, Math.max(longest.get(date) ?? 0, sample.value));
  }
  return longest;
}

export function groupSleepIntervals(
  intervals: { start: Date; end: Date }[],
): TimedValue[] {
  const sorted = intervals
    .filter((interval) => interval.end.getTime() > interval.start.getTime())
    .sort((a, b) => a.start.getTime() - b.start.getTime());
  const sessions: TimedValue[] = [];
  let sessionEnd: Date | undefined;
  let sessionMinutes = 0;

  for (const interval of sorted) {
    const start = interval.start.getTime();
    const end = interval.end.getTime();
    if (!sessionEnd || start - sessionEnd.getTime() > 3 * 60 * 60 * 1000) {
      if (sessionEnd) sessions.push({ date: sessionEnd, value: sessionMinutes });
      sessionEnd = interval.end;
      sessionMinutes = (end - start) / 60_000;
      continue;
    }

    if (end > sessionEnd.getTime()) {
      sessionMinutes += (end - Math.max(start, sessionEnd.getTime())) / 60_000;
      sessionEnd = interval.end;
    }
  }

  if (sessionEnd) sessions.push({ date: sessionEnd, value: sessionMinutes });
  return sessions;
}

export function createSummaries(
  metrics: {
    hrv?: TimedValue[];
    restingHeartRate?: TimedValue[];
    oxygenSaturation?: TimedValue[];
    sleepMinutes?: TimedValue[];
  },
): DailyHealthSummary[] {
  const hrv = latestValuesPerDay(metrics.hrv ?? []);
  const restingHeartRate = latestValuesPerDay(metrics.restingHeartRate ?? []);
  const oxygenSaturation = latestValuesPerDay(metrics.oxygenSaturation ?? []);
  const sleepMinutes = longestValuesPerDay(metrics.sleepMinutes ?? []);

  const dates = new Set([
    ...hrv.keys(),
    ...restingHeartRate.keys(),
    ...oxygenSaturation.keys(),
    ...sleepMinutes.keys(),
  ]);

  return Array.from(dates, (date) => {
    const hrvValue = hrv.get(date);
    const restingHeartRateValue = restingHeartRate.get(date);
    const oxygenSaturationValue = oxygenSaturation.get(date);
    const sleepMinutesValue = sleepMinutes.get(date);

    return {
      date,
      ...(hrvValue !== undefined ? { hrvRmssdMs: round(hrvValue, 1) } : {}),
      ...(restingHeartRateValue !== undefined
        ? { restingHeartRateBpm: round(restingHeartRateValue, 1) }
        : {}),
      ...(oxygenSaturationValue !== undefined
        ? { oxygenSaturationPercent: round(oxygenSaturationValue, 1) }
        : {}),
      ...(sleepMinutesValue !== undefined
        ? { sleepHours: round(sleepMinutesValue / 60, 1) }
        : {}),
    };
  }).sort((a, b) => a.date.localeCompare(b.date));
}

function round(value: number, decimals: number) {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}
