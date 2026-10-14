/** Shared ED care-sequence helpers for the live queue and patient record. */

export const DISPOSITION_STATUSES = ['referred', 'discharged']

export const DISPOSITION_LABELS = {
  referred: 'Referred',
  discharged: 'Discharged',
}

/**
 * Resolve the current step in:
 * Vitals → Scan → In Queue → Seen → Observation → Completed (Discharged / Referred)
 */
export function getCareSequence(patient, latestAssessment) {
  const assessment = latestAssessment || patient?.latest_assessment
  const hasVitals = !!(
    patient?.latest_vitals ||
    (Array.isArray(patient?.vital_readings) && patient.vital_readings.length > 0)
  )
  const tests = assessment?.ai_decision_support?.preliminary_tests
  const scanRequired = Array.isArray(tests) && tests.length > 0
  const underScan = !!patient?.under_scan
  const scanDone = !!(patient?.scan_reports && String(patient.scan_reports).trim())
  const status = patient?.status || 'waiting'
  const isDone = DISPOSITION_STATUSES.includes(status)
  const isInProgress = status === 'in_progress'
  const isAdmitted = status === 'admitted'
  const isWaiting = status === 'waiting'

  let activeIndex = 0
  if (isDone) {
    activeIndex = 5
  } else if (isAdmitted) {
    activeIndex = 4
  } else if (isInProgress) {
    activeIndex = 3
  } else if (!hasVitals) {
    activeIndex = 0
  } else if (underScan || (scanRequired && !scanDone)) {
    activeIndex = 1
  } else {
    activeIndex = 2
  }

  let scanDesc = 'Not required'
  if (underScan) scanDesc = 'In progress'
  else if (scanDone) scanDesc = 'Complete'
  else if (scanRequired) scanDesc = 'Ordered'

  const lastLabel = isDone ? DISPOSITION_LABELS[status] : 'Completed'

  return {
    activeIndex,
    hasVitals,
    scanRequired,
    underScan,
    scanDone,
    isDone,
    isInProgress,
    isAdmitted,
    isWaiting,
    dispositionKey: isDone ? status : null,
    lastLabel,
    steps: [
      { key: 'vitals', label: 'Vitals', desc: hasVitals ? 'Recorded' : 'Pending' },
      { key: 'scan', label: 'Scan', desc: scanDesc },
      {
        key: 'in_queue',
        label: 'In Queue',
        desc: activeIndex === 2 ? 'Waiting' : activeIndex > 2 ? 'Complete' : 'Pending',
      },
      {
        key: 'seen',
        label: 'Seen',
        desc: isInProgress ? 'In progress' : activeIndex > 3 ? 'Complete' : 'Pending',
      },
      {
        key: 'admitted',
        label: 'Observation',
        desc: isAdmitted ? 'Under observation' : activeIndex > 4 ? 'Complete' : 'Pending',
      },
      {
        key: 'disposition',
        label: lastLabel,
        desc: isDone ? DISPOSITION_LABELS[status] : 'Discharged / Referred',
      },
    ],
  }
}
