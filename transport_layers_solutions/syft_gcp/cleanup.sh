#!/bin/bash
#
# Cleanup script for Syft GCP Transport Layer
# Disables all APIs used by the transport layer
#

set -e

PROJECT_ID="${1:-}"

if [ -z "$PROJECT_ID" ]; then
    echo "Usage: ./cleanup.sh PROJECT_ID"
    echo ""
    echo "Example: ./cleanup.sh my-syft-project"
    exit 1
fi

echo "🧹 Cleaning up GCP project: $PROJECT_ID"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install it first:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Disable APIs
echo "Disabling APIs..."

apis=(
    "gmail.googleapis.com"
    "sheets.googleapis.com"
    "drive.googleapis.com"
    "forms.googleapis.com"
)

for api in "${apis[@]}"; do
    echo -n "  - $api ... "
    if gcloud services disable "$api" --project="$PROJECT_ID" --quiet 2>/dev/null; then
        echo "✅ disabled"
    else
        echo "⚠️  (may not be enabled or permission denied)"
    fi
done

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "Note: This script only disables APIs. To fully clean up:"
echo "  1. Delete OAuth credentials at: https://console.cloud.google.com/apis/credentials?project=$PROJECT_ID"
echo "  2. Delete the project at: https://console.cloud.google.com/home/dashboard?project=$PROJECT_ID"
echo "  3. Clear local tokens: rm -rf ~/.syft-gcp/"
