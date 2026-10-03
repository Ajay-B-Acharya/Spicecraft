# Controlled circuit regression references

`golden.json` references the seven existing source files. It does **not** duplicate circuit definitions. Inventory validation requires every JSON in `backend/circuits` and `backend/tests/fixtures/routing` to have an entry; new circuits cannot silently miss regression coverage.

## Reference provenance

- Reference commit: `4b0f4d71a75e27152136df8f1b236adf74c2eba7` (Phase 8).
- Topology: existing independently specified `TEMPLATE_PARTITIONS`, `EXPECTED_PARTITIONS` and explicit unwired-pin contracts, checked against source definitions when this dataset was created.
- Component identity/value: existing circuit source definitions.
- Pin definitions: canonical library snapshot, independently checked against existing stock-ASY test data and installed LTspice during verification.
- Metrics: verified Phase 8 exports, after safe export cleanup.
- Visual references: existing Phase 8 native screenshots; their paths and SHA-256 digests are stored, not copied.

## Semantic comparison

Golden acceptance does not compare ASC bytes. A canonical topology is a sorted partition of `Component.Pin` identities. Anonymous net names, layout coordinates, wire length, bend count, and export ordering are ignored for electrical equivalence. Electrical label identities and their pin memberships have an additional explicit comparison.

Pins absent from source wires are recorded as `optional_unwired_pins`; they remain separate singleton electrical groups. `required_pins` means connected in the controlled source—not a newly invented device requirement. Deleting a source-required connection fails semantic equivalence; it is never repaired.

## Metrics policy

- Wire length: REVIEW when growth is greater than 20% **and** at least 64 coordinate units.
- Bends: REVIEW when growth is greater than 30% **and** at least 2 bends.
- Crossings: REVIEW on any increase; unintended/unsafe crossings are a separate hard failure.
- Small changes and improvements do not fail the suite. A REVIEW is not an electrical failure or automatic reference approval.
- Wall-clock timing is observational, not a fixed CI threshold.

## Deliberate reference updates

There is no auto-update/snapshot-accept switch.

1. Identify the source, library, or routing change and retain the failing/review report.
2. Review intended source connections and canonical pin identities independently. Do not derive replacement expectations solely from the exporter under test.
3. Run the complete suite with actual LTspice; verify all pins, groups, labels, shorts and opens.
4. Inspect old/new native visual comparisons. Image differences alone neither pass nor fail a circuit.
5. Edit only the justified reference fields, updating provenance/source or image hashes when those files actually change. Document the reason in the change review.
6. Rerun semantic and complete verification. Never change topology or pin mappings to hide a failure.

The two-component fixtures are small. The largest available fixture has six components. No medium/large-scale or 500-component scalability claim is made.
