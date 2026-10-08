# Adding a component without changing the router

A component is supported for export only when its logical definition, native symbol geometry, canonical pins, and serialized LTspice behavior are verified. A frontend drawing alone is not backend support. Do not register aliases to a similar component as a substitute.

## 1. Add the logical definition

Add a definition under `frontend/lib/circuit/library/` using the existing `ComponentDefinition` shape and export it through that directory's index. Define its canonical type, reference prefix, display symbol, default value, and default rotation. `ComponentLibrary` instantiates definitions and clones pins so instances do not share mutable pin arrays.

## 2. Define stable pins

Give every electrical pin a unique canonical ID and meaningful name. Preserve IDs across frontend, backend, the compiler bridge, fixtures, and LTspice SpiceOrder mapping. Define compatibility aliases explicitly; ambiguous or unknown aliases must fail. Numeric device package pin numbers and schematic pin ordering are not automatically interchangeable.

Frontend logical alias normalization currently lives in the builder; backend aliases live in `PIN_ALIASES` in `pin_maps.py`. Add only the necessary mapping. Do not introduce component-name checks in collision predicates or routing searches.

## 3. Identify the real symbol

Choose a verified installed LTspice `.asy` file. Record its exact relative path in backend `ComponentDefinition.asy_file` and serialization name in `symbol`. Verify symbol availability and any required model attributes. Do not generate a fake symbol or infer one from a model value.

## 4. Copy exact physical geometry

Add the backend definition in `backend/app/services/pin_maps.py` with:

- `kind`, `symbol`, `prefix`, and `default_value`;
- exact `PIN` coordinates from the stock `.asy`;
- pin IDs, names, and outward facing direction;
- symbol anchor and body bounds;
- default/supported rotations and mirror support.

The symbol anchor is the native ASY origin, not necessarily the drawing center. Backend absolute pin coordinates use `anchor + orientation(local pin)`. Frontend UI coordinates may differ, but logical pin identities must match.

## 5. Verify rotations and mirroring

Exercise R0/R90/R180/R270 and every mirror orientation you declare supported through `PinResolver`. Check transformed bounds, pin coordinates, escape directions, and exact grid alignment. Reject unsupported orientations; do not silently reset them to zero. M90/M270 require independent native verification if newly emitted by an exporter path.

## 6. Register LTspice mapping

Register canonical kind/type aliases and pin aliases in the library-owned tables. Keep model refinement restricted to the declared compatible family. Check `frontend/tools/compile-regression.cjs` for the test bridge's export-support mapping and the independent stock-symbol parser/oracle in `backend/app/services/regression_validation.py`. Independent oracle updates must come from real ASY data, not copied generated results.

The router should automatically use bounds, pins, orientation, and escape corridors from the definition. A symbol-specific placement preference may belong in layout, but electrical pin metadata and type substitutions do not belong there. Export presentation preferences may require narrowly scoped presentation metadata; serialization must not redefine connectivity.

## 7. Add a meaningful fixture

Add a small circuit using the component with explicit connections and expected canonical electrical groups. Include typical pin use and any optional disconnected pins. Preserve existing fixtures. Document source/provenance. The corpus collector should discover the new fixture automatically; review its manifest entry for count/support/validation accuracy.

## 8. Add unit and regression coverage

Cover definition uniqueness, pin aliases, physical coordinates, rotations, compiler construction, invalid pin/type rejection, blocked escape failure, deterministic layout/routes, and serialized symbol/reference/value integrity. Add the fixture to the controlled Phase 9 regression inventory/golden contract using `backend/tests/fixtures/regression/README.md`; do not update goldens merely to silence a failure.

Run from the repository root:

```powershell
npm test
npm run test:regression -- --require-ltspice
```

Also collect and run the complete corpus using the commands in [TESTING.md](../TESTING.md). A native fixture added without full bridge support must remain explicitly unsupported, not skipped or counted as a successful export.

## 9. Verify native export and presentation

Require an actual LTspice netlist and compare its electrical partition, labels, references, values, and symbol pins with the source. Open the schematic and inspect pin contacts, labels, overlap, routing, and cropping. Use `npm run verify:full` for native/rendered evidence and record image-bound visual verdicts after inspection. Simulation is not required.

If the frontend component drawing or editing behavior changes, exercise it in the browser on desktop and mobile, including save/load/export failure and retry. Acceptance requires the complete chain, not only a screenshot or a parser pass.
