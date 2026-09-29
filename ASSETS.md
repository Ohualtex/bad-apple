# Bad-Apple Immutable Golden Assets Container 🍎📦

This permanent container hosts the verified, immutable binary and media assets for the [bad-apple](https://github.com/Ohualtex/bad-apple) terminal player.

## Assets Included
- `bad_apple.bin` (MD5: `bfb923d8e071539a4b23a9a9fabe6b04`): Pre-rendered BAPB binary cache container for zero-CPU, zero-OpenCV terminal playback.
- `bad_apple.mp3` (MD5: `fd4c1a0b0ead09b5c0ab58e4b1016317`): High-fidelity audio soundtrack.
- `bad_apple.mp4` (MD5: `187d905116db5e217338da08a67d1caf`): Original source video container for reference and cache generation.

## Architectural Purpose
Decoupling heavy binary assets into this immutable container guarantees:
1. PyPI distribution packages remain ultra-lightweight (<100 KB).
2. Git commit history remains lean without multi-megabyte binary bloat.
3. Every terminal player client fetches verified assets with cryptographic integrity.
