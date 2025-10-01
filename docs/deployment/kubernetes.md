# Kubernetes Deployment Guide

This guide covers deploying the MicroVM Sandbox on Kubernetes clusters.

## Prerequisites

- Kubernetes cluster 1.24+
- kubectl configured for your cluster
- Nodes with KVM support
- Helm 3.0+ (optional)
- Persistent storage provisioner

## Quick Start

### 1. Deploy with Kubectl

```bash
# Apply all manifests
kubectl apply -f scripts/deployment/kubernetes/

# Check deployment status
kubectl get pods -n microvm-sandbox
kubectl get services -n microvm-sandbox
```

### 2. Deploy with Helm

```bash
# Add Helm repository
helm repo add microvm-sandbox https://charts.microvm-sandbox.org
helm repo update

# Install with default values
helm install microvm-sandbox microvm-sandbox/microvm-sandbox

# Or install with custom values
helm install microvm-sandbox microvm-sandbox/microvm-sandbox \
  --values custom-values.yaml
```

## Manual Deployment

### 1. Namespace and RBAC

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: microvm-sandbox
  labels:
    name: microvm-sandbox

---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: microvm-sandbox
  namespace: microvm-sandbox

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: microvm-sandbox
rules:
- apiGroups: [""]
  resources: ["nodes", "pods", "services", "configmaps", "secrets"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
- apiGroups: ["apps"]
  resources: ["deployments", "replicasets"]
  verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]

---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: microvm-sandbox
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: microvm-sandbox
subjects:
- kind: ServiceAccount
  name: microvm-sandbox
  namespace: microvm-sandbox
```

### 2. ConfigMaps and Secrets

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: microvm-sandbox-config
  namespace: microvm-sandbox
data:
  config.yaml: |
    server:
      host: "0.0.0.0"
      port: 8000
      workers: 4
    
    cloud_hypervisor:
      binary_path: "/usr/local/bin/cloud-hypervisor"
      api_socket_dir: "/tmp/ch-sockets"
    
    networking:
      bridge_name: "chbr0"
      subnet: "192.168.200.0/24"
    
    resources:
      max_vms: 50
      max_memory_per_vm: 8192
      max_vcpus_per_vm: 8
    
    security:
      enable_authentication: true
      vm_isolation: true
    
    monitoring:
      prometheus_port: 9090
      metrics_enabled: true

---
apiVersion: v1
kind: Secret
metadata:
  name: microvm-sandbox-secrets
  namespace: microvm-sandbox
type: Opaque
data:
  jwt-secret: <base64-encoded-jwt-secret>
  database-password: <base64-encoded-password>
  encryption-key: <base64-encoded-encryption-key>
```

### 3. Persistent Volumes

```yaml
# storage.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: microvm-data
  namespace: microvm-sandbox
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Gi
  storageClassName: fast-ssd

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: microvm-images
  namespace: microvm-sandbox
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
  storageClassName: fast-ssd

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: microvm-snapshots
  namespace: microvm-sandbox
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 200Gi
  storageClassName: standard
```

### 4. Database Deployment

```yaml
# database.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: microvm-sandbox
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15-alpine
        env:
        - name: POSTGRES_DB
          value: "microvm_sandbox"
        - name: POSTGRES_USER
          value: "microvm"
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: microvm-sandbox-secrets
              key: database-password
        ports:
        - containerPort: 5432
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
      volumes:
      - name: postgres-data
        persistentVolumeClaim:
          claimName: postgres-data

---
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: microvm-sandbox
spec:
  selector:
    app: postgres
  ports:
  - port: 5432
    targetPort: 5432

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgres-data
  namespace: microvm-sandbox
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
  storageClassName: fast-ssd
```

### 5. Redis Deployment

```yaml
# redis.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: microvm-sandbox
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command:
        - redis-server
        - --appendonly
        - "yes"
        ports:
        - containerPort: 6379
        volumeMounts:
        - name: redis-data
          mountPath: /data
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "200m"
      volumes:
      - name: redis-data
        persistentVolumeClaim:
          claimName: redis-data

---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: microvm-sandbox
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379

---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: redis-data
  namespace: microvm-sandbox
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
```

### 6. Main Application Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: microvm-sandbox
  namespace: microvm-sandbox
  labels:
    app: microvm-sandbox
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: microvm-sandbox
  template:
    metadata:
      labels:
        app: microvm-sandbox
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9090"
        prometheus.io/path: "/metrics"
    spec:
      serviceAccountName: microvm-sandbox
      nodeSelector:
        kvm: "true"  # Schedule only on KVM-enabled nodes
      securityContext:
        fsGroup: 1000
      containers:
      - name: microvm-sandbox
        image: microvm-sandbox:v1.0.0
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8000
          name: api
        - containerPort: 9090
          name: metrics
        env:
        - name: CONFIG_PATH
          value: "/app/config/config.yaml"
        - name: LOG_LEVEL
          value: "INFO"
        - name: DATABASE_URL
          value: "postgresql://microvm:$(DATABASE_PASSWORD)@postgres:5432/microvm_sandbox"
        - name: REDIS_URL
          value: "redis://redis:6379/0"
        - name: JWT_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: microvm-sandbox-secrets
              key: jwt-secret
        - name: DATABASE_PASSWORD
          valueFrom:
            secretKeyRef:
              name: microvm-sandbox-secrets
              key: database-password
        - name: ENCRYPTION_KEY
          valueFrom:
            secretKeyRef:
              name: microvm-sandbox-secrets
              key: encryption-key
        volumeMounts:
        - name: config
          mountPath: /app/config
          readOnly: true
        - name: data
          mountPath: /var/lib/microvm-sandbox
        - name: images
          mountPath: /app/images
        - name: snapshots
          mountPath: /var/lib/microvm-sandbox/snapshots
        - name: kvm-device
          mountPath: /dev/kvm
        - name: tmp
          mountPath: /tmp
        securityContext:
          privileged: true  # Required for KVM access
          runAsUser: 1000
          runAsGroup: 1000
          capabilities:
            add:
            - NET_ADMIN
            - SYS_ADMIN
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "8Gi"
            cpu: "4000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
          timeoutSeconds: 10
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 2
      volumes:
      - name: config
        configMap:
          name: microvm-sandbox-config
      - name: data
        persistentVolumeClaim:
          claimName: microvm-data
      - name: images
        persistentVolumeClaim:
          claimName: microvm-images
      - name: snapshots
        persistentVolumeClaim:
          claimName: microvm-snapshots
      - name: kvm-device
        hostPath:
          path: /dev/kvm
          type: CharDevice
      - name: tmp
        emptyDir:
          sizeLimit: 1Gi
```

### 7. Services and Ingress

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: microvm-sandbox
  namespace: microvm-sandbox
  labels:
    app: microvm-sandbox
spec:
  type: ClusterIP
  ports:
  - port: 8000
    targetPort: 8000
    protocol: TCP
    name: api
  - port: 9090
    targetPort: 9090
    protocol: TCP
    name: metrics
  selector:
    app: microvm-sandbox

---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: microvm-sandbox
  namespace: microvm-sandbox
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/rewrite-target: /
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "300"
spec:
  tls:
  - hosts:
    - api.microvm-sandbox.example.com
    secretName: microvm-sandbox-tls
  rules:
  - host: api.microvm-sandbox.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: microvm-sandbox
            port:
              number: 8000
```

## Node Configuration

### 1. Node Labels

Label nodes that support KVM:

```bash
# Check KVM support
kubectl get nodes -o wide

# Label KVM-enabled nodes
kubectl label node worker-node-1 kvm=true
kubectl label node worker-node-2 kvm=true

# Verify labels
kubectl get nodes -l kvm=true
```

### 2. Device Plugin (Alternative)

Deploy KVM device plugin for better resource management:

```yaml
# kvm-device-plugin.yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: kvm-device-plugin
  namespace: kube-system
spec:
  selector:
    matchLabels:
      name: kvm-device-plugin
  template:
    metadata:
      labels:
        name: kvm-device-plugin
    spec:
      hostNetwork: true
      containers:
      - name: kvm-device-plugin
        image: kubevirt/kvm-device-plugin:latest
        securityContext:
          privileged: true
        volumeMounts:
        - name: device-plugin
          mountPath: /var/lib/kubelet/device-plugins
        - name: dev
          mountPath: /dev
      volumes:
      - name: device-plugin
        hostPath:
          path: /var/lib/kubelet/device-plugins
      - name: dev
        hostPath:
          path: /dev
      nodeSelector:
        kvm: "true"
```

Use in deployment:

```yaml
# Updated deployment with device plugin
spec:
  template:
    spec:
      containers:
      - name: microvm-sandbox
        resources:
          requests:
            devices.kubevirt.io/kvm: "1"
          limits:
            devices.kubevirt.io/kvm: "1"
```

## High Availability Setup

### 1. Multi-Region Deployment

```yaml
# ha-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: microvm-sandbox
  namespace: microvm-sandbox
spec:
  replicas: 6
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 2
      maxUnavailable: 1
  selector:
    matchLabels:
      app: microvm-sandbox
  template:
    metadata:
      labels:
        app: microvm-sandbox
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - microvm-sandbox
              topologyKey: kubernetes.io/hostname
          - weight: 50
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - microvm-sandbox
              topologyKey: topology.kubernetes.io/zone
      # ... rest of container spec
```

### 2. Database High Availability

```yaml
# postgres-ha.yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: postgres-cluster
  namespace: microvm-sandbox
spec:
  instances: 3
  primaryUpdateStrategy: unsupervised
  
  postgresql:
    parameters:
      max_connections: "200"
      shared_buffers: "256MB"
      effective_cache_size: "1GB"
  
  bootstrap:
    initdb:
      database: microvm_sandbox
      owner: microvm
      secret:
        name: postgres-credentials
  
  storage:
    size: 50Gi
    storageClass: fast-ssd
  
  monitoring:
    enabled: true
```

### 3. Load Balancer Configuration

```yaml
# load-balancer.yaml
apiVersion: v1
kind: Service
metadata:
  name: microvm-sandbox-lb
  namespace: microvm-sandbox
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: nlb
    service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"
spec:
  type: LoadBalancer
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
  - port: 443
    targetPort: 8000
    protocol: TCP
  selector:
    app: microvm-sandbox
```

## Monitoring and Observability

### 1. Prometheus Monitoring

```yaml
# monitoring.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: microvm-sandbox
  namespace: microvm-sandbox
  labels:
    app: microvm-sandbox
spec:
  selector:
    matchLabels:
      app: microvm-sandbox
  endpoints:
  - port: metrics
    interval: 30s
    path: /metrics

---
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: microvm-sandbox-alerts
  namespace: microvm-sandbox
spec:
  groups:
  - name: microvm-sandbox
    rules:
    - alert: MicroVMSandboxDown
      expr: up{job="microvm-sandbox"} == 0
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "MicroVM Sandbox is down"
        description: "MicroVM Sandbox has been down for more than 5 minutes."
    
    - alert: HighMemoryUsage
      expr: (microvm_host_memory_used / microvm_host_memory_total) * 100 > 90
      for: 10m
      labels:
        severity: warning
      annotations:
        summary: "High memory usage"
        description: "Memory usage is above 90% for more than 10 minutes."
    
    - alert: TooManyRunningVMs
      expr: microvm_vms_running > 40
      for: 5m
      labels:
        severity: warning
      annotations:
        summary: "Too many running VMs"
        description: "More than 40 VMs are running, approaching the limit."
```

### 2. Logging with Fluentd

```yaml
# logging.yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluentd
  namespace: microvm-sandbox
spec:
  selector:
    matchLabels:
      name: fluentd
  template:
    metadata:
      labels:
        name: fluentd
    spec:
      containers:
      - name: fluentd
        image: fluent/fluentd-kubernetes-daemonset:v1-debian-elasticsearch
        env:
        - name: FLUENT_ELASTICSEARCH_HOST
          value: "elasticsearch.elastic-system.svc.cluster.local"
        - name: FLUENT_ELASTICSEARCH_PORT
          value: "9200"
        volumeMounts:
        - name: varlog
          mountPath: /var/log
        - name: varlibdockercontainers
          mountPath: /var/lib/docker/containers
          readOnly: true
        - name: config
          mountPath: /fluentd/etc/fluent.conf
          subPath: fluent.conf
      volumes:
      - name: varlog
        hostPath:
          path: /var/log
      - name: varlibdockercontainers
        hostPath:
          path: /var/lib/docker/containers
      - name: config
        configMap:
          name: fluentd-config
```

## Scaling and Autoscaling

### 1. Horizontal Pod Autoscaler

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: microvm-sandbox-hpa
  namespace: microvm-sandbox
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: microvm-sandbox
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  - type: Pods
    pods:
      metric:
        name: microvm_vms_running
      target:
        type: AverageValue
        averageValue: "8"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 600
      policies:
      - type: Percent
        value: 25
        periodSeconds: 60
```

### 2. Vertical Pod Autoscaler

```yaml
# vpa.yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: microvm-sandbox-vpa
  namespace: microvm-sandbox
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: microvm-sandbox
  updatePolicy:
    updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
    - containerName: microvm-sandbox
      maxAllowed:
        cpu: 8
        memory: 16Gi
      minAllowed:
        cpu: 500m
        memory: 1Gi
```

## Security Configuration

### 1. Pod Security Standards

```yaml
# security-policy.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: microvm-sandbox
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted

---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: microvm-sandbox-quota
  namespace: microvm-sandbox
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.cpu: "40"
    limits.memory: 80Gi
    persistentvolumeclaims: "10"
    pods: "50"
```

### 2. Network Policies

```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: microvm-sandbox-netpol
  namespace: microvm-sandbox
spec:
  podSelector:
    matchLabels:
      app: microvm-sandbox
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  - from:
    - namespaceSelector:
        matchLabels:
          name: monitoring
    ports:
    - protocol: TCP
      port: 9090
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
  - to:
    - podSelector:
        matchLabels:
          app: redis
    ports:
    - protocol: TCP
      port: 6379
  - to: []
    ports:
    - protocol: TCP
      port: 53
    - protocol: UDP
      port: 53
```

## Helm Chart

### 1. Chart Structure

```
charts/microvm-sandbox/
├── Chart.yaml
├── values.yaml
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── pvc.yaml
│   ├── hpa.yaml
│   └── serviceaccount.yaml
└── values/
    ├── production.yaml
    ├── staging.yaml
    └── development.yaml
```

### 2. Values Configuration

```yaml
# values.yaml
image:
  repository: microvm-sandbox
  tag: "v1.0.0"
  pullPolicy: IfNotPresent

replicaCount: 3

resources:
  requests:
    memory: "2Gi"
    cpu: "1000m"
  limits:
    memory: "8Gi"
    cpu: "4000m"

autoscaling:
  enabled: true
  minReplicas: 3
  maxReplicas: 10
  targetCPUUtilizationPercentage: 70
  targetMemoryUtilizationPercentage: 80

persistence:
  data:
    enabled: true
    size: 100Gi
    storageClass: fast-ssd
  images:
    enabled: true
    size: 50Gi
    storageClass: fast-ssd
  snapshots:
    enabled: true
    size: 200Gi
    storageClass: standard

database:
  enabled: true
  type: postgresql
  host: postgres
  port: 5432
  name: microvm_sandbox
  username: microvm

redis:
  enabled: true
  host: redis
  port: 6379

ingress:
  enabled: true
  className: nginx
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: api.microvm-sandbox.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: microvm-sandbox-tls
      hosts:
        - api.microvm-sandbox.example.com

monitoring:
  enabled: true
  serviceMonitor:
    enabled: true
  prometheusRule:
    enabled: true

security:
  podSecurityContext:
    fsGroup: 1000
  securityContext:
    privileged: true
    runAsUser: 1000
    runAsGroup: 1000
```

### 3. Installation Commands

```bash
# Install with Helm
helm install microvm-sandbox ./charts/microvm-sandbox \
  --namespace microvm-sandbox \
  --create-namespace \
  --values values/production.yaml

# Upgrade
helm upgrade microvm-sandbox ./charts/microvm-sandbox \
  --namespace microvm-sandbox \
  --values values/production.yaml

# Uninstall
helm uninstall microvm-sandbox --namespace microvm-sandbox
```

## Troubleshooting

### 1. Common Issues

**Pods stuck in Pending:**
```bash
# Check node resources
kubectl describe nodes

# Check pod events
kubectl describe pod microvm-sandbox-xxx -n microvm-sandbox

# Check scheduler logs
kubectl logs -n kube-system deployment/kube-scheduler
```

**KVM access issues:**
```bash
# Check node labels
kubectl get nodes -l kvm=true

# Check device availability
kubectl exec -it microvm-sandbox-xxx -n microvm-sandbox -- ls -la /dev/kvm

# Check security context
kubectl get pod microvm-sandbox-xxx -n microvm-sandbox -o yaml | grep -A 10 securityContext
```

**Network connectivity issues:**
```bash
# Check services
kubectl get svc -n microvm-sandbox

# Check ingress
kubectl get ingress -n microvm-sandbox
kubectl describe ingress microvm-sandbox -n microvm-sandbox

# Test internal connectivity
kubectl exec -it microvm-sandbox-xxx -n microvm-sandbox -- curl http://postgres:5432
```

### 2. Debug Commands

```bash
# Get all resources
kubectl get all -n microvm-sandbox

# Check logs
kubectl logs -f deployment/microvm-sandbox -n microvm-sandbox

# Debug networking
kubectl exec -it microvm-sandbox-xxx -n microvm-sandbox -- netstat -tlnp

# Check resource usage
kubectl top pods -n microvm-sandbox
kubectl top nodes

# Get events
kubectl get events -n microvm-sandbox --sort-by=.metadata.creationTimestamp
```

## Best Practices

1. **Use resource quotas** to limit namespace resource usage
2. **Implement pod disruption budgets** for availability
3. **Use anti-affinity rules** to spread pods across nodes
4. **Configure health checks** for automatic recovery
5. **Use init containers** for setup tasks
6. **Implement proper RBAC** for security
7. **Use secrets** for sensitive configuration
8. **Monitor resource usage** and set alerts
9. **Implement backup strategies** for persistent data
10. **Use staging environments** for testing updates