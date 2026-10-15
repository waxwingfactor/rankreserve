# Opportunity evidence and alternatives

Research date: **2026-10-15**. This is bounded desk research by the lead and separate AI research reviewers. We did not conduct interviews, observe customer adoption, measure savings or establish that coordinators will switch. Demand for this particular implementation remains an inference. We do not claim universal uniqueness, statistical certification or EPA endorsement.

## Documented workflow

The [EPA NWCA 2026 Site Evaluation Guidelines](https://www.epa.gov/system/files/documents/2026-05/nwca-2026-site-evaluation-guidelines_v1.0_20251020.pdf), v1.0 October 2025, pp.20–22, require maintaining selection-list order while allowing practical chronological travel order. They specify same-state/stratum replacement and recording evaluated sites, including unsuccessful ones. The replacement flowchart was visually inspected. This documents a meaningful operational constraint, while also showing a substantial native spreadsheet/coordinator workflow. The private workbook's full automation was not inspected. RankReserve does not claim turnkey compatibility with that national survey.

The [NWCA 2026 QAPP](https://www.epa.gov/system/files/documents/2026-05/nwca-2026-quality-assurance-project-plan-v1_1.pdf), v1.1 March 2026, §4.4.1 p.59, describes crews submitting site-evaluation spreadsheets through SharePoint; coordinators combine those with Field App verification, identify missing information and request completion. This establishes reconciliation work, not its measured burden or dissatisfaction with EPA's existing system.

The [NRSA 2018–19 Technical Support Document](https://www.epa.gov/system/files/documents/2024-12/nrsa-2018-19-tsd-final-11252024.pdf), September 2024, §§3.4.3–3.5 pp.24–25, describes panel-specific replacement rules and the importance of dispositions for weight adjustment. That is why the product retains unsuccessful and unused sites for an analyst; it never computes weights or asserts unbiasedness. More complicated panel rules remain unsupported.

## Three independent competition checks

| Check | Strong existing capability | RankReserve's bounded distinction |
| --- | --- | --- |
| Native EPA tools and operations | Spreadsheets, field verification, coordinator review; design and post-field weighting tools | One ready-to-run local policy for explicitly supplied independent pools. Existing official processes remain authoritative. |
| Maintained open-source design tools | Ranked/nearest-neighbor reserves, spatial design and inference | Persistent disposition-to-activation state, corrections, holds and complete history; no new sampling algorithm. |
| Generic field platforms | Mobile/offline forms, persistent cases, assignments and synchronization | Supplied fixed policy and zero-service local install; accepts single-coordinator limitations in exchange. |

[spsurvey's official sampling vignette](https://usepa.github.io/spsurvey/articles/sampling.html) documents both reverse-hierarchical ordered oversampling (`n_over`) and nearest-neighbor replacements (`n_near`). It also documents stratification, weights and export. It is the appropriate design/analysis tool. Its [function index](https://usepa.github.io/spsurvey/reference/index.html) was checked for an existing operational activation ledger. The reviewed documentation covers design and analysis; that bounded observation does not prove other tools or scripts lack the workflow.

The [EPA Survey Design Tool](https://github.com/USEPA/OW_Survey_Design_Tool), v2.0.0 updated 2026-05-08, creates spatially balanced designs, exports locations and adjusts original design weights after replacements. Its README and public app source were checked at feature level. The documented design/export/adjustment workflow is substantial; a generic replacement-selector or weighting wrapper would add little. RankReserve instead stores operational decisions between design and analyst handoff.

[ODK Entities](https://docs.getodk.org/central-entities/) has persistent entity lists, CSV imports, forms that update status, history and conflict handling. Current Collect supports offline entity updates. A team can configure an appropriate policy around ODK; it is a serious open-source product alternative, particularly when mobile collection and multiple crews are required. We did not build and test such a configuration, so make no claim that ODK cannot implement the same policy.

[ArcGIS Survey123's Inbox](https://doc.arcgis.com/en/survey123/create/connect/prepareforediting.htm) retrieves and edits existing records using queries and filters. [Fulcrum Workflows](https://help.fulcrumapp.com/en/articles/5141320-how-do-workflows-work) supports triggers, conditions and record actions. Both can support field operations and custom integration. The inspected documentation did not describe this exact supplied ranked-pool ledger as a packaged workflow. Configuration is an alternative, not an impossibility; effective existing installations need not be replaced.

The native spreadsheet plus coordinator judgment is the **market alternative**. A configured ODK Entities workflow is the **product alternative**. RankReserve is plausible for a coordinator who prefers an installable local ledger and does not need the broader capabilities of a field platform. Whether that tradeoff appeals to real users has not been validated.

Searches independently combined GRTS, reserve/oversample, replacement, tracking, management, site evaluation, Survey123, Field Maps, ODK and field software. Searches were followed by the primary feature reviews above; scarce search results were not treated as proof of absence. Two initial lanes were rejected: generic camera-trap effort accounting (existing camtrapR/camtraptor tools) and water-quality fouling/drift correction ([USGS CHIMP](https://water.usgs.gov/usgs/owq/chimp/) and companions).
