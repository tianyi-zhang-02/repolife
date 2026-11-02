# Short brand exploration

2026-11-01. The author selected a shorter, more distinctive new name rather than polishing Repolife alone.
This changes the naming direction; it does not select a replacement or authorize an identifier migration.

## Brief

A small, independent developer tool that helps people and agents keep a working understanding of changing
systems. The brand should fit an editor panel, an offline report and a CLI, without requiring its own workflow.
Prefer five to seven letters, about two spoken syllables, lowercase ASCII spelling and a useful small wordmark.
Repo, Code and AI need not be in the name. Meaning can come from a clear product promise rather than a literal
description of the current scanner. Avoid names that suggest automated approval or a guarantee of safety.

The working product promise remains **Keep code understandable.** A supporting sentence is **Stay oriented
as code changes.** These describe the purpose; benefit still needs evaluation with maintainers.

## Lead proposal: Tessri

**Tessri** / **TESS-ree**, six letters, two proposed spoken syllables.

The intended association is separate pieces forming a coherent whole: code structure, change evidence,
maintenance history and the context a person needs. This is a proposed brand story inspired by a tiled
composition, not a claim that “Tessri” has this meaning in another language.

Why advance it:

- Shorter than Repolife and distinct from the generic Repo/Code naming pattern.
- Fits both a human-facing workbench and a small module used by another agent or tool.
- A compact geometric T can remain legible as an editor icon. A restrained purple mark and quiet surfaces fit
  the existing viewer direction; the status palette stays separate.
- “Open Tessri,” “Tessri evidence,” and “include the Tessri report” are workable product phrases.

Weaknesses to test: listeners may spell it Tesri or Tessry; the middle consonants may be awkward for some
speakers. Proposed pronunciation must be tested by asking people to say the name, then spell it after hearing
it. The initial exact-name and developer/package-oriented web searches found no obvious same-name development
tool, but did surface the company name string TESSRI S.A.S. in a
[Colombian court publication](https://www.ramajudicial.gov.co/documents/36156821/140101101/estado%2B065.pdf/cfc9eec0-5597-f5cc-d47f-2f538062011b).
The company's field and legal relevance were not established. Search absence is not availability.

### Official name checks, 2026-11-01

Read-only queries to the official services returned the following. The full URLs, UTC timestamp and HTTP
statuses are retained in [the check record](tessri-name-check.json). The timestamp corresponds to November 1
in America/New_York.

| Surface | Observed result |
| --- | --- |
| PyPI `tessri` | Package JSON endpoint returned 404. |
| npm `tessri` | Package registry endpoint returned 404. |
| GitHub `tessri` handle | User/organization endpoint returned 404. |
| GitHub repository names containing `tessri` | Repository search returned zero results. |
| `tessri.com` | Verisign RDAP returned 404. |
| `tessri.dev` | Google Registry RDAP returned 404. |
| `tessri.org` | Public Interest Registry RDAP returned 404. |

RDAP providers were obtained from the IANA bootstrap rather than inferred from DNS. A 404 means no public
record was returned at query time; it does not reserve the name or prove registration/publishing eligibility.
No domain was purchased or account/package name reserved. Trademark clearance remains unverified. These
results support a reversible Tessri viewer identity trial while the executable and integration identifiers
remain `repolife`.

The [identity study](assets/tessri-identity-study.svg) compares the same wordmark in light and dark contexts.
It is a reversible proposal, now being tried in the viewer name. Any Tessri command shown in design
material is illustrative; the executable remains `repolife`.

## Screening decisions

The shortlist intentionally advances one candidate rather than padding it with names that already have
strong adjacent uses. These are product differentiation decisions, not legal conclusions.

| Candidate | Decision | Evidence / concern |
| --- | --- | --- |
| Tessri | Viewer identity trial | No obvious same-name developer tool in the initial searches; company name use noted above. Official registry checks are recorded above; rights and publishing/registration eligibility remain unconfirmed. |
| Vesri | Hold | Compact, but visually close to Esri; weak differentiation for a system-mapping tool. |
| RepoKind | Deprioritize | Retains the descriptive Repo pattern the author now wants to move beyond. |
| Navri | Drop | [NavriScript](https://navri.ai/) already describes an AI systems language and ecosystem. |
| Nerlo | Drop | [Nerlo](https://nerlo.ai/about) already works on scrutiny of AI agent components and dependencies. |
| Orvyn | Drop | An existing [AI engineering workspace](https://www.kernelailabs.com/index.php/product) is too close to the target audience. |
| Velto | Drop | Existing [VS Code extension](https://marketplace.visualstudio.com/items?itemName=octamap.velto). |
| Tendry | Drop | Existing [verified-knowledge/RFP software](https://www.tendry.io/). |

## Before choosing and migrating

Test the name in the real viewer rail, a README introduction and a spoken maintainer handoff. Compare it with
Repolife on recall, spelling and expected purpose. Check the intended package registries and domains directly,
then assess relevant name rights before adopting it. No domain registration, purchase or public rename has
been performed.

If selected, design one migration covering package/command aliases, config discovery, integration ownership
markers, bundled skill names, links and documentation. Existing installs must keep working during a stated
transition. Do not spread a tentative name through analyzer logic or schema fields merely to preview a brand.
