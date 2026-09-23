# Findings, graph and PDF integration update

## Status

Coverage preview for `analysis_6b330c0e0ce24b6caebb40e041038c55` produced:

- Event: 9
- ContributingFactor: 8
- Finding: 6
- SafetyIssue: 6
- Recommendation: 2

This confirms that candidate extraction is substantially richer than the currently published graph. The principal defect is over-compression during cross-document resolution/publication rather than absence of source candidates.

## Resolution rule

The next production resolver must be coverage-preserving:

1. every extracted candidate is accounted for exactly once;
2. only clear duplicates are merged;
3. node kind is preserved;
4. all member passage IDs are retained;
5. after any duplicate repair, passage IDs and deterministic node IDs must be recomputed from the final member set;
6. no candidate may disappear silently;
7. relationships remain evidence-bounded and must not be invented during coverage completion.

Notebook 57 remains a preview/read-only step. Its corrected logic is the basis for the next notebook-16 resolver revision.

## Findings & Evidence UI

Always show these six analytical groups, even when the count is zero:

1. Events
2. Contributing factors
3. Findings
4. Safety issues
5. Safety recommendations
6. Analytical relationships

Each group should show a count and a selectable list. Selecting an item should display:

- canonical label / description;
- supporting evidence;
- source document and page;
- embedded PDF at the cited page where available;
- collapsed technical provenance;
- collapsed Validation controls where applicable.

The page should make absence explicit (for example, `Safety recommendations — 0 identified`) rather than hiding an empty category.

## Knowledge Graph readability

Graph labels must be readable independently of node shape or theme:

- explicit high-contrast text colour;
- light node fills with dark/black labels by default;
- wrapped labels;
- minimum readable font size;
- node dimensions should expand with label length;
- selected nodes should use a distinct border/highlight without reducing label contrast;
- node shapes may distinguish types only when they do not obstruct text.

## PDF search

Add a text-search field next to the embedded evidence PDF.

Expected behaviour:

- search within the currently selected source PDF;
- show the number of matches;
- allow previous/next match navigation;
- when possible, jump to the page containing the match;
- preserve the original cited page as a quick-return action;
- searching must not alter evidence provenance or the stored citation.

The implementation should prefer native PDF-text extraction/search rather than OCR. OCR is only a fallback for image-only documents and is outside the first implementation slice.

## Ask / Compare integration

Ask/Compare remains a question interface over the case evidence. It must not become a competing source of structured findings.

If an answer cites evidence-grounded concepts that are not represented in the structured analysis, the App should surface a consistency notice rather than silently add them to the graph.

Reference documents remain optional context through a checkbox in normal Ask/Compare. They are context/taxonomy sources, not occurrence evidence.

## Graph Q&A

Graph questions should report both:

- what is currently represented in the graph; and
- whether underlying evidence contains candidate concepts not represented in the graph.

Graph Q&A must not mutate the graph automatically.
