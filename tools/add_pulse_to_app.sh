#!/bin/bash
# Add Pulse Network Monitoring to iOS App
# Automatically integrates Pulse into App file or AppDelegate

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

# Check arguments
if [ "$#" -lt 1 ]; then
    echo "Usage: $0 <app_file_path>"
    echo
    echo "Examples:"
    echo "  $0 MyApp/MyApp.swift               # SwiftUI App"
    echo "  $0 MyApp/AppDelegate.swift         # UIKit App"
    exit 1
fi

APP_FILE="$1"

# Check if file exists
if [ ! -f "$APP_FILE" ]; then
    print_error "File not found: $APP_FILE"
    exit 1
fi

# Check if Pulse is already imported
if grep -q "import Pulse" "$APP_FILE"; then
    print_warning "Pulse already imported in $APP_FILE"
    exit 0
fi

# Detect app type (SwiftUI vs UIKit)
if grep -q "@main" "$APP_FILE" && grep -q ": App" "$APP_FILE"; then
    APP_TYPE="swiftui"
elif grep -q "UIApplicationDelegate" "$APP_FILE"; then
    APP_TYPE="uikit"
else
    print_error "Could not detect app type. File must be a SwiftUI App or UIKit AppDelegate."
    exit 1
fi

print_info "Detected app type: $APP_TYPE"

# Backup original file
cp "$APP_FILE" "$APP_FILE.backup"
print_info "Created backup: $APP_FILE.backup"

# Add Pulse integration based on app type
if [ "$APP_TYPE" = "swiftui" ]; then
    # SwiftUI App integration
    print_info "Adding Pulse to SwiftUI App..."

    # Add import at top
    if ! grep -q "import Pulse" "$APP_FILE"; then
        # Find the line after "import SwiftUI" or first import
        IMPORT_LINE=$(grep -n "^import " "$APP_FILE" | tail -1 | cut -d: -f1)
        sed -i '' "${IMPORT_LINE}a\\
import Pulse
" "$APP_FILE"
    fi

    # Add init() with Pulse setup
    if ! grep -q "URLSessionProxyDelegate.enableAutomaticRegistration()" "$APP_FILE"; then
        # Find @main line
        MAIN_LINE=$(grep -n "@main" "$APP_FILE" | cut -d: -f1)
        # Find struct line after @main
        STRUCT_LINE=$(awk "NR>${MAIN_LINE} && /struct .*: App/ {print NR; exit}" "$APP_FILE")

        # Insert init after struct declaration
        sed -i '' "${STRUCT_LINE}a\\
\\
    init() {\\
        #if DEBUG\\
        // Enable Pulse network monitoring\\
        URLSessionProxyDelegate.enableAutomaticRegistration()\\
        \\
        // Enable 3-finger tap to show Pulse console\\
        LoggerStore.shared.makeCurrentConsoleGesture()\\
        \\
        print(\"📊 Pulse network monitoring enabled\")\\
        print(\"   3-finger tap anywhere to view network logs\")\\
        #endif\\
    }
" "$APP_FILE"
    fi

    print_success "Pulse integrated into SwiftUI App"

elif [ "$APP_TYPE" = "uikit" ]; then
    # UIKit AppDelegate integration
    print_info "Adding Pulse to UIKit AppDelegate..."

    # Add import at top
    if ! grep -q "import Pulse" "$APP_FILE"; then
        IMPORT_LINE=$(grep -n "^import " "$APP_FILE" | tail -1 | cut -d: -f1)
        sed -i '' "${IMPORT_LINE}a\\
import Pulse
" "$APP_FILE"
    fi

    # Add to didFinishLaunchingWithOptions
    if ! grep -q "URLSessionProxyDelegate.enableAutomaticRegistration()" "$APP_FILE"; then
        # Find didFinishLaunchingWithOptions method
        if grep -q "didFinishLaunchingWithOptions" "$APP_FILE"; then
            # Insert after method start
            FUNC_LINE=$(grep -n "didFinishLaunchingWithOptions" "$APP_FILE" | cut -d: -f1)
            # Find first line after {
            BRACE_LINE=$(awk "NR>${FUNC_LINE} && /{/ {print NR; exit}" "$APP_FILE")

            sed -i '' "${BRACE_LINE}a\\
\\
        #if DEBUG\\
        // Enable Pulse network monitoring\\
        URLSessionProxyDelegate.enableAutomaticRegistration()\\
        \\
        // Enable 3-finger tap to show Pulse console\\
        LoggerStore.shared.makeCurrentConsoleGesture()\\
        \\
        print(\"📊 Pulse network monitoring enabled\")\\
        print(\"   3-finger tap anywhere to view network logs\")\\
        #endif
" "$APP_FILE"

            print_success "Pulse integrated into AppDelegate"
        else
            print_warning "Could not find didFinishLaunchingWithOptions method"
            print_info "Add this code manually to your AppDelegate:"
            echo
            echo "  func application(_ application: UIApplication,"
            echo "                   didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {"
            echo "      #if DEBUG"
            echo "      URLSessionProxyDelegate.enableAutomaticRegistration()"
            echo "      LoggerStore.shared.makeCurrentConsoleGesture()"
            echo "      #endif"
            echo "      return true"
            echo "  }"
        fi
    fi
fi

# Display what was added
echo
print_success "Pulse integration complete!"
echo
print_info "What was added:"
echo "  1. ✅ Import Pulse framework"
echo "  2. ✅ Automatic URLSession request monitoring"
echo "  3. ✅ 3-finger tap gesture to view network logs"
echo "  4. ✅ DEBUG-only (zero production overhead)"
echo
print_info "Next steps:"
echo "  1. Build and run your app"
echo "  2. Make network requests"
echo "  3. Use 3-finger tap to view logs"
echo "  4. Export logs: ruby tools/pulse_log_export.rb export --app-id YOUR_BUNDLE_ID"
echo
print_info "Original file backed up to: $APP_FILE.backup"
