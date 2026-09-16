# Legacy 2022 forensic archive

Every item in `original/` is a byte-preserving forensic copy of the exact
legacy tree at Git commit `669f6e2`. These files are retained only for legacy
reproduction and reconciliation. They are outside the active calculation path
and must not be used as inputs to the reproducible pipeline.

`original-paths.txt` fixes the complete source path set; `sha256.txt` records
the SHA-256 digest of every archived byte sequence.
