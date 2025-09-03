#!/bin/bash


# Function to validate URL
validate_url() {
    local url=$1
    local name=$2

    # Check if URL is empty or contains 'null'
    if [ -z "$url" ] || [[ "$url" == *"null"* ]]; then
        echo "❌ $name URL is invalid: $url"
        return 1
    fi
    echo "✅ $name URL is valid"
    return 0
}

# Set namespace - use NAMESPACE env var if set, otherwise use current project
if [ -z "$NAMESPACE" ]; then
    NAMESPACE=$(oc project -q 2>/dev/null)
    if [ -z "$NAMESPACE" ]; then
        echo "❌ Error: Unable to determine current namespace. Please set NAMESPACE environment variable or ensure you're logged into OpenShift."
        exit 1
    fi
    echo "ℹ️  Using current namespace: $NAMESPACE"
else
    echo "ℹ️  Using specified namespace: $NAMESPACE"
fi

# Get URLs dynamically using the namespace
export TEST_FRONTEND_URL=$(oc get routes product-recommender-system-frontend -n "$NAMESPACE" -o json | jq -r '"https://" + .spec.host')
export TEST_FEAST_URL=$(oc get routes feast-feast-recommendation-ui -n "$NAMESPACE" -o json | jq -r '"https://" + .spec.host')

# Generate unique timestamp for test emails
export TEST_TIMESTAMP=$(date +%s)

echo "Testing with:"
echo "Namespace: $NAMESPACE"
echo "Frontend URL: $TEST_FRONTEND_URL"
echo "Feast URL: $TEST_FEAST_URL"
echo ""

# Validate critical URLs (Frontend and Backend)
echo "Validating URLs..."
validate_url "$TEST_FRONTEND_URL" "Frontend"
frontend_valid=$?

validate_url "$TEST_FEAST_URL" "Feast"
feast_valid=$?

# Exit if either critical URL is invalid
if [ $frontend_valid -ne 0 ] || [ $feast_valid -ne 0 ]; then
    echo "ERROR: One or more critical URLs are invalid. Exiting."
    exit 1
fi

echo "All critical URLs validated successfully. Starting tests..."
echo ""

# Determine test target
if [ -n "$1" ]; then
    # Specific test file provided
    TEST_TARGET="$1"
    if [ ! -f "$TEST_TARGET" ]; then
        echo "❌ Test file not found: $TEST_TARGET"
        exit 1
    fi
    echo "Running specific test: $TEST_TARGET"
else
    # Run all tests in current directory
    TEST_TARGET="."
    echo "Running all tests in current directory"
fi

echo ""

# Run pytest with the determined target and capture exit code
PYTHONPATH=. pytest "$TEST_TARGET" -v
PYTEST_EXIT_CODE=$?

echo ""
echo "Pytest exit code: $PYTEST_EXIT_CODE"

if [ $PYTEST_EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed successfully!"
    exit 0
elif [ $PYTEST_EXIT_CODE -eq 1 ]; then
    echo "❌ Some tests failed"
    exit 1
elif [ $PYTEST_EXIT_CODE -eq 2 ]; then
    echo "⚠️  Test execution was interrupted"
    exit 2
elif [ $PYTEST_EXIT_CODE -eq 3 ]; then
    echo "💥 Internal pytest error occurred"
    exit 3
elif [ $PYTEST_EXIT_CODE -eq 4 ]; then
    echo "🚫 Pytest was misused"
    exit 4
elif [ $PYTEST_EXIT_CODE -eq 5 ]; then
    echo "📭 No tests were collected"
    exit 5
else
    echo "❓ Unknown pytest exit code: $PYTEST_EXIT_CODE"
    exit $PYTEST_EXIT_CODE
fi
