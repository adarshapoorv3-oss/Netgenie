# Fiber Cut Incident Response

## Detection
A fiber cut typically surfaces as a sudden, simultaneous loss of signal (LOS)
alarm across every cell on the affected transport ring, paired with a sharp
drop in throughput and a spike in dropped-call rate for every site on that
ring within the same one-to-two minute window. A single isolated cell losing
signal is more likely a local hardware fault, not a fiber cut — check whether
neighboring cells on the same ring are also alarming before proceeding.

## Immediate Actions
1. Confirm the blast radius: pull every cell on the affected ring and verify
   they alarmed within the same short window.
2. Fail traffic over to the protection path or backup microwave link if one
   is provisioned for the ring.
3. Notify the field operations team with the suspected physical route segment
   so a truck roll can be dispatched.
4. Open a customer-facing status page entry if the affected ring serves more
   than 2 sites or any priority/enterprise customer.

## Escalation
Escalate to Tier 3 transport engineering immediately if protection switching
fails or is unavailable. Escalate to the incident commander on-call if the
outage is projected to exceed 30 minutes or affects an emergency-services
adjacent site.

## Root Cause Checklist
- Was there recent construction, utility, or landscaping work along the route?
- Did the alarm timestamp align with any reported utility dig activity?
- Was the cut on the primary path, the protection path, or both?
- Confirm restoration with an end-to-end optical power reading, not just the
  alarm clearing, before closing the ticket.
