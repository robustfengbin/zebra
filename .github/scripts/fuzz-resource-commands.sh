#!/usr/bin/env bash
# Diagnostic only: use the existing CI command shapes, never execute fuzzers.
set -euo pipefail
case "${1:?probe mode required}" in
  clippy-release)
    cargo clippy --workspace --all-targets --features default-release-binaries
    ;;
  clippy-tests)
    cargo clippy --workspace --all-targets --features 'default-release-binaries proptest-impl lightwalletd-grpc-tests zebra-checkpoints'
    ;;
  hack)
    cargo hack check --workspace
    ;;
  crate)
    cargo clippy --package zebra-fuzz-targets -- -D warnings
    cargo build --package zebra-fuzz-targets
    cargo clippy --package zebra-fuzz-targets --no-default-features --all-targets -- -D warnings
    cargo build --package zebra-fuzz-targets --no-default-features --all-targets
    cargo clippy --package zebra-fuzz-targets --all-targets -- -D warnings
    cargo build --package zebra-fuzz-targets --all-targets
    cargo clippy --package zebra-fuzz-targets --all-features --all-targets -- -D warnings
    cargo build --package zebra-fuzz-targets --all-features --all-targets
    ;;
  msrv)
    cargo build --package zebra-fuzz-targets --all-features --all-targets
    ;;
  *) printf 'Unknown probe mode: %s\n' "$1" >&2; exit 2 ;;
esac
