# Releasing 0.1.0

Run the full CI-equivalent checks, build the wheel and source distribution, inspect their file lists for secrets and customer media, and verify that `captivate --version` reports the release version. Tag the commit as `v0.1.0` and attach SHA-256 checksums to the GitHub Release. Publish to PyPI only after the package name, license, Ruffle asset policy, and supported operating systems have been reviewed.

