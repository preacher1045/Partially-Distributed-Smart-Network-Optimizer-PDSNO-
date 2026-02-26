# PDSNO Helm Chart

Deploy PDSNO to Kubernetes using Helm.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- PV provisioner support

## Installing the Chart
```bash
# Add PDSNO Helm repository
helm repo add pdsno https://charts.pdsno.io
helm repo update

# Install with default values
helm install my-pdsno pdsno/pdsno

# Install with custom values
helm install my-pdsno pdsno/pdsno -f custom-values.yaml

# Install from local chart
helm install my-pdsno ./deployment/helm
```

## Uninstalling
```bash
helm uninstall my-pdsno
```

## Configuration

See `values.yaml` for all configuration options.

### Key Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `globalController.enabled` | Enable Global Controller | `true` |
| `globalController.replicaCount` | Number of replicas | `1` |
| `postgresql.enabled` | Enable PostgreSQL | `true` |
| `mqtt.enabled` | Enable MQTT broker | `true` |
| `ingress.enabled` | Enable ingress | `true` |

### Example: Production Deployment
```yaml
# production-values.yaml
globalController:
  replicaCount: 2
  resources:
    limits:
      cpu: 4000m
      memory: 8Gi
  
  tls:
    enabled: true

postgresql:
  primary:
    persistence:
      size: 100Gi

ingress:
  enabled: true
  hosts:
    - host: pdsno.production.com
```

Deploy:
```bash
helm install pdsno-prod ./deployment/helm -f production-values.yaml
```