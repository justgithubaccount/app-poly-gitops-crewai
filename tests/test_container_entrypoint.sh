#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

printf '%s' 'test-token' > "$tmp_dir/token"
printf '%s' 'test-ca' > "$tmp_dir/ca.crt"

KUBERNETES_SERVICEACCOUNT_DIR="$tmp_dir" \
KUBERNETES_SERVICE_HOST="10.0.0.1" \
KUBERNETES_SERVICE_PORT_HTTPS="443" \
"$repo_root/docker-entrypoint.sh" sh -c '
  test -n "$KUBECONFIG"
  test -f "$KUBECONFIG"
  grep -q "server: https://10.0.0.1:443" "$KUBECONFIG"
  grep -q "token: test-token" "$KUBECONFIG"
  grep -q "certificate-authority: $KUBERNETES_SERVICEACCOUNT_DIR/ca.crt" "$KUBECONFIG"
'
