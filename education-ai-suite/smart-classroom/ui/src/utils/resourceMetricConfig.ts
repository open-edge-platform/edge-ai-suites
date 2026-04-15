/**
 * Maximum duration for resource metric polling.
 * After this duration, polling is automatically paused and the user is prompted to resume.
 * Default: 45 minutes (in milliseconds)
 */
export const RESOURCE_METRIC_DURATION_MIN = 45;
export const RESOURCE_METRIC_DURATION_MS = RESOURCE_METRIC_DURATION_MIN * 60 * 1000;
