# Security Incident Response (Network Elements)

## Detection
Watch for unexpected configuration changes on network elements outside a
scheduled maintenance window, unusual authentication attempts against
element-management systems, or traffic patterns inconsistent with normal
subscriber behavior (for example, a sudden signaling flood from a single
cell that resembles a denial-of-service pattern rather than organic load).

## Immediate Actions
1. Isolate the affected element from the management network if active
   compromise is suspected, while preserving logs for forensics.
2. Rotate credentials for any account associated with the unexpected
   configuration change.
3. Cross-check the change against the approved change-management calendar —
   many "incidents" turn out to be an undocumented but legitimate change.
4. Notify the security operations center immediately; do not attempt to
   remediate a suspected compromise unilaterally from the NOC.

## Escalation
Any confirmed unauthorized configuration change or credential compromise is
escalated to the security operations center and incident commander
immediately, regardless of time of day.

## Root Cause Checklist
- Was the change made through an approved management interface or an
  unexpected access path?
- Does the account that made the change have a legitimate reason to touch
  this element?
- Are there similar unexplained changes on other elements in the same
  management domain in the last 24 hours?
