# Enterprise Customer SLA Escalation

## Detection
An SLA-relevant event is any outage, sustained congestion, or latency
degradation on a cell or transport path flagged as serving a priority
enterprise customer. These sites are tagged in the customer topology
mapping and should always be checked first when triaging any alarm.

## Immediate Actions
1. Confirm the customer's contracted SLA thresholds (availability, latency,
   or throughput) before determining whether the event is reportable.
2. Open a proactive notification to the account team as soon as an SLA
   threshold is breached — do not wait for the customer to report it.
3. Prioritize remediation actions (load-balancing, failover, dispatch) for
   SLA-tagged sites ahead of non-tagged sites of similar severity.
4. Track time-to-restore separately for SLA-tagged incidents; this feeds
   the monthly SLA compliance report.

## Escalation
Escalate directly to the account management team, in parallel with normal
technical escalation, for any SLA breach projected to exceed the customer's
contracted maximum outage window.

## Root Cause Checklist
- Was the SLA tag on the affected site current, or has the customer's
  footprint changed recently?
- Does the root cause qualify for an SLA credit under the contract's
  force-majeure or planned-maintenance exclusions?
- Was the account team notified within the internal SLA-breach notification
  window (typically 15 minutes)?
