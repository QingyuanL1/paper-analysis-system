#!/bin/bash

echo "Paper Analysis System Docker Build & Deploy Script"
echo "================================================="

IMAGE_NAME="paper-analysis-system"
CONTAINER_NAME="paper-analysis-system"
PORT=5002

echo "1. Checking for running containers with the same name..."
if [ "$(docker ps -q -f name=${CONTAINER_NAME})" ]; then
    echo "   Found running container, stopping it..."
    docker stop ${CONTAINER_NAME}
    echo "   Container stopped"
fi

echo "2. Checking for existing containers with the same name..."
if [ "$(docker ps -a -q -f name=${CONTAINER_NAME})" ]; then
    echo "   Found existing container, removing it..."
    docker rm ${CONTAINER_NAME}
    echo "   Container removed"
fi

echo "3. Building Docker image..."
docker build -t ${IMAGE_NAME}:latest .

if [ $? -eq 0 ]; then
    echo "   Image built successfully"
    
    echo "4. Starting container..."
    docker run -d -p ${PORT}:${PORT} -v $(pwd):/app --name ${CONTAINER_NAME} ${IMAGE_NAME}:latest
    
    if [ $? -eq 0 ]; then
        echo "   Container started successfully"
        echo "5. Container status:"
        docker ps -f name=${CONTAINER_NAME}
        
        echo ""
        echo "System successfully deployed!"
        echo "Access it at http://localhost:${PORT}"
    else
        echo "   Container failed to start, check logs"
    fi
else
    echo "   Image build failed, check Dockerfile and dependencies"
fi 