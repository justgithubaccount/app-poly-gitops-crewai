#!/bin/sh
set -eu

serviceaccount_dir=${KUBERNETES_SERVICEACCOUNT_DIR:-/var/run/secrets/kubernetes.io/serviceaccount}

if [ -n "${KUBERNETES_SERVICE_HOST:-}" ] && [ -z "${KUBECONFIG:-}" ] \
  && [ -f "$serviceaccount_dir/token" ] && [ -f "$serviceaccount_dir/ca.crt" ]; then
  kubeconfig=/tmp/auto-k8s-pilot-kubeconfig
  service_port=${KUBERNETES_SERVICE_PORT_HTTPS:-${KUBERNETES_SERVICE_PORT:-443}}
  token=$(cat "$serviceaccount_dir/token")
  namespace=default
  if [ -f "$serviceaccount_dir/namespace" ]; then
    namespace=$(cat "$serviceaccount_dir/namespace")
  fi

  umask 077
  cat > "$kubeconfig" <<EOF
apiVersion: v1
kind: Config
clusters:
  - name: in-cluster
    cluster:
      server: https://${KUBERNETES_SERVICE_HOST}:${service_port}
      certificate-authority: ${serviceaccount_dir}/ca.crt
users:
  - name: service-account
    user:
      token: ${token}
contexts:
  - name: in-cluster
    context:
      cluster: in-cluster
      user: service-account
      namespace: ${namespace}
current-context: in-cluster
EOF
  export KUBECONFIG="$kubeconfig"
fi

exec "$@"
