#!/bin/bash
# Kubernetes deployment guide for task-api

echo "=== Kubernetes Deployment Guide ==="
echo ""
echo "Prerequisites:"
echo "1. kubectl installed and configured"
echo "2. Kubernetes cluster running (minikube, kind, or managed cluster)"
echo "3. Docker image built: docker build -t task-api:latest ."
echo "4. Update secrets in k8s/secret.yaml with real values"
echo ""

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl."
    exit 1
fi

# Check if cluster is reachable
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cannot connect to Kubernetes cluster"
    echo "Make sure your cluster is running and kubeconfig is configured"
    exit 1
fi

echo "✓ kubectl is available and cluster is reachable"
echo ""

# Create namespace
echo "Creating namespace 'task-api'..."
kubectl create namespace task-api --dry-run=client -o yaml | kubectl apply -f -

# Apply configurations
echo "Applying ConfigMap and Secrets..."
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml

echo "Applying PersistentVolumeClaim..."
kubectl apply -f k8s/pvc.yaml

echo "Applying ServiceAccount..."
kubectl apply -f k8s/serviceaccount.yaml

echo "Deploying PostgreSQL..."
kubectl apply -f k8s/postgres-service.yaml
kubectl apply -f k8s/postgres-deployment.yaml

echo "Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres -n task-api --timeout=300s

echo "Deploying Task API..."
kubectl apply -f k8s/api-service.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/hpa.yaml
kubectl apply -f k8s/network-policy.yaml

echo ""
echo "✓ All resources deployed!"
echo ""
echo "Useful commands:"
echo "  # Check pod status"
echo "  kubectl get pods -n task-api"
echo ""
echo "  # View pod logs"
echo "  kubectl logs -n task-api -l app=task-api -f"
echo ""
echo "  # Port forward to access API locally"
echo "  kubectl port-forward -n task-api svc/task-api 5000:80"
echo ""
echo "  # Get service endpoints"
echo "  kubectl get svc -n task-api"
echo ""
echo "  # Scale replicas"
echo "  kubectl scale deployment task-api -n task-api --replicas=2"
echo ""
echo "  # View HPA status"
echo "  kubectl get hpa -n task-api"
echo ""
echo "  # Delete deployment"
echo "  kubectl delete namespace task-api"
echo ""
echo "Access the API:"
echo "  # Using port-forward:"
echo "  kubectl port-forward -n task-api svc/task-api 5000:80"
echo "  http://localhost:5000"
echo ""
echo "View metrics:"
echo "  # Using port-forward:"
echo "  kubectl port-forward -n task-api svc/task-api 5000:80"
echo "  http://localhost:5000/metrics"
