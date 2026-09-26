---
name: ios-device-deployment
description: Deploy iOS apps wirelessly to your physical iPhone via Tailscale (default) with automatic code signing
when: Deploying to physical device, testing on real iPhone, validating device-specific features, or preparing for App Store submission
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - mcp__xcodebuildmcp__build_sim
  - mcp__xcodebuildmcp__discover_tools
  - mcp__xcodebuildmcp__get_tools
---

# iOS Device Deployment Skill

## Purpose
Deploy iOS apps wirelessly to your physical iPhone for testing and development. Handles the full build-to-device workflow including code signing, wireless connection, and installation.

## Primary Agent
**📱 Mobile Developer** - This skill is designed for the Mobile Developer agent but can be invoked by {{ORCHESTRATOR_NAME}} when deployment is needed.

## Core Capabilities

### 1. Wireless Device Discovery
```bash
# List connected devices (both wired and wireless)
xcrun xctrace list devices

# More detailed device info
instruments -s devices

# Check if specific device is available
xcrun devicectl list devices
```

### 2. Device Connection Setup

**Requirements for wireless deployment (Tailscale preferred):**
- **Default: Tailscale** — iPhone and Mac both on Tailscale network (works from anywhere, not just same WiFi)
- Fallback: iPhone and Mac on same WiFi network
- Device previously connected via cable at least once
- "Connect via network" enabled in Xcode Devices window
- Device unlocked and trusted

**Tailscale setup:**
- Both devices must have Tailscale installed and signed in to same tailnet
- Device will appear via Tailscale IP in `xcrun devicectl list devices`
- More reliable than local network — no WiFi flakiness, works across networks

**Verify connection:**
```bash
# Modern approach (Xcode 15+)
xcrun devicectl list devices

# Check device state
xcrun devicectl device info --device <UDID>
```

### 3. Build for Physical Device

**Key differences from simulator builds:**
```bash
# Build for physical device (arm64)
xcodebuild -project YourApp.xcodeproj \
  -scheme YourApp \
  -configuration Debug \
  -destination 'platform=iOS,id=<DEVICE_UDID>' \
  -allowProvisioningUpdates \
  CODE_SIGN_STYLE=Automatic \
  DEVELOPMENT_TEAM=<TEAM_ID> \
  build

# Or using workspace
xcodebuild -workspace YourApp.xcworkspace \
  -scheme YourApp \
  -configuration Debug \
  -destination 'platform=iOS,id=<DEVICE_UDID>' \
  -allowProvisioningUpdates \
  build
```

### 4. Code Signing Essentials

**Automatic signing (preferred):**
```bash
# Let Xcode handle provisioning
-allowProvisioningUpdates \
CODE_SIGN_STYLE=Automatic \
DEVELOPMENT_TEAM=<TEAM_ID>
```

**Check signing identity:**
```bash
# List available signing identities
security find-identity -v -p codesigning

# Check provisioning profiles
ls -la ~/Library/MobileDevice/Provisioning\ Profiles/
```

### 5. Wireless Deployment

**Modern approach (Xcode 15+):**
```bash
# Install app to device
xcrun devicectl device install app \
  --device <DEVICE_UDID> \
  <PATH_TO_APP>

# Example with typical derived data path
xcrun devicectl device install app \
  --device <DEVICE_UDID> \
  ~/Library/Developer/Xcode/DerivedData/YourApp-*/Build/Products/Debug-iphoneos/YourApp.app
```

**Legacy approach (Xcode 14 and earlier):**
```bash
# Using ios-deploy (install if needed: brew install ios-deploy)
ios-deploy --bundle <PATH_TO_APP> --id <DEVICE_UDID>

# With debug mode
ios-deploy --debug --bundle <PATH_TO_APP> --id <DEVICE_UDID>
```

### 6. Launch App After Install

```bash
# Launch installed app
xcrun devicectl device process launch \
  --device <DEVICE_UDID> \
  <BUNDLE_IDENTIFIER>

# Example
xcrun devicectl device process launch \
  --device <DEVICE_UDID> \
  com.example.yourapp
```

## Complete Deployment Workflow

### Step 1: Discover Device
```bash
# Find the target iPhone on the network
xcrun devicectl list devices | grep iPhone
```

**Expected output pattern:**
```
iPhone (My iPhone) (00008XXX-XXXXXXXXXXXX) (network)
```

**Extract UDID from output for subsequent commands.**

### Step 2: Verify Device Ready
```bash
# Check device state
xcrun devicectl device info --device <UDID>
```

**Look for:**
- Connection Type: network
- Device State: unlocked or available
- OS Version: should match deployment target

### Step 3: Build for Device
```bash
# Navigate to project
cd /path/to/project

# Build (example using typical iOS project structure)
xcodebuild -workspace YourApp.xcworkspace \
  -scheme YourApp \
  -configuration Debug \
  -destination "platform=iOS,id=<UDID>" \
  -allowProvisioningUpdates \
  CODE_SIGN_STYLE=Automatic \
  clean build
```

**Monitor for:**
- Code signing success
- Build completion
- Archive location in output

### Step 4: Find Built App
```bash
# Typical location
find ~/Library/Developer/Xcode/DerivedData -name "YourApp.app" -type d | grep Debug-iphoneos
```

### Step 5: Deploy to Device
```bash
# Install app
xcrun devicectl device install app \
  --device <UDID> \
  <PATH_TO_APP>
```

### Step 6: Launch App
```bash
# Launch on device
xcrun devicectl device process launch \
  --device <UDID> \
  <BUNDLE_ID>
```

## Troubleshooting Guide

### Connection Issues

**Device not showing as network device:**
```bash
# 1. Verify both devices are on Tailscale (tailscale status)
# 2. If Tailscale unavailable, check device is on same WiFi as Mac
# 3. Try cable connection first, then disconnect
# 4. Check Xcode > Window > Devices and Simulators > "Connect via network" checkbox
```

**"Device not found" error:**
```bash
# Refresh device list
killall -9 com.apple.CoreSimulator.CoreSimulatorService
xcrun simctl list devices

# For physical devices, restart usbmuxd
sudo launchctl stop com.apple.usbmuxd
sudo launchctl start com.apple.usbmuxd
```

### Code Signing Issues

**"No signing identity found" error:**
```bash
# Check available identities
security find-identity -v -p codesigning

# If empty, need to install developer certificate from Apple Developer portal
# Or use Xcode: Preferences > Accounts > Download Manual Profiles
```

**"Provisioning profile doesn't match" error:**
```bash
# Use automatic provisioning
# Add to build command:
-allowProvisioningUpdates \
CODE_SIGN_STYLE=Automatic \
DEVELOPMENT_TEAM=<YOUR_TEAM_ID>
```

**Find your Team ID:**
```bash
# In Xcode, go to project settings > Signing & Capabilities > Team
# Or check Apple Developer portal
```

### Build Failures

**"arm64 architecture missing" error:**
```bash
# Ensure building for device, not simulator
# Check destination includes actual device UDID, not generic iOS
```

**"Unable to install" error:**
```bash
# 1. Check device storage space
# 2. Delete old version of app from device
# 3. Verify app bundle is complete:
ls -la <PATH_TO_APP>

# Should contain:
# - Info.plist
# - Executable binary
# - _CodeSignature directory
```

### Trust Issues

**"App from unidentified developer" on device:**
```bash
# On iPhone: Settings > General > VPN & Device Management
# Trust the developer certificate

# This happens on first install with new signing identity
# User must manually trust on device
```

## Owner-Specific Setup

**Device Information:**
- Need to discover UDID dynamically each session
- Device name pattern: Look for "iPhone" in device list
- Connection: **Default to Tailscale** for wireless deployment (works across networks). Fall back to local WiFi if Tailscale unavailable.

**Project Specifics:**
- Likely in Huxley capsule structure
- May use SwiftUI or UIKit
- Check for `.xcworkspace` vs `.xcodeproj`

**To discover the device setup dynamically:**
```bash
# 1. Find device
DEVICE_UDID=$(xcrun devicectl list devices | grep "iPhone" | grep -oE '[0-9a-fA-F-]{36,}' | head -1)

# 2. Find Xcode project in current directory
find . -name "*.xcworkspace" -o -name "*.xcodeproj" | head -1

# 3. Extract scheme from project
xcodebuild -list -workspace <WORKSPACE> 2>/dev/null | grep -A 100 "Schemes:" | grep -v "Schemes:" | head -1 | xargs
```

## Integration with ios-testing Skill

**Workflow separation:**
- **ios-device-deployment**: Build and deploy to physical device
- **ios-testing**: Run tests in simulator, check UI, verify functionality

**Combined usage:**
1. Use ios-testing for rapid iteration in simulator
2. Use ios-device-deployment for real-device validation
3. Use ios-testing for automated test suites
4. Use ios-device-deployment for final verification before release

## Advanced Features

### Debug on Device

```bash
# Install and attach debugger
xcrun devicectl device install app --device <UDID> <APP_PATH>
xcrun devicectl device process launch --device <UDID> <BUNDLE_ID> --attach-debugger
```

### View Device Logs

```bash
# Stream device logs
xcrun devicectl device log stream --device <UDID>

# Filter for specific app
xcrun devicectl device log stream --device <UDID> --predicate 'processImagePath CONTAINS "YourApp"'
```

### Take Device Screenshot

```bash
# Capture screenshot from device
xcrun devicectl device screenshot --device <UDID> screenshot.png
```

### Performance Testing

```bash
# Launch with instruments for profiling
instruments -w <UDID> -t "Time Profiler" <APP_PATH>
```

## Quick Reference Commands

```bash
# Discover device
xcrun devicectl list devices

# Build for device
xcodebuild -workspace App.xcworkspace -scheme App -destination "platform=iOS,id=<UDID>" -allowProvisioningUpdates build

# Install app
xcrun devicectl device install app --device <UDID> <APP_PATH>

# Launch app
xcrun devicectl device process launch --device <UDID> <BUNDLE_ID>

# Complete one-liner (after build)
APP_PATH=$(find ~/Library/Developer/Xcode/DerivedData -name "*.app" -type d | grep Debug-iphoneos | head -1) && \
xcrun devicectl device install app --device <UDID> "$APP_PATH" && \
xcrun devicectl device process launch --device <UDID> <BUNDLE_ID>
```

## Expected Usage Pattern

**Typical request:**
> "Deploy this to my iPhone"

**Agent response:**
1. Discover iPhone UDID on network
2. Identify Xcode project/workspace
3. Build for physical device with code signing
4. Deploy wirelessly to iPhone
5. Launch app on device
6. Report success/failure with screenshots if needed

**Autonomous execution - no asking {{USER_NAME}} to:**
- Unlock their phone (check if unlocked via devicectl)
- Connect via cable (use wireless)
- Run build manually (agent runs xcodebuild)
- Trust certificate (detect and instruct if needed)

## Cost Considerations
- No external API costs
- Uses local Xcode toolchain
- Network transfer minimal (app bundle typically <100MB)
- Build time depends on project size (typically 1-5 minutes)

## Success Criteria
- App appears on the iPhone home screen
- App launches without crashes
- Console confirms successful installation
- No code signing errors
- Wireless connection maintained throughout deployment
