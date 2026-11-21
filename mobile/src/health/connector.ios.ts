import {
  CategoryValueSleepAnalysis,
  isHealthDataAvailableAsync,
  queryCategorySamples,
  queryQuantitySamples,
  requestAuthorization,
} from '@kingstinct/react-native-healthkit';
import { createSummaries, getDateWindow, groupSleepIntervals } from './summary';
import type { TimedValue } from './types';

const READ_TYPES = [
  'HKQuantityTypeIdentifierHeartRateVariabilityRMSSD',
  'HKQuantityTypeIdentifierRestingHeartRate',
  'HKQuantityTypeIdentifierOxygenSaturation',
  'HKCategoryTypeIdentifierSleepAnalysis',
] as const;

export async function connectAndReadHealthData() {
  if (!(await isHealthDataAvailableAsync())) {
    throw new Error('Apple Health non è disponibile su questo dispositivo.');
  }

  const authorized = await requestAuthorization({ toRead: READ_TYPES });
  if (!authorized) {
    throw new Error('Apple Health non ha completato la richiesta di autorizzazione.');
  }

  const { start, end } = getDateWindow(28);
  const filter = { date: { startDate: start, endDate: end } };
  const [hrvSamples, restingHeartRateSamples, oxygenSamples, sleepSamples] =
    await Promise.all([
      queryQuantitySamples('HKQuantityTypeIdentifierHeartRateVariabilityRMSSD', {
        filter,
        limit: -1,
        ascending: false,
        unit: 'ms',
      }),
      queryQuantitySamples('HKQuantityTypeIdentifierRestingHeartRate', {
        filter,
        limit: -1,
        ascending: false,
        unit: 'count/min',
      }),
      queryQuantitySamples('HKQuantityTypeIdentifierOxygenSaturation', {
        filter,
        limit: -1,
        ascending: false,
        unit: '%',
      }),
      queryCategorySamples('HKCategoryTypeIdentifierSleepAnalysis', {
        filter,
        limit: -1,
        ascending: false,
      }),
    ]);

  const hrv: TimedValue[] = hrvSamples.map((sample) => ({
    date: sample.endDate,
    value: sample.quantity,
  }));
  const restingHeartRate: TimedValue[] = restingHeartRateSamples.map((sample) => ({
    date: sample.endDate,
    value: sample.quantity,
  }));
  const oxygenSaturation: TimedValue[] = oxygenSamples.map((sample) => ({
    date: sample.endDate,
    value: sample.quantity <= 1 ? sample.quantity * 100 : sample.quantity,
  }));
  const sleepMinutes = groupSleepIntervals(sleepSamples
    .filter((sample) =>
      [
        CategoryValueSleepAnalysis.asleepUnspecified,
        CategoryValueSleepAnalysis.asleepCore,
        CategoryValueSleepAnalysis.asleepDeep,
        CategoryValueSleepAnalysis.asleepREM,
      ].includes(sample.value),
    )
    .map((sample) => ({ start: sample.startDate, end: sample.endDate })));

  return createSummaries({ hrv, restingHeartRate, oxygenSaturation, sleepMinutes });
}
