#!/bin/bash
# Docker Swarm deployment guide for task-api

echo "=== Docker Swarm Deployment Guide ==="
echo ""
echo "Prerequisites:"
echo "1. Docker installed with Swarm mode enabled"
echo "2. .env file with DB_PASSWORD and JWT_SECRET_KEY configured"
echo ""

# Check if swarm is initialized
if ! docker info | grep -q "Swarm: active"; then
    echo "❌ Docker Swarm is not active"
    echo "Initialize Swarm with: docker swarm init"
    exit 1
fi

echo "✓ Docker Swarm is active"
echo ""

# Deploy the stack
echo "Deploying task-api stack..."
docker stack deploy -c docker-stack.yml task-api

echo ""
echo "✓ Stack deployed successfully!"
echo ""
echo "Useful commands:"
echo "  # View stack services"
echo "  docker stack services task-api"
echo ""
echo "  # View task logs"
echo "  docker service logs task-api_web"
echo ""
echo "  # Scale API replicas"
echo "  docker service scale task-api_web=2"
echo ""
echo "  # Update service"
echo "  docker service update --image task-api:new task-api_web"
echo ""
echo "  # Remove stack"
echo "  docker stack rm task-api"
echo ""
echo "Access the API:"
echo "  http://localhost:5000"
echo ""
echo "View metrics:"
echo "  http://localhost:5000/metrics"
