Test Data
=========

This folder holds sample inputs for local testing. Suggested structure:

- albums/    structured album folders (artist/album/track files)
- singles/   individual tracks or small batches
- fixtures/  tiny files for quick smoke tests
- misc/      anything else temporary

Use `make seed-incoming-from-test` to copy everything under `test-data/albums` into `pipeline-data/incoming` while preserving structure.
