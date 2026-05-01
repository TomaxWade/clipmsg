# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-05-01

### Added

- Public-release project structure for GitHub and MIT distribution
- QR pairing flow that opens the phone page and pairs automatically
- Automatic port fallback when the preferred port is already occupied
- One-file Windows EXE packaging script
- Release bundle script that creates a ZIP ready for GitHub Releases

### Changed

- Launcher no longer depends on a specific Conda environment
- Pairing now uses a strong token plus an HTTP-only cookie session
- Message storage now uses a lightweight JSON store outside the repo
- README rewritten for open-source and release usage

### Notes

- ClipMsg is still in the `0.x` phase, so minor versions may include breaking changes while the app shape settles.
