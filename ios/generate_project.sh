#!/usr/bin/env bash
# Generate OrneryKiwi.xcodeproj from project.yml using xcodegen.
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v xcodegen &>/dev/null; then
    echo "xcodegen not found. Install with: brew install xcodegen"
    exit 1
fi

echo "Generating OrneryKiwi.xcodeproj..."
xcodegen generate --spec project.yml

echo ""
echo "Done. Open OrneryKiwi.xcodeproj in Xcode:"
echo "  open OrneryKiwi.xcodeproj"
echo ""
echo "Before building:"
echo "  1. Set your Development Team in Signing & Capabilities"
echo "  2. Confirm the App Group 'group.com.ornery-kiwi.shared' is registered"
echo "     for both targets in your Apple Developer account"
