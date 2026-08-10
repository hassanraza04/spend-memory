# Releasing Spend Memory

Releases are created from version tags such as `v0.1.0`. The tag must match the
version in `pyproject.toml`.

The release workflow repeats the complete local verification suite, builds the
API and web containers from the committed lockfiles, and publishes these images:

```text
ghcr.io/hassanraza04/spend-memory-api:<version>
ghcr.io/hassanraza04/spend-memory-web:<version>
```

Each container has an SBOM and build provenance attached in the container
registry. The GitHub release also contains a source archive, both lockfiles,
and `SHA256SUMS` for offline verification:

```sh
sha256sum --check SHA256SUMS
```

Spend Memory does not have a hosted application or hosted upload endpoint.
Run the released source or containers locally and keep statement data on your
own machine.
