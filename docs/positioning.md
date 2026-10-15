# Beachhead, positioning and whole supported workflow

## Original two-sentence positioning

For small watershed and wetland survey coordinators dissatisfied with manually reconciling an approved ranked site list and field-status spreadsheets, RankReserve is an offline survey operations ledger that turns explicit human dispositions into the next permitted reserve and a complete analyst record. Unlike a configured general field platform such as ODK Entities, RankReserve supplies a fixed independent-pool policy, transactional local storage, correction and incident holds, revision guards, full exports, backups, packaged examples and tested installation for this specific coordinator workflow.

This is intended positioning, not a claim that dissatisfaction or customer preference was observed. The market alternative is spreadsheet/coordinator reconciliation; the product alternative is a configured ODK workflow. Broader platforms remain better fits when mobile capture, maps or distributed synchronization are required.

## Applying Geoffrey Moore selectively

Moore's [own account of Crossing the Chasm](https://geoffreyamoore.com/book/crossing-the-chasm/) emphasizes a narrowly chosen use case, a compelling reason to adopt and the complete solution required to make it work. The [Chasm Institute's whole-product messaging material](https://www.chasminstitute.com/LinkClick.aspx?fileticket=pKf52Jeg8-4%3D&portalid=0), slide 11, connects segment, need, category, benefit, alternative and differentiated solution. The two-sentence statement above is original and applies that structure to this product; it does not reproduce the source template.

Beachhead: one coordinator of a small environmental probability survey with an already approved sequence and scientifically independent fixed pools. The reason to use it is keeping reserve activation and the full disposition record consistent during field operations. That need is supported by protocol evidence in [research](research.md); willingness to adopt this implementation remains unproven. There are no reference customers.

The whole supported workflow includes approved mapping, local installation, a learning example, explicit human outcomes, next-only activation, corrections without erased history, off-plan incident evidence, exhaustion/conflict handling, all-site analyst exports, recovery/backup and isolated distribution checks. The command itself is only part of the solution. Scope is intentionally fixed so those pieces can be supplied and tested together. This open-source release makes no invented revenue, pricing, sales-channel or market-share strategy.

## Constructed usage scenarios

**Two denials before a crew week.** A coordinator has two Inland base sites and three ordered reserves. Both bases receive documented final denial. The coordinator activates the first two reserves, retaining both denials. The crew completes the second active reserve before the first because of travel conditions. This is allowed: activation order and travel order serve different purposes.

**Weather delay is unresolved work.** A base is temporarily flooded and marked `deferred`. No reserve slot opens. The coordinator must obtain an explicit final disposition under the approved protocol before replacing it. The tool cannot judge flood duration, eligibility or safe access.

**Truthful correction after an activation.** A mistaken denial is corrected after a reserve has been activated. The ledger preserves both events and the reserve activation, reports overcommitment and stops further activation. The coordinator exports the conflict for the design authority. It does not quietly cancel work or turn a correction into evidence of a valid design.

**Crew used an unactivated reserve.** The coordinator records an incident. The real report is retained, the reserve is still shown as never authorized, and the pool is held for analyst review. The product does not invent retrospective authorization. Resolving a changed design is outside version 1.

These scenarios are constructed acceptance cases, not customer stories or measured outcomes.
