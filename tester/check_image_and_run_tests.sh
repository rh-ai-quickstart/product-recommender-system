#!/bin/bash

set -e

echo "=== Product Recommender System - Image Change Detection and Testing ==="
TIMESTAMP=$(date +%s)
echo $TIMESTAMP
echo ""

# Function to get image digest
get_image_digest() {
    local image=$1

    # Try skopeo first (more efficient)
    if command -v skopeo &> /dev/null; then
        skopeo inspect --format "{{.Digest}}" docker://$image 2>/dev/null
    else
        # Fallback: use docker manifest inspect if available
        docker manifest inspect $image | jq -r '.config.digest' 2>/dev/null
    fi
}

# Function to store digest in a configmap
store_digest() {
    local digest=$1
    local configmap_name="frontend-backend-image-digest"
    local namespace=${NAMESPACE:-"product-recommender-testing"}

    echo "Storing digest: $digest"
    oc patch configmap $configmap_name -n $namespace --type='merge' -p="{\"data\":{\"digest\":\"$digest\"}}"
}

# Function to get stored digest
get_stored_digest() {
    local configmap_name="frontend-backend-image-digest"
    local namespace=${NAMESPACE:-"product-recommender-testing"}

    oc get configmap $configmap_name -n $namespace -o jsonpath='{.data.digest}' 2>/dev/null || echo ""
}

# Function to ensure cleanup always happens
cleanup_and_exit() {
    local original_exit_code=${1:-0}
    echo ""
    echo "=== CLEANUP: Ensuring system uninstall ==="
    if [ ! -z "$TESTING_NAMESPACE" ]; then
        echo "Uninstalling from namespace: $TESTING_NAMESPACE"
        cd /app/helm
        make SHELL=/bin/bash uninstall NAMESPACE=$TESTING_NAMESPACE || echo "⚠️  Uninstall had some issues"
        echo "✅ Cleanup completed"
    fi
    echo "=== Workflow Complete ==="
    echo "Original exit code would have been: $original_exit_code"
    echo "Exiting gracefully with code: 0"
    exit 0
}

# Target image to monitor
TARGET_IMAGE="quay.io/rh-ai-quickstart/product-recommender-frontend-backend:latest"

echo "=== Step 1: Checking for Image Changes ==="
echo "Monitoring image: $TARGET_IMAGE"

# Get current image digest
echo "Getting digest for image: $TARGET_IMAGE"
CURRENT_DIGEST=$(get_image_digest $TARGET_IMAGE)
echo "Current digest: $CURRENT_DIGEST"

# Get stored digest
STORED_DIGEST=$(get_stored_digest)
echo "Stored digest: $STORED_DIGEST"

# Compare digests
if [ "$CURRENT_DIGEST" = "$STORED_DIGEST" ] && [ -n "$STORED_DIGEST" ]; then
    echo "✅ No change detected in frontend-backend image. Skipping tests."
    echo "=== Workflow Complete ==="
    exit 0
else
    echo "🔄 Change detected in frontend-backend image. Running tests."
    # Store new digest
    store_digest "$CURRENT_DIGEST"

    # Set up trap for cleanup only when we're actually running tests
    trap 'cleanup_and_exit 1' INT TERM EXIT
fi

echo ""

# Step 2: Create testing namespace if it doesn't exist
echo "=== Step 2: Creating Testing Namespace ==="
# Use shorter namespace name to avoid route hostname length issues
TESTING_NAMESPACE="pr-test-$(date +%m%d-%H%M)"
echo "Creating namespace: $TESTING_NAMESPACE"
oc create namespace $TESTING_NAMESPACE || echo "Namespace $TESTING_NAMESPACE already exists or creation failed"
oc label namespace $TESTING_NAMESPACE modelmesh-enabled=false || true
echo "✅ Testing namespace ready: $TESTING_NAMESPACE"
echo ""

# Step 3: Install the system
echo "=== Step 3: Installing Product Recommender System ==="
cd /app/helm
if ! make SHELL=/bin/bash install NAMESPACE=$TESTING_NAMESPACE minio.userId=minio minio.password=minio123; then
    echo "❌ Installation failed"
    curl -X POST -H 'Content-type: application/json' --data "{\"text\": "❌ Prouduct recommender system installation failed at $TIMESTAMP ❌"}" $SLACK_WEBHOOK
    cleanup_and_exit 1
fi

# Wait 3 minutes for the pipeline to finish
sleep 180
echo "✅ Installation completed successfully"
echo ""

# Step 4: Run integration tests
echo "=== Step 4: Running Integration Tests ==="
cd /app/tests/integration

# Run integration tests, display in real-time, and capture output
echo "Running integration tests and capturing output..."
TEST_OUTPUT=$(NAMESPACE=rec-sys-ofridman bash run_integration_tests.sh 2>&1 | tee /dev/stdout)
TEST_EXIT_CODE=${PIPESTATUS[0]}

# Send output to Slack
echo "Sending test results to Slack..."
# Escape the output for JSON and create a proper payload
ESCAPED_OUTPUT=$(echo "$TEST_OUTPUT" | jq -Rs .)
curl -X POST -H 'Content-type: application/json' --data "{\"text\": $ESCAPED_OUTPUT}" $SLACK_WEBHOOK

# Check if tests failed
if [ $TEST_EXIT_CODE -ne 0 ]; then
    {
        echo "❌ Integration tests failed to run"
        cleanup_and_exit $TEST_EXIT_CODE
    }
else
    echo "✅ Integration tests completed successfully"
fi

# Step 5: Uninstall the system
trap - INT TERM EXIT

cleanup_and_exit 0
