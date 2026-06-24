# Production Deployment Guide

This guide covers deploying the task-api application to production using both Docker Swarm and Kubernetes.

## What Each Platform Provides

### Docker Swarm
- **Simplicity**: Built into Docker, minimal setup
- **Best for**: Single server to small clusters (1-10 nodes)
- **Setup time**: ~5 minutes
- **Use case**: Staging, small production deployments
- **File**: `docker-stack.yml`

### Kubernetes
- **Features**: Self-healing, auto-scaling, rolling updates, advanced networking
- **Best for**: Enterprise, complex deployments, high availability (10+ nodes)
- **Setup time**: ~20 minutes (with existing cluster)
- **Use case**: Production, multi-region deployments
- **Files**: `k8s/*.yaml` manifests

---

## Docker Swarm Deployment

### Prerequisites
1. Docker installed on all nodes
2. Initialize swarm mode: `docker swarm init` (on manager node)
3. Environment variables set in `.env` file

### What's Included in docker-stack.yml
- **Replicas**: 1 API replica + 1 PostgreSQL
- **Health checks**: Automatic restart on failure
- **Resource limits**: CPU 500m / Memory 512MB per service
- **Networking**: Overlay network for inter-service communication
- **Restart policy**: Automatic restart with exponential backoff
- **Rolling updates**: Gradual deployment, automatic rollback on failure

### Deployment Steps

```bash
# 1. Build the image
docker build -t task-api:latest .

# 2. Create .env file with production secrets
cp .env.example .env
# Edit .env with strong passwords and JWT secret

# 3. Deploy the stack
docker stack deploy -c docker-stack.yml task-api

# 4. Check status
docker stack services task-api
docker stack ps task-api
```

### Common Operations

```bash
# View logs
docker service logs task-api_web

# Scale API (if needed)
docker service scale task-api_web=2

# Update image
docker service update --image task-api:new task-api_web

# Monitor resource usage
docker stats

# Remove stack
docker stack rm task-api
```

### Monitoring & Metrics
- Metrics available at: `http://localhost:5000/metrics`
- Integrate with Prometheus by scraping this endpoint
- Check logs: `docker service logs task-api_web`

---

## Kubernetes Deployment

### Prerequisites
1. Kubernetes cluster running (minikube, kind, managed service)
2. kubectl configured and authenticated
3. Image built and available: `docker build -t task-api:latest .`
4. For local development: `minikube start`

### What's Included in k8s/ Manifests
- **Namespace**: `task-api` for isolation
- **Secrets**: Database password, JWT key (update before deployment)
- **ConfigMap**: Application configuration
- **PersistentVolumeClaim**: 5GB storage for PostgreSQL
- **Deployments**: Postgres + API with 1 replica each
- **Services**: ClusterIP for Postgres, LoadBalancer for API
- **HPA**: Auto-scaling based on CPU/memory (1-3 replicas)
- **NetworkPolicy**: Security rules for pod communication
- **ServiceAccount**: RBAC for API pod

### Deployment Steps

```bash
# 1. Build image
docker build -t task-api:latest .

# 2. Update k8s/secret.yaml with production secrets
# IMPORTANT: Edit DATABASE_URL, JWT_SECRET_KEY with strong values

# 3. Deploy to cluster
bash k8s-deploy.sh

# Or apply manually:
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/postgres-service.yaml
kubectl apply -f k8s/postgres-deployment.yaml
kubectl apply -f k8s/api-service.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/network-policy.yaml
```

### Accessing the Application

```bash
# Port-forward to localhost
kubectl port-forward -n task-api svc/task-api 5000:80

# Access API
curl http://localhost:5000/health

# View metrics
curl http://localhost:5000/metrics
```

### Common Operations

```bash
# Check pod status
kubectl get pods -n task-api

# View pod logs
kubectl logs -n task-api -l app=task-api -f

# Describe pod (troubleshooting)
kubectl describe pod -n task-api <pod-name>

# Scale replicas
kubectl scale deployment task-api -n task-api --replicas=2

# View HPA status
kubectl get hpa -n task-api

# Check resource usage
kubectl top pods -n task-api

# Delete deployment
kubectl delete namespace task-api
```

### Monitoring & Metrics
- Metrics endpoint: `/metrics` (Prometheus format)
- HPA monitors CPU/memory and auto-scales
- Pod logs centralized via `kubectl logs`
- Integrate with Prometheus Operator for advanced monitoring

### Advanced: Cloud Providers

#### AWS EKS
```bash
# Create cluster
eksctl create cluster --name task-api --region us-east-1

# Deploy
bash k8s-deploy.sh
```

#### Azure AKS
```bash
# Create cluster
az aks create --resource-group mygroup --name task-api

# Get credentials
az aks get-credentials --resource-group mygroup --name task-api

# Deploy
bash k8s-deploy.sh
```

#### GCP GKE
```bash
# Create cluster
gcloud container clusters create task-api --zone us-central1-a

# Get credentials
gcloud container clusters get-credentials task-api

# Deploy
bash k8s-deploy.sh
```

---

## Production Checklist

- [ ] Update `DB_PASSWORD` to strong password (32+ chars, random)
- [ ] Update `JWT_SECRET_KEY` to strong secret (32+ chars, random)
- [ ] Configure backups for PostgreSQL PVC
- [ ] Set up monitoring (Prometheus, Grafana)
- [ ] Configure log aggregation (ELK, Loki)
- [ ] Set up CI/CD pipeline for image builds
- [ ] Enable TLS/HTTPS with ingress or load balancer
- [ ] Configure DNS/domain name
- [ ] Set resource requests/limits appropriately
- [ ] Test failover and recovery procedures
- [ ] Document rollback procedures
- [ ] Set up alerting for errors and slow requests

---

## Architecture Comparison

| Feature | Swarm | Kubernetes |
|---------|-------|-----------|
| Setup time | 5 min | 20 min |
| Learning curve | Easy | Steep |
| Scaling | Manual | Auto (HPA) |
| Self-healing | Yes | Yes |
| Multi-region | No | Yes |
| Best for | Small/medium | Enterprise |
| Cluster size | 1-10 nodes | 10+ nodes |

---

## Troubleshooting

### Swarm Issues
```bash
# Service not starting
docker service ls
docker service ps task-api_web

# Check logs
docker service logs task-api_web --follow

# Resource exhausted
docker node ls
docker stats
```

### Kubernetes Issues
```bash
# Pod stuck in Pending
kubectl describe pod -n task-api <pod-name>

# CrashLoopBackOff
kubectl logs -n task-api <pod-name>

# Service not accessible
kubectl get svc -n task-api
kubectl get endpoints -n task-api

# HPA not scaling
kubectl describe hpa -n task-api
kubectl get events -n task-api
```

---

## Next Steps

1. **Choose your platform**: Docker Swarm for simplicity, Kubernetes for scale
2. **Update secrets**: Edit `.env` and `k8s/secret.yaml` with real values
3. **Deploy**: Run `swarm-deploy.sh` or `k8s-deploy.sh`
4. **Monitor**: Set up Prometheus and Grafana
5. **Backup**: Configure automated database backups
6. **Scale**: Use HPA (Kubernetes) or manual scaling (Swarm) as needed
