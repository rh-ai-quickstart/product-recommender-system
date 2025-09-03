podman build -t quay.io/rh-ai-quickstart/product-recommender-testing:latest -f tester/Containerfile .
podman push quay.io/rh-ai-quickstart/product-recommender-testing:latest
