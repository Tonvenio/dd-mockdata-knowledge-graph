# `kg/` — built knowledge-graph outputs

This folder holds the materialised KG files produced by `python -m ddkg build`.
By default the `.ttl`, `.jsonld`, `.cypher` and `.graphml` files are
**git-ignored** (they're regenerable from the corpus + extractors in seconds).

If you want to ship the canonical gold KG with the repo, remove the
`kg/*.ttl` etc. lines from `.gitignore`, run a build, and commit. You may
also publish it as a GitHub Release asset (recommended for stable
versions; keeps the repo small).

Build with:

```bash
python -m ddkg build --corpus ../dd-mockdata --out kg/
```

Verify with:

```bash
python -m ddkg eval --kg kg/gold.ttl --suite ie
python -m ddkg eval --kg kg/gold.ttl --suite contradiction
pyshacl -s ../schema/shapes.ttl -e ../schema/ontology.ttl -d gold.ttl
```
