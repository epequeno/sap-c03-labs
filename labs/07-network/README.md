# Lab 7 — Network and hybrid patterns (optional)

**Stack:** not written. `infra/stacks/lab07_network.py`. **First to drop if the schedule slips** — Lab 7 is the cheapest thing to lose, and practice questions are not.

## Question

For a service that must be reachable from two VPCs without peering, which construct carries the routing, and what is unreachable until the association exists?

## Constraints

- `us-east-1`, sandbox account, **$2–4**.
- Two VPCs maximum. Transit Gateway only if it already exists in the account; otherwise the route-table artifact is a design note.
- NAT gateways are the cost trap. Use VPC endpoints and no NAT where possible.

## Build

Two VPCs, a VPC Lattice service network with a Lambda target, a PrivateLink endpoint for a service in the second VPC, IPv6 dual-stack on the subnets, and Reachability Analyzer to prove the path.

## Failure to demonstrate

The service is unreachable until the Lattice association or the route-table entry is added. Capture the failing Reachability Analyzer result and then the passing one.

## Evidence

Service network and associations, endpoint, IPv6 addresses on an ENI, Reachability Analyzer before and after, route tables, cost report.

## Exam mapping

1.3.1–1.3.5 (connectivity and hybrid), 1.4.1–1.4.5 (network design), 3.2.4 (network cost).

## Still to fill

- [ ] Stack
- [ ] Diagram, committed as Mermaid or SVG
- [ ] Deploy section with the exact commands
- [ ] Evidence folder committed, with both Analyzer results
- [ ] `cost.md` with teardown timestamp
- [ ] Interview line: Lattice vs PrivateLink vs Transit Gateway, chosen by requirement, not preference
