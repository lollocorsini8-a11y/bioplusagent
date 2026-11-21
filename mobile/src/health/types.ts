export interface DailyHealthSummary {
  date: string;
  hrvRmssdMs?: number;
  restingHeartRateBpm?: number;
  oxygenSaturationPercent?: number;
  sleepHours?: number;
}

export interface TimedValue {
  date: Date;
  value: number;
}
