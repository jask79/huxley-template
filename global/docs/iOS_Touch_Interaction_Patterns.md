# iOS Touch & Gesture Interaction Patterns

**Complete reference for handling touch interactions and gestures in iOS apps**

---

## Overview

Touch interactions are the foundation of iOS interfaces. This guide covers everything from basic taps to complex multi-touch gestures, providing patterns for SwiftUI and UIKit.

**Key Principles:**
- **Responsive** - Immediate visual feedback (<100ms)
- **Predictable** - Follow platform conventions
- **Forgiving** - Large touch targets (44pt minimum)
- **Discoverable** - Clear affordances for interactive elements
- **Accessible** - VoiceOver and Switch Control support

---

## Table of Contents

1. [SwiftUI Gestures](#swiftui-gestures)
2. [UIKit Gesture Recognizers](#uikit-gesture-recognizers)
3. [Gesture Composition](#gesture-composition)
4. [Custom Gestures](#custom-gestures)
5. [Hit Testing](#hit-testing)
6. [Haptic Feedback](#haptic-feedback)
7. [Accessibility](#accessibility)
8. [Touch Target Guidelines](#touch-target-guidelines)
9. [Advanced Patterns](#advanced-patterns)
10. [iPad Pointer, Pencil & Hover Interactions](#ipad-pointer-pencil--hover-interactions)
11. [iPad Keyboard Interactions](#ipad-keyboard-interactions)

---

## SwiftUI Gestures

### Tap Gestures

**Single Tap:**
```swift
struct TapExample: View {
    @State private var tapCount = 0

    var body: some View {
        Text("Tap count: \(tapCount)")
            .padding()
            .background(Color.blue)
            .cornerRadius(10)
            .onTapGesture {
                tapCount += 1
            }
    }
}
```

**Double Tap:**
```swift
struct DoubleTapExample: View {
    @State private var isLiked = false

    var body: some View {
        Image(systemName: isLiked ? "heart.fill" : "heart")
            .font(.system(size: 60))
            .foregroundColor(isLiked ? .red : .gray)
            .onTapGesture(count: 2) {
                withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
                    isLiked.toggle()
                }
            }
    }
}
```

**Tap with Location:**
```swift
struct TapLocationExample: View {
    @State private var tapLocation: CGPoint?

    var body: some View {
        Rectangle()
            .fill(Color.blue.opacity(0.3))
            .frame(width: 300, height: 300)
            .overlay(
                Circle()
                    .fill(Color.red)
                    .frame(width: 20, height: 20)
                    .position(tapLocation ?? CGPoint(x: 150, y: 150))
            )
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onEnded { value in
                        tapLocation = value.location
                    }
            )
    }
}
```

### Long Press Gesture

**Basic Long Press:**
```swift
struct LongPressExample: View {
    @State private var isPressed = false

    var body: some View {
        RoundedRectangle(cornerRadius: 10)
            .fill(isPressed ? Color.green : Color.blue)
            .frame(width: 200, height: 100)
            .onLongPressGesture(minimumDuration: 0.5) {
                withAnimation {
                    isPressed.toggle()
                }
            }
    }
}
```

**Long Press with Progress:**
```swift
struct LongPressProgressExample: View {
    @GestureState private var isDetectingLongPress = false
    @State private var completedLongPress = false

    var longPress: some Gesture {
        LongPressGesture(minimumDuration: 1.0)
            .updating($isDetectingLongPress) { currentState, gestureState, transaction in
                gestureState = currentState
            }
            .onEnded { _ in
                completedLongPress = true
            }
    }

    var body: some View {
        Circle()
            .fill(completedLongPress ? Color.green : (isDetectingLongPress ? Color.yellow : Color.blue))
            .frame(width: 100, height: 100)
            .scaleEffect(isDetectingLongPress ? 1.1 : 1.0)
            .animation(.easeInOut(duration: 0.2), value: isDetectingLongPress)
            .gesture(longPress)
    }
}
```

### Drag Gesture

**Basic Drag:**
```swift
struct DragExample: View {
    @State private var offset = CGSize.zero

    var body: some View {
        Circle()
            .fill(Color.blue)
            .frame(width: 100, height: 100)
            .offset(offset)
            .gesture(
                DragGesture()
                    .onChanged { value in
                        offset = value.translation
                    }
                    .onEnded { _ in
                        withAnimation(.spring()) {
                            offset = .zero
                        }
                    }
            )
    }
}
```

**Drag with Velocity:**
```swift
struct DragWithVelocityExample: View {
    @State private var position = CGPoint(x: 150, y: 150)

    var body: some View {
        Circle()
            .fill(Color.blue)
            .frame(width: 50, height: 50)
            .position(position)
            .gesture(
                DragGesture()
                    .onChanged { value in
                        position = value.location
                    }
                    .onEnded { value in
                        // Calculate velocity
                        let velocity = CGPoint(
                            x: value.predictedEndLocation.x - value.location.x,
                            y: value.predictedEndLocation.y - value.location.y
                        )

                        // Animate to predicted end location
                        withAnimation(.interpolatingSpring(stiffness: 50, damping: 10)) {
                            position = value.predictedEndLocation
                        }
                    }
            )
    }
}
```

**Constrained Drag (Slider):**
```swift
struct CustomSlider: View {
    @State private var value: CGFloat = 0.5
    let width: CGFloat = 300

    var body: some View {
        ZStack(alignment: .leading) {
            // Track
            Capsule()
                .fill(Color.gray.opacity(0.3))
                .frame(width: width, height: 8)

            // Thumb
            Circle()
                .fill(Color.blue)
                .frame(width: 28, height: 28)
                .offset(x: value * (width - 28))
                .gesture(
                    DragGesture()
                        .onChanged { gesture in
                            let newValue = (gesture.location.x / width).clamped(to: 0...1)
                            value = newValue
                        }
                )
        }
    }
}

extension Comparable {
    func clamped(to limits: ClosedRange<Self>) -> Self {
        return min(max(self, limits.lowerBound), limits.upperBound)
    }
}
```

### Magnification Gesture (Pinch to Zoom)

**Basic Zoom:**
```swift
struct ZoomExample: View {
    @State private var scale: CGFloat = 1.0

    var body: some View {
        Image(systemName: "photo")
            .font(.system(size: 100))
            .scaleEffect(scale)
            .gesture(
                MagnificationGesture()
                    .onChanged { value in
                        scale = value
                    }
                    .onEnded { _ in
                        withAnimation(.spring()) {
                            scale = max(1.0, min(scale, 3.0))
                        }
                    }
            )
    }
}
```

**Zoom with Limits:**
```swift
struct LimitedZoomExample: View {
    @State private var currentScale: CGFloat = 1.0
    @State private var finalScale: CGFloat = 1.0

    var body: some View {
        Image("photo")
            .scaleEffect(currentScale * finalScale)
            .gesture(
                MagnificationGesture()
                    .onChanged { value in
                        currentScale = value
                    }
                    .onEnded { value in
                        finalScale *= currentScale
                        finalScale = min(max(finalScale, 1.0), 5.0)  // Clamp 1x-5x
                        currentScale = 1.0
                    }
            )
            .onTapGesture(count: 2) {
                withAnimation(.spring()) {
                    finalScale = finalScale > 1.0 ? 1.0 : 2.0
                }
            }
    }
}
```

### Rotation Gesture

**Basic Rotation:**
```swift
struct RotationExample: View {
    @State private var angle: Angle = .zero

    var body: some View {
        RoundedRectangle(cornerRadius: 20)
            .fill(Color.blue)
            .frame(width: 150, height: 100)
            .rotationEffect(angle)
            .gesture(
                RotationGesture()
                    .onChanged { value in
                        angle = value
                    }
                    .onEnded { _ in
                        withAnimation(.spring()) {
                            // Snap to nearest 45 degrees
                            let degrees = angle.degrees
                            let snapped = round(degrees / 45) * 45
                            angle = .degrees(snapped)
                        }
                    }
            )
    }
}
```

### Simultaneous Gestures

**Pan + Zoom + Rotate:**
```swift
struct MultiGestureExample: View {
    @State private var offset = CGSize.zero
    @State private var scale: CGFloat = 1.0
    @State private var rotation: Angle = .zero

    var body: some View {
        Image("photo")
            .offset(offset)
            .scaleEffect(scale)
            .rotationEffect(rotation)
            .gesture(
                DragGesture()
                    .onChanged { value in
                        offset = value.translation
                    }
            )
            .gesture(
                MagnificationGesture()
                    .onChanged { value in
                        scale = value
                    }
            )
            .gesture(
                RotationGesture()
                    .onChanged { value in
                        rotation = value
                    }
            )
    }
}
```

---

## UIKit Gesture Recognizers

### Tap Gesture Recognizer

**Single Tap:**
```swift
let tapGesture = UITapGestureRecognizer(target: self, action: #selector(handleTap))
view.addGestureRecognizer(tapGesture)

@objc func handleTap(_ gesture: UITapGestureRecognizer) {
    let location = gesture.location(in: view)
    print("Tapped at: \(location)")
}
```

**Double Tap:**
```swift
let doubleTap = UITapGestureRecognizer(target: self, action: #selector(handleDoubleTap))
doubleTap.numberOfTapsRequired = 2
view.addGestureRecognizer(doubleTap)

@objc func handleDoubleTap(_ gesture: UITapGestureRecognizer) {
    UIView.animate(withDuration: 0.3) {
        self.imageView.transform = self.imageView.transform == .identity
            ? CGAffineTransform(scaleX: 2.0, y: 2.0)
            : .identity
    }
}
```

### Long Press Gesture Recognizer

**Basic Long Press:**
```swift
let longPress = UILongPressGestureRecognizer(target: self, action: #selector(handleLongPress))
longPress.minimumPressDuration = 0.5
view.addGestureRecognizer(longPress)

@objc func handleLongPress(_ gesture: UILongPressGestureRecognizer) {
    switch gesture.state {
    case .began:
        print("Long press began")
        UIView.animate(withDuration: 0.2) {
            gesture.view?.transform = CGAffineTransform(scaleX: 1.1, y: 1.1)
        }

    case .ended, .cancelled:
        print("Long press ended")
        UIView.animate(withDuration: 0.2) {
            gesture.view?.transform = .identity
        }

    default:
        break
    }
}
```

### Pan Gesture Recognizer

**Draggable View:**
```swift
let panGesture = UIPanGestureRecognizer(target: self, action: #selector(handlePan))
view.addGestureRecognizer(panGesture)

@objc func handlePan(_ gesture: UIPanGestureRecognizer) {
    let translation = gesture.translation(in: view.superview)

    switch gesture.state {
    case .changed:
        gesture.view?.center = CGPoint(
            x: gesture.view!.center.x + translation.x,
            y: gesture.view!.center.y + translation.y
        )
        gesture.setTranslation(.zero, in: view.superview)

    case .ended:
        let velocity = gesture.velocity(in: view.superview)

        // Animate to rest position with velocity
        UIView.animate(
            withDuration: 0.6,
            delay: 0,
            usingSpringWithDamping: 0.7,
            initialSpringVelocity: velocity.magnitude / 1000,
            options: [],
            animations: {
                gesture.view?.center = self.view.center
            }
        )

    default:
        break
    }
}

extension CGPoint {
    var magnitude: CGFloat {
        sqrt(x * x + y * y)
    }
}
```

### Pinch Gesture Recognizer

**Zoom Image:**
```swift
let pinchGesture = UIPinchGestureRecognizer(target: self, action: #selector(handlePinch))
imageView.addGestureRecognizer(pinchGesture)

@objc func handlePinch(_ gesture: UIPinchGestureRecognizer) {
    switch gesture.state {
    case .changed:
        let scale = gesture.scale
        gesture.view?.transform = gesture.view!.transform.scaledBy(x: scale, y: scale)
        gesture.scale = 1.0

    case .ended:
        // Constrain scale
        let currentScale = gesture.view!.transform.scaleValue
        let clampedScale = min(max(currentScale, 1.0), 5.0)

        UIView.animate(withDuration: 0.3) {
            gesture.view?.transform = CGAffineTransform(scaleX: clampedScale, y: clampedScale)
        }

    default:
        break
    }
}

extension CGAffineTransform {
    var scaleValue: CGFloat {
        return sqrt(a * a + c * c)
    }
}
```

### Rotation Gesture Recognizer

**Rotate View:**
```swift
let rotationGesture = UIRotationGestureRecognizer(target: self, action: #selector(handleRotation))
view.addGestureRecognizer(rotationGesture)

@objc func handleRotation(_ gesture: UIRotationGestureRecognizer) {
    switch gesture.state {
    case .changed:
        gesture.view?.transform = gesture.view!.transform.rotated(by: gesture.rotation)
        gesture.rotation = 0

    case .ended:
        // Snap to nearest 45 degrees
        let currentRotation = atan2(gesture.view!.transform.b, gesture.view!.transform.a)
        let snappedRotation = round(currentRotation / (.pi / 4)) * (.pi / 4)

        UIView.animate(withDuration: 0.3, delay: 0, usingSpringWithDamping: 0.7, initialSpringVelocity: 0) {
            gesture.view?.transform = CGAffineTransform(rotationAngle: snappedRotation)
        }

    default:
        break
    }
}
```

### Swipe Gesture Recognizer

**Swipe to Delete:**
```swift
let swipeLeft = UISwipeGestureRecognizer(target: self, action: #selector(handleSwipe))
swipeLeft.direction = .left
view.addGestureRecognizer(swipeLeft)

let swipeRight = UISwipeGestureRecognizer(target: self, action: #selector(handleSwipe))
swipeRight.direction = .right
view.addGestureRecognizer(swipeRight)

@objc func handleSwipe(_ gesture: UISwipeGestureRecognizer) {
    let direction = gesture.direction

    UIView.animate(withDuration: 0.3) {
        if direction == .left {
            gesture.view?.center.x -= self.view.bounds.width
        } else if direction == .right {
            gesture.view?.center.x += self.view.bounds.width
        }
    } completion: { _ in
        gesture.view?.removeFromSuperview()
    }
}
```

---

## Gesture Composition

### SwiftUI Gesture Composition

**Exclusive (Only One Wins):**
```swift
struct ExclusiveGestureExample: View {
    @State private var action = ""

    var body: some View {
        Rectangle()
            .fill(Color.blue)
            .frame(width: 200, height: 200)
            .gesture(
                TapGesture()
                    .onEnded { _ in action = "Tapped" }
                    .exclusively(before:
                        LongPressGesture()
                            .onEnded { _ in action = "Long Pressed" }
                    )
            )
            .overlay(Text(action))
    }
}
```

**Simultaneous (Both Fire):**
```swift
struct SimultaneousGestureExample: View {
    @State private var offset = CGSize.zero
    @State private var scale: CGFloat = 1.0

    var body: some View {
        Circle()
            .fill(Color.blue)
            .frame(width: 100, height: 100)
            .scaleEffect(scale)
            .offset(offset)
            .gesture(
                DragGesture()
                    .onChanged { value in
                        offset = value.translation
                    }
                    .simultaneously(with:
                        MagnificationGesture()
                            .onChanged { value in
                                scale = value
                            }
                    )
            )
    }
}
```

**Sequenced (One After Another):**
```swift
struct SequencedGestureExample: View {
    @State private var isUnlocked = false

    var body: some View {
        Rectangle()
            .fill(isUnlocked ? Color.green : Color.red)
            .frame(width: 200, height: 200)
            .gesture(
                LongPressGesture(minimumDuration: 1.0)
                    .sequenced(before:
                        DragGesture()
                            .onEnded { _ in
                                isUnlocked = true
                            }
                    )
            )
            .overlay(Text(isUnlocked ? "Unlocked" : "Hold and Drag"))
    }
}
```

### UIKit Gesture Composition

**Require Other Gesture to Fail:**
```swift
let singleTap = UITapGestureRecognizer(target: self, action: #selector(handleSingleTap))
let doubleTap = UITapGestureRecognizer(target: self, action: #selector(handleDoubleTap))
doubleTap.numberOfTapsRequired = 2

// Single tap only fires if double tap fails
singleTap.require(toFail: doubleTap)

view.addGestureRecognizer(singleTap)
view.addGestureRecognizer(doubleTap)
```

**Simultaneous Recognition (Delegate):**
```swift
class ViewController: UIViewController, UIGestureRecognizerDelegate {
    override func viewDidLoad() {
        super.viewDidLoad()

        let pan = UIPanGestureRecognizer(target: self, action: #selector(handlePan))
        pan.delegate = self

        let pinch = UIPinchGestureRecognizer(target: self, action: #selector(handlePinch))
        pinch.delegate = self

        view.addGestureRecognizer(pan)
        view.addGestureRecognizer(pinch)
    }

    func gestureRecognizer(
        _ gestureRecognizer: UIGestureRecognizer,
        shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer
    ) -> Bool {
        return true  // Allow both pan and pinch simultaneously
    }
}
```

---

## Custom Gestures

### SwiftUI Custom Gesture

**Circular Drag Gesture:**
```swift
struct CircularDragGesture: Gesture {
    @Binding var angle: Angle
    let radius: CGFloat

    func body(content: Content) -> some Gesture {
        DragGesture()
            .onChanged { value in
                let vector = CGVector(dx: value.location.x - radius, dy: value.location.y - radius)
                let angleRadians = atan2(vector.dy, vector.dx)
                angle = Angle(radians: Double(angleRadians))
            }
    }
}

// Usage
struct CircularSlider: View {
    @State private var angle: Angle = .zero
    let radius: CGFloat = 100

    var body: some View {
        ZStack {
            Circle()
                .stroke(Color.gray, lineWidth: 4)
                .frame(width: radius * 2, height: radius * 2)

            Circle()
                .fill(Color.blue)
                .frame(width: 30, height: 30)
                .offset(x: cos(angle.radians) * radius, y: sin(angle.radians) * radius)
                .gesture(
                    DragGesture()
                        .onChanged { value in
                            let vector = CGVector(
                                dx: value.location.x - radius,
                                dy: value.location.y - radius
                            )
                            let angleRadians = atan2(vector.dy, vector.dx)
                            angle = Angle(radians: Double(angleRadians))
                        }
                )
        }
    }
}
```

### UIKit Custom Gesture Recognizer

**Directional Pan Gesture:**
```swift
class DirectionalPanGestureRecognizer: UIPanGestureRecognizer {
    enum Direction {
        case horizontal, vertical
    }

    var direction: Direction = .horizontal

    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent) {
        super.touchesMoved(touches, with: event)

        if state == .began {
            let velocity = self.velocity(in: view)

            // Determine if gesture is horizontal or vertical
            if abs(velocity.x) > abs(velocity.y) {
                direction = .horizontal
            } else {
                direction = .vertical
            }
        }
    }
}

// Usage
let directionalPan = DirectionalPanGestureRecognizer(target: self, action: #selector(handleDirectionalPan))
view.addGestureRecognizer(directionalPan)

@objc func handleDirectionalPan(_ gesture: DirectionalPanGestureRecognizer) {
    let translation = gesture.translation(in: view)

    switch gesture.direction {
    case .horizontal:
        // Handle horizontal pan
        gesture.view?.center.x += translation.x

    case .vertical:
        // Handle vertical pan
        gesture.view?.center.y += translation.y
    }

    gesture.setTranslation(.zero, in: view)
}
```

---

## Hit Testing

### SwiftUI Hit Testing

**Allow Hit Testing:**
```swift
struct HitTestingExample: View {
    var body: some View {
        ZStack {
            // Background - responds to taps
            Color.blue
                .onTapGesture {
                    print("Background tapped")
                }

            // Overlay - does NOT respond to taps (transparent to hit testing)
            Text("Overlay")
                .allowsHitTesting(false)
        }
    }
}
```

**Content Shape for Irregular Shapes:**
```swift
struct IrregularShapeExample: View {
    var body: some View {
        // Only circular area is tappable
        Image(systemName: "star.fill")
            .font(.system(size: 100))
            .contentShape(Circle())
            .onTapGesture {
                print("Star tapped")
            }
    }
}
```

### UIKit Hit Testing

**Override Hit Test:**
```swift
class CustomView: UIView {
    override func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
        // Custom hit testing logic
        if let hitView = super.hitTest(point, with: event) {
            // Only respond to touches in circular area
            let radius = bounds.width / 2
            let center = CGPoint(x: bounds.midX, y: bounds.midY)
            let distance = hypot(point.x - center.x, point.y - center.y)

            if distance <= radius {
                return hitView
            }
        }

        return nil  // Pass through
    }
}
```

**Point Inside:**
```swift
class CustomButton: UIButton {
    override func point(inside point: CGPoint, with event: UIEvent?) -> Bool {
        // Expand hit area by 20pt on all sides
        let expandedBounds = bounds.insetBy(dx: -20, dy: -20)
        return expandedBounds.contains(point)
    }
}
```

---

## Haptic Feedback

### UIFeedbackGenerator

**Impact Feedback:**
```swift
class HapticExample {
    func lightImpact() {
        let generator = UIImpactFeedbackGenerator(style: .light)
        generator.impactOccurred()
    }

    func mediumImpact() {
        let generator = UIImpactFeedbackGenerator(style: .medium)
        generator.impactOccurred()
    }

    func heavyImpact() {
        let generator = UIImpactFeedbackGenerator(style: .heavy)
        generator.impactOccurred()
    }

    // iOS 13+
    func softImpact() {
        let generator = UIImpactFeedbackGenerator(style: .soft)
        generator.impactOccurred()
    }

    func rigidImpact() {
        let generator = UIImpactFeedbackGenerator(style: .rigid)
        generator.impactOccurred()
    }
}
```

**Selection Feedback:**
```swift
// For picker wheels, segmented controls
let selectionGenerator = UISelectionFeedbackGenerator()
selectionGenerator.selectionChanged()
```

**Notification Feedback:**
```swift
let notificationGenerator = UINotificationFeedbackGenerator()

// Success
notificationGenerator.notificationOccurred(.success)

// Warning
notificationGenerator.notificationOccurred(.warning)

// Error
notificationGenerator.notificationOccurred(.error)
```

### Haptic Best Practices

**Prepare for Haptics:**
```swift
class HapticManager {
    private let impactGenerator = UIImpactFeedbackGenerator(style: .medium)

    func prepareHaptics() {
        // Call this before haptic is needed (e.g., on button press began)
        impactGenerator.prepare()
    }

    func triggerHaptic() {
        // Haptic fires immediately (was prepared)
        impactGenerator.impactOccurred()
    }
}
```

**When to Use Haptics:**
- ✅ Button presses (light impact)
- ✅ Toggle switches (selection)
- ✅ Slider snap points (selection)
- ✅ Pull to refresh (light/medium impact)
- ✅ Success/error notifications (notification feedback)
- ❌ Every tap (overuse fatigues)
- ❌ Continuous gestures (battery drain)

---

## Accessibility

### VoiceOver Support

**SwiftUI Accessibility:**
```swift
struct AccessibleButton: View {
    var body: some View {
        Button(action: { /* action */ }) {
            Image(systemName: "heart.fill")
        }
        .accessibilityLabel("Like")
        .accessibilityHint("Double tap to like this post")
        .accessibilityAddTraits(.isButton)
    }
}
```

**UIKit Accessibility:**
```swift
class AccessibleView: UIView {
    override init(frame: CGRect) {
        super.init(frame: frame)

        isAccessibilityElement = true
        accessibilityLabel = "Profile picture"
        accessibilityHint = "Double tap to view profile"
        accessibilityTraits = .button
    }
}
```

### Custom Actions

**SwiftUI Custom Actions:**
```swift
struct CustomActionsExample: View {
    var body: some View {
        Image("profile")
            .accessibilityElement()
            .accessibilityLabel("Profile")
            .accessibilityAction(named: "View Profile") {
                // View profile action
            }
            .accessibilityAction(named: "Edit Profile") {
                // Edit profile action
            }
    }
}
```

**UIKit Custom Actions:**
```swift
class CustomActionsView: UIView {
    override var accessibilityCustomActions: [UIAccessibilityCustomAction]? {
        get {
            return [
                UIAccessibilityCustomAction(name: "View Profile") { _ in
                    self.viewProfile()
                    return true
                },
                UIAccessibilityCustomAction(name: "Edit Profile") { _ in
                    self.editProfile()
                    return true
                }
            ]
        }
        set { }
    }

    func viewProfile() {
        // Implementation
    }

    func editProfile() {
        // Implementation
    }
}
```

---

## Touch Target Guidelines

### Minimum Sizes

**Apple HIG Standards:**
- **Minimum touch target**: 44pt × 44pt
- **Recommended**: 48pt × 48pt for primary actions
- **Small controls**: Use `contentShape()` (SwiftUI) or expand hit area (UIKit)

**Expanding Touch Targets:**

```swift
// SwiftUI - Visual size 20pt, hit area 44pt
struct SmallButton: View {
    var body: some View {
        Image(systemName: "xmark")
            .font(.system(size: 12))
            .frame(width: 20, height: 20)
            .contentShape(Rectangle())
            .frame(width: 44, height: 44)  // Hit area
            .onTapGesture {
                // Action
            }
    }
}

// UIKit - Override point(inside:with:)
class SmallButton: UIButton {
    override func point(inside point: CGPoint, with event: UIEvent?) -> Bool {
        let expandedBounds = bounds.insetBy(dx: -12, dy: -12)  // Expand to 44pt
        return expandedBounds.contains(point)
    }
}
```

---

## Advanced Patterns

### Pull to Refresh

**SwiftUI (iOS 15+):**
```swift
struct RefreshableList: View {
    @State private var items: [String] = []

    var body: some View {
        List(items, id: \.self) { item in
            Text(item)
        }
        .refreshable {
            await loadData()
        }
    }

    func loadData() async {
        // Simulate network request
        try? await Task.sleep(nanoseconds: 2_000_000_000)
        items = ["Item 1", "Item 2", "Item 3"]
    }
}
```

**UIKit (UIRefreshControl):**
```swift
class RefreshableTableViewController: UITableViewController {
    override func viewDidLoad() {
        super.viewDidLoad()

        let refreshControl = UIRefreshControl()
        refreshControl.addTarget(self, action: #selector(handleRefresh), for: .valueChanged)
        tableView.refreshControl = refreshControl
    }

    @objc func handleRefresh() {
        // Load data
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.0) {
            self.tableView.refreshControl?.endRefreshing()
        }
    }
}
```

### Swipe Actions

**SwiftUI Swipe Actions:**
```swift
struct SwipeActionsExample: View {
    @State private var items = ["Item 1", "Item 2", "Item 3"]

    var body: some View {
        List {
            ForEach(items, id: \.self) { item in
                Text(item)
                    .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                        Button(role: .destructive) {
                            deleteItem(item)
                        } label: {
                            Label("Delete", systemImage: "trash")
                        }

                        Button {
                            archiveItem(item)
                        } label: {
                            Label("Archive", systemImage: "archivebox")
                        }
                        .tint(.blue)
                    }
            }
        }
    }

    func deleteItem(_ item: String) {
        items.removeAll { $0 == item }
    }

    func archiveItem(_ item: String) {
        print("Archived: \(item)")
    }
}
```

### Edge Swipe Navigation

**UIKit (Interactive Pop Gesture):**
```swift
class CustomNavigationController: UINavigationController {
    override func viewDidLoad() {
        super.viewDidLoad()

        // Enable interactive pop gesture
        interactivePopGestureRecognizer?.isEnabled = true
        interactivePopGestureRecognizer?.delegate = self
    }
}

extension CustomNavigationController: UIGestureRecognizerDelegate {
    func gestureRecognizerShouldBegin(_ gestureRecognizer: UIGestureRecognizer) -> Bool {
        return viewControllers.count > 1
    }
}
```

---

## UIScrollViewDelegate Deep Patterns

### Overview

UIScrollViewDelegate provides fine-grained control over scroll behavior that SwiftUI's declarative APIs don't fully expose. Essential for custom deceleration, pagination, nested scroll coordination, and rubber-banding physics.

### Core Delegate Methods

**Tracking Scroll Position:**

```swift
class ScrollViewController: UIViewController, UIScrollViewDelegate {
    func scrollViewDidScroll(_ scrollView: UIScrollView) {
        let offset = scrollView.contentOffset
        let contentHeight = scrollView.contentSize.height
        let frameHeight = scrollView.frame.height

        // Scroll progress (0.0 to 1.0)
        let maxOffset = contentHeight - frameHeight
        let progress = maxOffset > 0 ? offset.y / maxOffset : 0

        // Direction detection
        let velocity = scrollView.panGestureRecognizer.translation(in: scrollView)
        let isScrollingDown = velocity.y < 0

        // Near-bottom detection (infinite scroll trigger)
        let distanceFromBottom = contentHeight - offset.y - frameHeight
        if distanceFromBottom < 200 {
            loadMoreContent()
        }
    }
}
```

### Custom Deceleration & Pagination

**scrollViewWillEndDragging — The Most Powerful Delegate Method:**

```swift
func scrollViewWillEndDragging(
    _ scrollView: UIScrollView,
    withVelocity velocity: CGPoint,
    targetContentOffset: UnsafeMutablePointer<CGPoint>
) {
    // CUSTOM PAGINATION: Snap to page boundaries
    let pageHeight: CGFloat = 300
    let currentOffset = scrollView.contentOffset.y

    // Calculate target page
    let estimatedPage = (currentOffset + velocity.y * 300) / pageHeight
    let targetPage: CGFloat

    if velocity.y > 0 {
        targetPage = ceil(estimatedPage)    // Scrolling down → next page
    } else if velocity.y < 0 {
        targetPage = floor(estimatedPage)   // Scrolling up → previous page
    } else {
        targetPage = round(estimatedPage)   // No velocity → nearest page
    }

    // Override the deceleration target
    targetContentOffset.pointee.y = targetPage * pageHeight
}
```

**Custom Deceleration Rate:**

```swift
// Slow deceleration (like UIScrollView.DecelerationRate.fast but custom)
func scrollViewWillEndDragging(
    _ scrollView: UIScrollView,
    withVelocity velocity: CGPoint,
    targetContentOffset: UnsafeMutablePointer<CGPoint>
) {
    // Reduce scroll distance to 40% of natural deceleration
    let currentOffset = scrollView.contentOffset.y
    let naturalTarget = targetContentOffset.pointee.y
    let reducedTarget = currentOffset + (naturalTarget - currentOffset) * 0.4

    targetContentOffset.pointee.y = reducedTarget
}
```

### Snap-to-Item Scrolling

```swift
func scrollViewWillEndDragging(
    _ scrollView: UIScrollView,
    withVelocity velocity: CGPoint,
    targetContentOffset: UnsafeMutablePointer<CGPoint>
) {
    guard let collectionView = scrollView as? UICollectionView,
          let layout = collectionView.collectionViewLayout as? UICollectionViewFlowLayout else { return }

    let itemWidth = layout.itemSize.width + layout.minimumLineSpacing
    let currentOffset = scrollView.contentOffset.x
    let targetOffset = targetContentOffset.pointee.x

    // Find nearest item
    let index = round(targetOffset / itemWidth)
    let clampedIndex = max(0, index)

    // Snap to item center
    targetContentOffset.pointee.x = clampedIndex * itemWidth - layout.sectionInset.left
}
```

### Scroll State Tracking

```swift
// Called when user starts dragging
func scrollViewWillBeginDragging(_ scrollView: UIScrollView) {
    initialOffset = scrollView.contentOffset
    // Hide keyboard, cancel animations, prepare for scroll
}

// Called when dragging ends (before deceleration)
func scrollViewDidEndDragging(_ scrollView: UIScrollView, willDecelerate decelerate: Bool) {
    if !decelerate {
        // Scroll stopped immediately (user lifted finger gently)
        scrollDidStop(scrollView)
    }
}

// Called when deceleration animation finishes
func scrollViewDidEndDecelerating(_ scrollView: UIScrollView) {
    scrollDidStop(scrollView)
}

// Called when programmatic scroll animation finishes
func scrollViewDidEndScrollingAnimation(_ scrollView: UIScrollView) {
    scrollDidStop(scrollView)
}

private func scrollDidStop(_ scrollView: UIScrollView) {
    // Load visible content, update UI, report analytics
    let visibleRect = CGRect(
        origin: scrollView.contentOffset,
        size: scrollView.bounds.size
    )
    updateVisibleContent(in: visibleRect)
}
```

### Nested Scroll View Coordination

**Parent-child scroll view delegation:**

```swift
class NestedScrollViewController: UIViewController, UIScrollViewDelegate {
    let parentScrollView = UIScrollView()
    let childScrollView = UIScrollView()

    private let switchThreshold: CGFloat = 200 // Header height

    func scrollViewDidScroll(_ scrollView: UIScrollView) {
        if scrollView == parentScrollView {
            // Lock child at top until parent passes threshold
            if scrollView.contentOffset.y < switchThreshold {
                childScrollView.contentOffset.y = 0
                childScrollView.isScrollEnabled = false
            } else {
                childScrollView.isScrollEnabled = true
            }
        }

        if scrollView == childScrollView {
            // Prevent child from scrolling past top (bounce back to parent)
            if scrollView.contentOffset.y < 0 {
                scrollView.contentOffset.y = 0
                parentScrollView.contentOffset.y += scrollView.contentOffset.y
            }
        }
    }

    // Allow simultaneous recognition for smooth handoff
    func gestureRecognizer(
        _ gestureRecognizer: UIGestureRecognizer,
        shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer
    ) -> Bool {
        return true
    }
}
```

### Rubber-Banding Physics

**Custom rubber-band effect (beyond default UIScrollView bounce):**

```swift
func scrollViewDidScroll(_ scrollView: UIScrollView) {
    let offset = scrollView.contentOffset.y
    let contentHeight = scrollView.contentSize.height
    let frameHeight = scrollView.frame.height

    // Top overscroll rubber-banding
    if offset < 0 {
        let rubberBandOffset = rubberBand(offset: -offset, dimension: frameHeight)
        // Apply to stretchy header or parallax effect
        headerHeightConstraint.constant = baseHeaderHeight + rubberBandOffset
    }

    // Bottom overscroll
    let maxOffset = contentHeight - frameHeight
    if offset > maxOffset {
        let overscroll = offset - maxOffset
        let rubberBandOffset = rubberBand(offset: overscroll, dimension: frameHeight)
        // Apply to footer stretch effect
        footerView.transform = CGAffineTransform(scaleX: 1, y: 1 + rubberBandOffset / 200)
    }
}

/// Apple's rubber-banding formula: x = (1 - (1 / (x * c / d + 1))) * d
/// - offset: How far past the boundary
/// - dimension: The scroll view's size on this axis
/// - coefficient: Resistance (0.55 matches UIScrollView default)
private func rubberBand(offset: CGFloat, dimension: CGFloat, coefficient: CGFloat = 0.55) -> CGFloat {
    let result = (1.0 - (1.0 / ((offset * coefficient / dimension) + 1.0))) * dimension
    return result
}
```

### Zoom Support

```swift
func viewForZooming(in scrollView: UIScrollView) -> UIView? {
    return imageView // The view to zoom
}

func scrollViewDidZoom(_ scrollView: UIScrollView) {
    // Center content when zoomed out
    let offsetX = max((scrollView.bounds.width - scrollView.contentSize.width) / 2, 0)
    let offsetY = max((scrollView.bounds.height - scrollView.contentSize.height) / 2, 0)
    imageView.center = CGPoint(
        x: scrollView.contentSize.width / 2 + offsetX,
        y: scrollView.contentSize.height / 2 + offsetY
    )
}

func scrollViewDidEndZooming(
    _ scrollView: UIScrollView,
    with view: UIView?,
    atScale scale: CGFloat
) {
    // Snap to 1x if close
    if scale < 1.1 {
        scrollView.setZoomScale(1.0, animated: true)
    }
}
```

### Delegate Method Quick Reference

| Method | When It Fires | Common Use |
|--------|--------------|------------|
| `scrollViewDidScroll` | Every frame during scroll | Position tracking, parallax |
| `scrollViewWillBeginDragging` | User touches and starts drag | Hide keyboard, cancel timers |
| `scrollViewWillEndDragging` | User lifts finger | Custom pagination, snap points |
| `scrollViewDidEndDragging` | Drag ended | Check if deceleration follows |
| `scrollViewDidEndDecelerating` | Deceleration animation done | Load content, update state |
| `scrollViewDidEndScrollingAnimation` | Programmatic scroll done | Post-scroll actions |
| `scrollViewShouldScrollToTop` | Status bar tapped | Gate scroll-to-top behavior |
| `scrollViewDidScrollToTop` | After scroll-to-top | Refresh content |
| `viewForZooming` | Zoom gesture detected | Return zoomable view |
| `scrollViewDidZoom` | During zoom | Center content |

---

## iPad Pointer, Pencil & Hover Interactions

### Overview

iPad supports three distinct input modalities beyond touch: **trackpad/mouse pointer** (iPadOS 13.4+), **Apple Pencil** (pressure, tilt, hover), and **hardware keyboard**. Each has dedicated APIs and design conventions.

**Key Principle:** These are *additions* to touch, not replacements. Every pointer/pencil interaction must also work with finger touch. Design for touch first, then enhance for pointer and pencil.

---

### UIHoverGestureRecognizer (iPadOS 13+)

Detects when a pointer (trackpad cursor, mouse, or Apple Pencil hover) moves over a view without touching it.

**Basic Hover Detection (UIKit):**

```swift
class HoverableCardView: UIView {
    private let hoverGesture = UIHoverGestureRecognizer()

    override init(frame: CGRect) {
        super.init(frame: frame)
        hoverGesture.addTarget(self, action: #selector(handleHover))
        addGestureRecognizer(hoverGesture)
    }

    required init?(coder: NSCoder) { fatalError() }

    @objc private func handleHover(_ gesture: UIHoverGestureRecognizer) {
        switch gesture.state {
        case .began:
            UIView.animate(withDuration: 0.2) {
                self.transform = CGAffineTransform(scaleX: 1.02, y: 1.02)
                self.layer.shadowOpacity = 0.3
            }

        case .ended, .cancelled:
            UIView.animate(withDuration: 0.2) {
                self.transform = .identity
                self.layer.shadowOpacity = 0.1
            }

        case .changed:
            // Track pointer position within the view
            let location = gesture.location(in: self)
            updateHighlight(at: location)

        default:
            break
        }
    }

    private func updateHighlight(at point: CGPoint) {
        // Spotlight effect following pointer
    }
}
```

**Apple Pencil Hover (iPadOS 16.1+):**

Apple Pencil (2nd gen on M-chip iPads) provides hover altitude and azimuth *before touch*. Detect pencil hover vs pointer hover using `zOffset`:

```swift
@objc private func handleHover(_ gesture: UIHoverGestureRecognizer) {
    switch gesture.state {
    case .changed:
        let location = gesture.location(in: view)

        // iPadOS 16.1+: zOffset indicates distance from screen
        // 0.0 = touching, 1.0 = max hover distance (~12mm)
        if #available(iOS 16.1, *) {
            let zOffset = gesture.zOffset  // 0.0...1.0
            let altitude = gesture.altitudeAngle  // radians from surface
            let azimuth = gesture.azimuthAngle(in: view)  // rotation around z-axis

            // Scale brush preview based on hover distance
            let previewScale = 1.0 - (zOffset * 0.5)
            brushPreview.transform = CGAffineTransform(scaleX: previewScale, y: previewScale)
            brushPreview.center = location

            // Tilt the preview based on pencil angle
            let tiltX = cos(azimuth) * (1.0 - altitude / (.pi / 2))
            let tiltY = sin(azimuth) * (1.0 - altitude / (.pi / 2))
            brushPreview.layer.transform = CATransform3DMakeRotation(tiltX, 1, 0, 0)
        }

    case .ended, .cancelled:
        brushPreview.isHidden = true

    default:
        break
    }
}
```

**SwiftUI Hover (iPadOS 13.4+):**

```swift
struct HoverableCard: View {
    @State private var isHovered = false

    var body: some View {
        RoundedRectangle(cornerRadius: 12)
            .fill(isHovered ? Color.blue.opacity(0.15) : Color.clear)
            .frame(width: 200, height: 120)
            .overlay(Text("Hover me"))
            .scaleEffect(isHovered ? 1.02 : 1.0)
            .shadow(radius: isHovered ? 8 : 2)
            .animation(.easeInOut(duration: 0.2), value: isHovered)
            .onHover { hovering in
                isHovered = hovering
            }
    }
}
```

---

### UIPointerInteraction (iPadOS 13.4+)

The pointer system transforms the cursor shape and adds visual effects when hovering over interactive elements. This is the *primary* API for iPad pointer support — use it instead of raw `UIHoverGestureRecognizer` for standard UI elements.

**Pointer Effects (UIKit):**

```swift
class PointerButtonView: UIButton, UIPointerInteractionDelegate {
    override init(frame: CGRect) {
        super.init(frame: frame)
        // Add pointer interaction
        let pointerInteraction = UIPointerInteraction(delegate: self)
        addInteraction(pointerInteraction)
    }

    required init?(coder: NSCoder) { fatalError() }

    func pointerInteraction(
        _ interaction: UIPointerInteraction,
        styleFor region: UIPointerRegion
    ) -> UIPointerStyle? {
        let targetedPreview = UITargetedPreview(view: self)

        // .highlight — Subtle highlight behind the view (best for text/icons)
        // .lift     — View lifts toward the user with shadow (best for cards/tiles)
        // .hover    — View scales up slightly (best for toolbar items)
        let effect = UIPointerEffect.lift(targetedPreview)

        return UIPointerStyle(effect: effect)
    }
}
```

**Custom Pointer Shapes:**

```swift
func pointerInteraction(
    _ interaction: UIPointerInteraction,
    styleFor region: UIPointerRegion
) -> UIPointerStyle? {
    // Beam cursor (for text fields)
    let shape = UIPointerShape.verticalBeam(length: 24)
    return UIPointerStyle(shape: shape)
}

// Other shapes:
// .roundedRect(CGRect)          — Rounded rectangle
// .roundedRect(CGRect, radius:) — Custom corner radius
// .verticalBeam(length:)        — Text cursor
// .horizontalBeam(length:)      — Horizontal text cursor
// .path(UIBezierPath)           — Arbitrary shape
```

**Pointer Regions (Different Effects per Area):**

```swift
func pointerInteraction(
    _ interaction: UIPointerInteraction,
    regionFor request: UIPointerRegionRequest,
    defaultRegion: UIPointerRegion
) -> UIPointerRegion? {
    let location = request.location

    // Left half: highlight effect
    if location.x < bounds.midX {
        return UIPointerRegion(rect: CGRect(x: 0, y: 0, width: bounds.midX, height: bounds.height),
                               identifier: "left" as NSString)
    }

    // Right half: lift effect
    return UIPointerRegion(rect: CGRect(x: bounds.midX, y: 0, width: bounds.midX, height: bounds.height),
                           identifier: "right" as NSString)
}
```

**SwiftUI Hover Effects:**

```swift
struct PointerEffectExample: View {
    var body: some View {
        VStack(spacing: 20) {
            // Automatic pointer lift effect
            Button("Lift Effect") { }
                .buttonStyle(.borderedProminent)
                .hoverEffect(.lift)

            // Highlight effect
            Image(systemName: "star.fill")
                .font(.title)
                .padding()
                .hoverEffect(.highlight)

            // Automatic (system chooses best effect)
            Text("Auto Effect")
                .padding()
                .background(Color.blue.opacity(0.1))
                .cornerRadius(8)
                .hoverEffect(.automatic)
        }
    }
}
```

**UIButton Automatic Pointer Support:**

```swift
// UIButton has built-in pointer support — just enable it
let button = UIButton(type: .system)
button.isPointerInteractionEnabled = true  // That's it

// For custom pointer style on UIButton:
button.pointerStyleProvider = { button, proposedEffect, proposedShape in
    let targetedPreview = UITargetedPreview(view: button)
    return UIPointerStyle(effect: .lift(targetedPreview))
}
```

---

### Apple Pencil Input

#### UITouch Pencil Properties

When `touch.type == .pencil`, UITouch provides pressure, tilt, and azimuth:

```swift
class DrawingView: UIView {
    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {
        guard let touch = touches.first, touch.type == .pencil else { return }

        let location = touch.location(in: self)

        // Force: 0.0 (no pressure) to maximumPossibleForce
        let pressure = touch.force / touch.maximumPossibleForce  // Normalized 0.0...1.0

        // Altitude: radians from the surface (0 = flat, pi/2 = perpendicular)
        let altitude = touch.altitudeAngle

        // Azimuth: rotation direction of the pencil around the z-axis
        let azimuth = touch.azimuthAngle(in: self)  // 0...2*pi
        let azimuthUnitVector = touch.azimuthUnitVector(in: self)  // CGVector

        // Combine for brush dynamics
        let lineWidth = baseBrushSize * (0.5 + pressure * 0.5)
        let opacity = 0.3 + pressure * 0.7
        let tiltShading = cos(altitude)  // 0 = full shading (flat), 1 = no shading (upright)

        drawStroke(at: location, width: lineWidth, opacity: opacity, tilt: tiltShading, azimuth: azimuth)
    }
}
```

#### Predicted & Coalesced Touches (Low-Latency Drawing)

```swift
override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {
    guard let touch = touches.first else { return }

    // COALESCED touches: All intermediate points since last callback
    // Essential for smooth lines — touchesMoved fires at 60Hz but Pencil samples at 240Hz
    if let coalescedTouches = event?.coalescedTouches(for: touch) {
        for coalescedTouch in coalescedTouches {
            let point = coalescedTouch.location(in: self)
            let force = coalescedTouch.force
            commitStrokePoint(at: point, pressure: force)
        }
    }

    // PREDICTED touches: Where Apple thinks the pencil is heading
    // Draw these tentatively, then replace with real touches on next callback
    removePredictedPoints()
    if let predictedTouches = event?.predictedTouches(for: touch) {
        for predictedTouch in predictedTouches {
            let point = predictedTouch.location(in: self)
            drawPredictedPoint(at: point, pressure: predictedTouch.force)
        }
    }
}

override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent?) {
    removePredictedPoints()
    finalizeStroke()
}
```

#### Estimated Properties (iPadOS 9.1+)

Some touch properties (force, azimuth) arrive as estimates and get refined later:

```swift
override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {
    guard let touch = touches.first else { return }

    // Check which properties are still estimated
    let estimated = touch.estimatedProperties       // Currently estimated
    let expecting = touch.estimatedPropertiesExpectingUpdates  // Will be updated later

    if estimated.contains(.force) {
        // Force value is an estimate — will be refined
        // Use it for now but mark the point for update
        drawPoint(at: touch.location(in: self), pressure: touch.force, isEstimate: true)
    }
}

// Receive refined values
override func touchesEstimatedPropertiesUpdated(_ touches: Set<UITouch>) {
    for touch in touches {
        // Update previously drawn points with accurate force/azimuth
        updateStrokePoint(estimationIndex: touch.estimationUpdateIndex,
                          pressure: touch.force,
                          azimuth: touch.azimuthAngle(in: self))
    }
}
```

#### UIPencilInteraction (Double-Tap & Squeeze)

```swift
class DrawingViewController: UIViewController, UIPencilInteractionDelegate {
    override func viewDidLoad() {
        super.viewDidLoad()

        let pencilInteraction = UIPencilInteraction()
        pencilInteraction.delegate = self
        view.addInteraction(pencilInteraction)
    }

    // Double-tap on Apple Pencil 2nd gen barrel
    func pencilInteractionDidTap(_ interaction: UIPencilInteraction) {
        // Respect user's system-wide preference
        switch UIPencilInteraction.preferredTapAction {
        case .switchEraser:
            toggleEraser()
        case .switchPrevious:
            switchToPreviousTool()
        case .showColorPalette:
            showColorPicker()
        case .showInkAttributes:
            showInkSettings()
        case .ignore:
            break
        @unknown default:
            break
        }
    }

    // Apple Pencil Pro squeeze gesture (iPadOS 17.5+)
    @available(iOS 17.5, *)
    func pencilInteraction(
        _ interaction: UIPencilInteraction,
        didReceiveSqueeze squeeze: UIPencilInteraction.Squeeze
    ) {
        // Respect system preference
        switch UIPencilInteraction.preferredSqueezeAction {
        case .showContextualPalette:
            showToolPalette(at: squeeze.hoverPose?.location)
        case .switchEraser:
            toggleEraser()
        case .switchPrevious:
            switchToPreviousTool()
        case .ignore:
            break
        @unknown default:
            break
        }
    }
}
```

#### PencilKit (High-Level Drawing)

For apps that need full drawing canvas without low-level touch handling:

```swift
import PencilKit

class SketchViewController: UIViewController, PKCanvasViewDelegate, PKToolPickerObserver {
    let canvasView = PKCanvasView()
    let toolPicker = PKToolPicker()

    override func viewDidLoad() {
        super.viewDidLoad()

        canvasView.frame = view.bounds
        canvasView.delegate = self
        canvasView.drawingPolicy = .anyInput  // or .pencilOnly
        canvasView.tool = PKInkingTool(.pen, color: .black, width: 5)
        view.addSubview(canvasView)

        // Show system tool picker
        toolPicker.setVisible(true, forFirstResponder: canvasView)
        toolPicker.addObserver(canvasView)
        canvasView.becomeFirstResponder()
    }

    // React to drawing changes
    func canvasViewDrawingDidChange(_ canvasView: PKCanvasView) {
        let drawing = canvasView.drawing
        let strokeCount = drawing.strokes.count

        // Export drawing as image
        let image = drawing.image(from: drawing.bounds, scale: UIScreen.main.scale)

        // Export as data (for saving/syncing)
        let data = drawing.dataRepresentation()
    }
}
```

**SwiftUI PencilKit Integration:**

```swift
import PencilKit

struct DrawingCanvas: UIViewRepresentable {
    @Binding var drawing: PKDrawing

    func makeUIView(context: Context) -> PKCanvasView {
        let canvas = PKCanvasView()
        canvas.drawing = drawing
        canvas.drawingPolicy = .anyInput
        canvas.delegate = context.coordinator

        // Show tool picker
        let toolPicker = PKToolPicker()
        toolPicker.setVisible(true, forFirstResponder: canvas)
        toolPicker.addObserver(canvas)
        canvas.becomeFirstResponder()

        return canvas
    }

    func updateUIView(_ uiView: PKCanvasView, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(drawing: $drawing)
    }

    class Coordinator: NSObject, PKCanvasViewDelegate {
        @Binding var drawing: PKDrawing

        init(drawing: Binding<PKDrawing>) {
            _drawing = drawing
        }

        func canvasViewDrawingDidChange(_ canvasView: PKCanvasView) {
            drawing = canvasView.drawing
        }
    }
}

// Usage
struct DrawingView: View {
    @State private var drawing = PKDrawing()

    var body: some View {
        DrawingCanvas(drawing: $drawing)
            .ignoresSafeArea()
    }
}
```

---

### Pointer & Pencil Design Guidelines

**Pointer (Trackpad/Mouse):**
- Use `.hoverEffect(.lift)` for cards and tiles
- Use `.hoverEffect(.highlight)` for text and icons
- Buttons: Enable `isPointerInteractionEnabled = true` (free)
- Custom cursor shapes for specialized tools (crosshair for drawing, beam for text)
- Pointer effects should be *subtle* — never dramatically change layout on hover

**Apple Pencil:**
- Always respect `UIPencilInteraction.preferredTapAction` and `preferredSqueezeAction`
- Use coalesced touches for smooth 240Hz stroke rendering
- Use predicted touches to reduce perceived latency
- Map pressure to brush size/opacity, altitude to shading/tilt
- Provide palm rejection — pencil input should not conflict with resting hand
- Gate pencil-specific features: `if touch.type == .pencil { ... }`

**Hover (Pencil + Pointer):**
- Pencil hover provides `zOffset` (distance), `altitudeAngle`, and `azimuthAngle`
- Pointer hover only provides 2D position (no altitude/azimuth)
- Use hover for preview (brush cursor, tooltip, selection highlight)
- Never *require* hover — it's an enhancement, not all iPads support pencil hover

**When to Use Which API:**

| Need | API |
|------|-----|
| Button/control pointer feedback | `UIPointerInteraction` or `.hoverEffect()` |
| Custom hover tracking | `UIHoverGestureRecognizer` |
| Pencil pressure/tilt drawing | `UITouch` properties in `touchesMoved` |
| Full drawing canvas | `PencilKit` (PKCanvasView) |
| Pencil barrel tap | `UIPencilInteraction` delegate |
| Pencil Pro squeeze | `UIPencilInteraction` squeeze delegate (iPadOS 17.5+) |
| Pencil hover preview | `UIHoverGestureRecognizer` with `zOffset` (iPadOS 16.1+) |
| Pointer cursor shape | `UIPointerStyle` with custom `UIPointerShape` |

---

## iPad Keyboard Interactions

### UIKeyCommand (UIKit)

For hardware keyboard shortcuts on iPad:

```swift
class EditorViewController: UIViewController {
    override var keyCommands: [UIKeyCommand]? {
        return [
            UIKeyCommand(input: "s", modifierFlags: .command,
                         action: #selector(saveDocument),
                         discoverabilityTitle: "Save"),
            UIKeyCommand(input: "z", modifierFlags: .command,
                         action: #selector(undoAction),
                         discoverabilityTitle: "Undo"),
            UIKeyCommand(input: "z", modifierFlags: [.command, .shift],
                         action: #selector(redoAction),
                         discoverabilityTitle: "Redo"),
            UIKeyCommand(input: "n", modifierFlags: .command,
                         action: #selector(newDocument),
                         discoverabilityTitle: "New Document"),
            UIKeyCommand(input: UIKeyCommand.inputEscape, modifierFlags: [],
                         action: #selector(dismissModal),
                         discoverabilityTitle: "Dismiss"),
            // Arrow key navigation
            UIKeyCommand(input: UIKeyCommand.inputUpArrow, modifierFlags: [],
                         action: #selector(navigateUp)),
            UIKeyCommand(input: UIKeyCommand.inputDownArrow, modifierFlags: [],
                         action: #selector(navigateDown)),
        ]
    }

    @objc func saveDocument() { /* ... */ }
    @objc func undoAction() { /* ... */ }
    @objc func redoAction() { /* ... */ }
    @objc func newDocument() { /* ... */ }
    @objc func dismissModal() { dismiss(animated: true) }
    @objc func navigateUp() { /* ... */ }
    @objc func navigateDown() { /* ... */ }
}
```

### SwiftUI Keyboard Shortcuts

```swift
struct EditorView: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack {
            TextEditor(text: $content)
        }
        .toolbar {
            Button("Save") { save() }
                .keyboardShortcut("s", modifiers: .command)

            Button("New") { newDocument() }
                .keyboardShortcut("n", modifiers: .command)
        }
        // Escape to dismiss
        .keyboardShortcut(.escape, modifiers: [])
    }
}

// Default button shortcuts
struct DialogView: View {
    var body: some View {
        HStack {
            Button("Cancel") { cancel() }
                .keyboardShortcut(.cancelAction)   // Escape

            Button("OK") { confirm() }
                .keyboardShortcut(.defaultAction)   // Return
        }
    }
}
```

### Focus System (iPadOS 15+)

For keyboard and game controller navigation between UI elements:

```swift
struct FocusableGridView: View {
    @FocusState private var focusedItem: String?

    let items = ["A", "B", "C", "D"]

    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 100))]) {
            ForEach(items, id: \.self) { item in
                CardView(title: item)
                    .focusable()
                    .focused($focusedItem, equals: item)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(focusedItem == item ? Color.blue : Color.clear, lineWidth: 2)
                    )
                    .onKeyPress(.return) {
                        selectItem(item)
                        return .handled
                    }
            }
        }
        .focusSection()  // Group for directional focus navigation
    }
}
```

### iPad Keyboard Design Guidelines

- Hold Command key to show keyboard shortcut overlay (system-provided, free)
- Match macOS conventions: Cmd+S save, Cmd+Z undo, Cmd+C copy, etc.
- Provide `discoverabilityTitle` for all key commands (shows in overlay)
- Arrow keys should navigate between items in lists/grids
- Escape should dismiss modals, popovers, search
- Tab/Shift+Tab should move focus between form fields
- Return/Enter should activate the focused element or default button

---

## Resources

**Apple Documentation:**
- [SwiftUI Gestures](https://developer.apple.com/documentation/swiftui/gestures)
- [UIGestureRecognizer](https://developer.apple.com/documentation/uikit/uigesturerecognizer)
- [UIScrollViewDelegate](https://developer.apple.com/documentation/uikit/uiscrollviewdelegate)
- [Haptic Feedback](https://developer.apple.com/documentation/uikit/uifeedbackgenerator)
- [Accessibility](https://developer.apple.com/documentation/accessibility)

**WWDC Videos:**
- WWDC 2024: "What's New in SwiftUI" (ScrollGeometry)
- WWDC 2023: "Beyond scroll views" (scrollTransition, visualEffect)
- WWDC 2020: "What's New in SwiftUI"
- WWDC 2019: "Advances in UI Data Sources"
- WWDC 2018: "Designing Fluid Interfaces" (rubber-banding, spring physics)

**Recommended Reading:**
- Apple HIG: Gestures section
- iOS Human Interface Guidelines: Touch and Gestures

---

*iOS Touch & Gesture Interaction Patterns - Huxley Mobile Development*
*Building responsive, accessible, and delightful touch interactions*
