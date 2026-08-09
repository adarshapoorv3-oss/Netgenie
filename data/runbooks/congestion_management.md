# Congestion Management

## Detection
Sustained congestion is indicated by congestion percentage trending above 60%
for more than three consecutive measurement windows on the same cell, usually
accompanied by a gradual (not sudden) rise in dropped-call rate and latency.
A gradual multi-day upward trend, rather than a step change, is the key signal
that distinguishes congestion from a hardware or transport fault.

## Immediate Actions
1. Identify whether the congestion is time-of-day driven (recurring at the
   same hours) or a sustained new baseline.
2. For time-of-day congestion, enable load-balancing to neighboring cells or
   activate any available carrier aggregation / additional spectrum layer.
3. For a sustained new baseline, check for a nearby event, new venue, or
   permanent traffic growth that may justify a capacity upgrade request.
4. If congestion is degrading a priority enterprise SLA, temporarily
   reprioritize scheduling weights in favor of that traffic class.

## Escalation
Escalate to the RF/capacity planning team if congestion persists for more
than 5 consecutive days after load-balancing is applied — this indicates a
genuine capacity shortfall rather than a transient spike.

## Root Cause Checklist
- Compare congestion trend against a rolling 14-day baseline for the same
  cell, not just yesterday's numbers.
- Check for correlated alarms on neighboring cells that may be shedding
  traffic onto this one.
- Verify no misconfigured handover parameters are steering excess traffic to
  this cell.
