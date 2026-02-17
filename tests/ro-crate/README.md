# RO-Crate Example

This directory provides a complete RO-Crate example that can be inspected without running a workflow.
See [`docs/ro-crate.md`](../../docs/ro-crate.md) for the full specification.

- `ro-crate-metadata.json`: Generated metadata (quick reference copy of `ro-crate_dir/ro-crate-metadata.json`)
- `ro-crate_dir/`: Sample run directory with all source files and generated metadata

## Regenerating Metadata

To regenerate metadata from the data in `ro-crate_dir/`:

```bash
sapporo-cli generate-ro-crate tests/ro-crate/ro-crate_dir
cp tests/ro-crate/ro-crate_dir/ro-crate-metadata.json tests/ro-crate/ro-crate-metadata.json
```
