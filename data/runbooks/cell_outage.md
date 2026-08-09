# Cell Outage Response

## Detection
A cell outage presents as a critical alarm with zero throughput and zero
active subscribers reported from a single cell, while neighboring cells on
different transport paths remain healthy. This distinguishes it from a fiber
cut, which takes out an entire ring at once.

## Immediate Actions
1. Attempt a remote restart of the affected baseband/radio unit.
2. If remote restart fails twice, dispatch a field technician and open a
   hardware replacement ticket in parallel rather than waiting for on-site
   diagnosis first.
3. Activate any overlapping macro or small-cell coverage to absorb displaced
   subscribers while the outage is open.
4. Log estimated subscriber impact (approximate active users at time of
   outage) for the post-incident report.

## Escalation
Escalate to Tier 2 RAN engineering if the remote restart fails. Escalate to
the incident commander if the outage exceeds 15 minutes in a dense urban
cell or 60 minutes anywhere else.

## Root Cause Checklist
- Was there a recent software push to this cell or its controller?
- Check power alarms — a brief power fluctuation immediately before the
  outage often points to a power root cause rather than hardware failure.
- Confirm whether the same hardware unit has had repeat outages in the last
  30 days, which would indicate a unit needing replacement rather than reset.
