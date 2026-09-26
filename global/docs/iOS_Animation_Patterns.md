# iOS Animation & Motion Patterns

**Complete reference for building fluid, expressive animations in iOS apps**

---

## Overview

Animations bring iOS apps to life, providing visual feedback, clarifying relationships, and creating memorable experiences. This guide covers animation techniques from simple SwiftUI modifiers to complex Core Animation compositions.

**Key Principles:**
- **Purposeful** - Every animation should have a clear reason
- **Natural** - Follow physics and real-world motion
- **Subtle** - Don't distract from content
- **Performant** - 60fps on all devices (120fps on Pro models)
- **Respectful** - Honor Reduce Motion accessibility setting

---

## Table of Contents

1. [SwiftUI Animations](#swiftui-animations)
2. [UIKit Animations](#uikit-animations)
3. [Core Animation](#core-animation)
4. [Gesture-Driven Animations](#gesture-driven-animations)
5. [Physics & Spring Animations](#physics--spring-animations)
6. [Custom Transitions](#custom-transitions)
7. [Hero Animations](#hero-animations)
8. [Performance Optimization](#performance-optimization)
9. [Accessibility Considerations](#accessibility-considerations)
10. [Animation Libraries](#animation-libraries)

---

## SwiftUI Animations

### Basic Animations

**Implicit Animations** - Animate any animatable property:

```swift
struct PulsingButton: View {
    @State private var isPressed = false

    var body: some View {
        Button("Tap Me") {
            // Action
        }
        .scaleEffect(isPressed ? 0.9 : 1.0)
        .animation(.easeInOut(duration: 0.2), value: isPressed)
        .simultaneousGesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in isPressed = true }
                .onEnded { _ in isPressed = false }
        )
    }
}
```

**Explicit Animations** - Control when animation occurs:

```swift
struct ExpandableCard: View {
    @State private var isExpanded = false

    var body: some View {
        VStack {
            Text("Title")

            if isExpanded {
                Text("Additional content")
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .onTapGesture {
            withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                isExpanded.toggle()
            }
        }
    }
}
```

### Timing Curves

**Built-in Curves:**
```swift
// Linear - constant speed
.animation(.linear(duration: 0.3), value: state)

// Ease In - starts slow, ends fast
.animation(.easeIn(duration: 0.3), value: state)

// Ease Out - starts fast, ends slow
.animation(.easeOut(duration: 0.3), value: state)

// Ease In-Out - slow at both ends (most natural)
.animation(.easeInOut(duration: 0.3), value: state)
```

**Custom Curves:**
```swift
// Custom timing function
.animation(
    .timingCurve(0.17, 0.67, 0.83, 0.67, duration: 0.4),
    value: state
)

// Spring physics (recommended)
.animation(
    .spring(response: 0.3, dampingFraction: 0.7, blendDuration: 0),
    value: state
)
```

### Transitions

**Built-in Transitions:**
```swift
// Opacity fade
.transition(.opacity)

// Slide from edge
.transition(.move(edge: .bottom))

// Scale
.transition(.scale)

// Combined transitions
.transition(.opacity.combined(with: .scale))

// Asymmetric (different in/out)
.transition(.asymmetric(
    insertion: .move(edge: .leading),
    removal: .move(edge: .trailing)
))
```

**Custom Transitions:**
```swift
extension AnyTransition {
    static var fadeAndSlide: AnyTransition {
        .opacity.combined(with: .move(edge: .bottom))
    }

    static var pivot: AnyTransition {
        .modifier(
            active: PivotModifier(rotation: 90),
            identity: PivotModifier(rotation: 0)
        )
    }
}

struct PivotModifier: ViewModifier {
    let rotation: Double

    func body(content: Content) -> some View {
        content
            .rotationEffect(.degrees(rotation))
            .opacity(rotation == 0 ? 1 : 0)
    }
}
```

### Matched Geometry Effect

**Hero-style animations between views:**

```swift
struct ContentView: View {
    @State private var showDetail = false
    @Namespace private var namespace

    var body: some View {
        if showDetail {
            DetailView(namespace: namespace, show: $showDetail)
        } else {
            ListView(namespace: namespace, show: $showDetail)
        }
    }
}

struct ListView: View {
    let namespace: Namespace.ID
    @Binding var show: Bool

    var body: some View {
        VStack {
            Image("hero")
                .matchedGeometryEffect(id: "heroImage", in: namespace)

            Text("Title")
                .matchedGeometryEffect(id: "title", in: namespace)
        }
        .onTapGesture {
            withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                show = true
            }
        }
    }
}

struct DetailView: View {
    let namespace: Namespace.ID
    @Binding var show: Bool

    var body: some View {
        VStack {
            Image("hero")
                .matchedGeometryEffect(id: "heroImage", in: namespace)
                .frame(height: 300)

            Text("Title")
                .matchedGeometryEffect(id: "title", in: namespace)
                .font(.largeTitle)

            Text("Detail content...")
        }
        .onTapGesture {
            withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                show = false
            }
        }
    }
}
```

### Animatable Properties

**All SwiftUI animatable properties:**
- Position: `offset()`, `position()`
- Size: `frame()`, `scaleEffect()`
- Rotation: `rotationEffect()`, `rotation3DEffect()`
- Opacity: `opacity()`
- Color: `foregroundColor()`, `background()`
- Corner radius: `cornerRadius()`
- Blur: `blur()`
- Saturation: `saturation()`
- Brightness: `brightness()`
- Contrast: `contrast()`

---

## UIKit Animations

### UIView Animations

**Basic UIView animation:**

```swift
// Simple property animation
UIView.animate(withDuration: 0.3) {
    view.alpha = 0.5
    view.frame.origin.y += 100
    view.backgroundColor = .red
}

// With completion
UIView.animate(withDuration: 0.3, animations: {
    view.transform = CGAffineTransform(scaleX: 1.2, y: 1.2)
}) { completed in
    print("Animation finished")
}

// With spring physics
UIView.animate(
    withDuration: 0.6,
    delay: 0,
    usingSpringWithDamping: 0.7,
    initialSpringVelocity: 0.5,
    options: [.curveEaseInOut],
    animations: {
        view.center.y += 200
    }
)
```

**Animatable UIView Properties:**
- `frame`, `bounds`, `center`
- `transform` (scale, rotation, translation)
- `alpha`
- `backgroundColor`
- `contentStretch` (deprecated in favor of resizableImage)

**Animation Options:**
```swift
UIView.animate(
    withDuration: 0.3,
    delay: 0.1,
    options: [
        .curveEaseInOut,        // Timing curve
        .allowUserInteraction,  // Allow touches during animation
        .beginFromCurrentState, // Start from current position (not final)
        .repeat,                // Repeat indefinitely
        .autoreverse            // Reverse back to start
    ],
    animations: {
        // Animate properties
    },
    completion: { finished in
        // Completion handler
    }
)
```

### Keyframe Animations

**Multi-step animations:**

```swift
UIView.animateKeyframes(
    withDuration: 2.0,
    delay: 0,
    options: [],
    animations: {
        // 0-0.25: Move right
        UIView.addKeyframe(withRelativeStartTime: 0.0, relativeDuration: 0.25) {
            view.center.x += 100
        }

        // 0.25-0.5: Move down
        UIView.addKeyframe(withRelativeStartTime: 0.25, relativeDuration: 0.25) {
            view.center.y += 100
        }

        // 0.5-0.75: Move left
        UIView.addKeyframe(withRelativeStartTime: 0.5, relativeDuration: 0.25) {
            view.center.x -= 100
        }

        // 0.75-1.0: Move up
        UIView.addKeyframe(withRelativeStartTime: 0.75, relativeDuration: 0.25) {
            view.center.y -= 100
        }
    }
)
```

---

## Core Animation

### CABasicAnimation

**Animate single property:**

```swift
let animation = CABasicAnimation(keyPath: "position.y")
animation.fromValue = view.layer.position.y
animation.toValue = view.layer.position.y + 100
animation.duration = 0.5
animation.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
view.layer.add(animation, forKey: "moveDown")

// Update model layer (important!)
view.layer.position.y += 100
```

**Common keyPaths:**
- `position`, `position.x`, `position.y`
- `opacity`
- `transform.scale`, `transform.scale.x`, `transform.scale.y`
- `transform.rotation`, `transform.rotation.x`, `transform.rotation.y`, `transform.rotation.z`
- `transform.translation.x`, `transform.translation.y`, `transform.translation.z`
- `backgroundColor`
- `cornerRadius`
- `borderWidth`, `borderColor`
- `shadowOpacity`, `shadowRadius`, `shadowOffset`

### CAKeyframeAnimation

**Multi-value animations:**

```swift
let animation = CAKeyframeAnimation(keyPath: "position")
animation.values = [
    NSValue(cgPoint: CGPoint(x: 50, y: 50)),
    NSValue(cgPoint: CGPoint(x: 150, y: 50)),
    NSValue(cgPoint: CGPoint(x: 150, y: 150)),
    NSValue(cgPoint: CGPoint(x: 50, y: 150)),
    NSValue(cgPoint: CGPoint(x: 50, y: 50))
]
animation.duration = 2.0
animation.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
view.layer.add(animation, forKey: "square")
```

**Path-based animations:**

```swift
let path = UIBezierPath()
path.move(to: CGPoint(x: 50, y: 50))
path.addCurve(
    to: CGPoint(x: 250, y: 250),
    controlPoint1: CGPoint(x: 150, y: 50),
    controlPoint2: CGPoint(x: 150, y: 250)
)

let animation = CAKeyframeAnimation(keyPath: "position")
animation.path = path.cgPath
animation.duration = 1.5
animation.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
view.layer.add(animation, forKey: "curve")
```

### CAAnimationGroup

**Combine multiple animations:**

```swift
let scaleAnimation = CABasicAnimation(keyPath: "transform.scale")
scaleAnimation.fromValue = 1.0
scaleAnimation.toValue = 1.5

let rotateAnimation = CABasicAnimation(keyPath: "transform.rotation")
rotateAnimation.fromValue = 0
rotateAnimation.toValue = CGFloat.pi * 2

let fadeAnimation = CABasicAnimation(keyPath: "opacity")
fadeAnimation.fromValue = 1.0
fadeAnimation.toValue = 0.0

let group = CAAnimationGroup()
group.animations = [scaleAnimation, rotateAnimation, fadeAnimation]
group.duration = 1.0
group.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)

view.layer.add(group, forKey: "combo")
```

### CASpringAnimation

**Physics-based spring animation:**

```swift
let spring = CASpringAnimation(keyPath: "position.y")
spring.fromValue = view.layer.position.y
spring.toValue = view.layer.position.y + 200
spring.damping = 10  // Higher = less bouncy (default: 10)
spring.stiffness = 100  // Higher = faster oscillation (default: 100)
spring.mass = 1  // Higher = heavier (default: 1)
spring.initialVelocity = 0  // Initial velocity
spring.duration = spring.settlingDuration  // Auto-calculated

view.layer.add(spring, forKey: "bounce")
view.layer.position.y += 200
```

---

## Gesture-Driven Animations

### SwiftUI Gesture Animations

**Drag with animation:**

```swift
struct DraggableView: View {
    @State private var offset = CGSize.zero

    var body: some View {
        Circle()
            .fill(Color.blue)
            .frame(width: 100, height: 100)
            .offset(offset)
            .gesture(
                DragGesture()
                    .onChanged { gesture in
                        offset = gesture.translation
                    }
                    .onEnded { _ in
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) {
                            offset = .zero
                        }
                    }
            )
    }
}
```

**Interactive spring animation:**

```swift
struct InteractiveCard: View {
    @GestureState private var dragState = CGSize.zero
    @State private var position = CGSize.zero

    var body: some View {
        RoundedRectangle(cornerRadius: 20)
            .fill(Color.blue)
            .frame(width: 300, height: 400)
            .offset(x: position.width + dragState.width, y: position.height + dragState.height)
            .gesture(
                DragGesture()
                    .updating($dragState) { value, state, _ in
                        state = value.translation
                    }
                    .onEnded { value in
                        withAnimation(.interpolatingSpring(stiffness: 100, damping: 10)) {
                            position.width += value.translation.width
                            position.height += value.translation.height
                        }
                    }
            )
    }
}
```

### UIKit Gesture Animations

**Pan gesture with animation:**

```swift
class DraggableViewController: UIViewController {
    private var animator: UIViewPropertyAnimator?

    override func viewDidLoad() {
        super.viewDidLoad()

        let pan = UIPanGestureRecognizer(target: self, action: #selector(handlePan))
        view.addGestureRecognizer(pan)
    }

    @objc func handlePan(_ gesture: UIPanGestureRecognizer) {
        let translation = gesture.translation(in: view)

        switch gesture.state {
        case .changed:
            // Update position during drag
            gesture.view?.center.x += translation.x
            gesture.view?.center.y += translation.y
            gesture.setTranslation(.zero, in: view)

        case .ended, .cancelled:
            // Animate back to center
            let velocity = gesture.velocity(in: view)

            animator = UIViewPropertyAnimator(
                duration: 0.6,
                dampingRatio: 0.7,
                animations: {
                    gesture.view?.center = self.view.center
                }
            )

            // Add velocity for natural motion
            let vector = CGVector(dx: velocity.x / 500, dy: velocity.y / 500)
            animator?.addAnimations({}, delayFactor: 0)
            animator?.startAnimation()

        default:
            break
        }
    }
}
```

### UIViewPropertyAnimator

**Interruptible, scrubbing animations:**

```swift
class InteractiveViewController: UIViewController {
    private var animator: UIViewPropertyAnimator?

    func setupInteractiveAnimation() {
        animator = UIViewPropertyAnimator(duration: 2.0, curve: .easeInOut) {
            self.view.backgroundColor = .red
            self.view.alpha = 0.5
        }

        // Scrub animation with slider
        let slider = UISlider()
        slider.addTarget(self, action: #selector(sliderChanged), for: .valueChanged)
    }

    @objc func sliderChanged(_ slider: UISlider) {
        animator?.fractionComplete = CGFloat(slider.value)
    }
}
```

---

## Physics & Spring Animations

### Spring Parameters

**Understanding spring physics:**

```swift
// response: Time for one oscillation cycle (in seconds)
// dampingFraction: 0 = bouncy forever, 1 = no bounce
// blendDuration: How long to blend with current animation

// Gentle bounce
.spring(response: 0.6, dampingFraction: 0.75, blendDuration: 0)

// Snappy
.spring(response: 0.3, dampingFraction: 0.7, blendDuration: 0)

// Bouncy
.spring(response: 0.5, dampingFraction: 0.5, blendDuration: 0)

// Critically damped (no overshoot)
.spring(response: 0.4, dampingFraction: 1.0, blendDuration: 0)
```

**Common spring presets:**

```swift
extension Animation {
    // Quick, snappy response
    static var snappy: Animation {
        .spring(response: 0.3, dampingFraction: 0.7)
    }

    // Smooth, no bounce
    static var smooth: Animation {
        .spring(response: 0.4, dampingFraction: 1.0)
    }

    // Playful bounce
    static var bouncy: Animation {
        .spring(response: 0.5, dampingFraction: 0.5)
    }
}
```

---

## Custom Transitions

### View Controller Transitions (UIKit)

**Custom push/pop transitions:**

```swift
class CustomPushAnimator: NSObject, UIViewControllerAnimatedTransitioning {
    func transitionDuration(using transitionContext: UIViewControllerContextTransitioning?) -> TimeInterval {
        return 0.5
    }

    func animateTransition(using transitionContext: UIViewControllerContextTransitioning) {
        guard let fromVC = transitionContext.viewController(forKey: .from),
              let toVC = transitionContext.viewController(forKey: .to) else { return }

        let containerView = transitionContext.containerView
        containerView.addSubview(toVC.view)

        // Start position (off-screen right)
        toVC.view.frame = containerView.bounds.offsetBy(dx: containerView.bounds.width, dy: 0)

        UIView.animate(
            withDuration: transitionDuration(using: transitionContext),
            delay: 0,
            usingSpringWithDamping: 0.8,
            initialSpringVelocity: 0.5,
            options: [],
            animations: {
                toVC.view.frame = containerView.bounds
                fromVC.view.alpha = 0.5
            },
            completion: { finished in
                fromVC.view.alpha = 1.0
                transitionContext.completeTransition(!transitionContext.transitionWasCancelled)
            }
        )
    }
}

// Usage in navigation controller delegate
class NavigationControllerDelegate: NSObject, UINavigationControllerDelegate {
    func navigationController(
        _ navigationController: UINavigationController,
        animationControllerFor operation: UINavigationController.Operation,
        from fromVC: UIViewController,
        to toVC: UIViewController
    ) -> UIViewControllerAnimatedTransitioning? {
        return CustomPushAnimator()
    }
}
```

### Modal Presentation Transitions

**Custom modal presentation:**

```swift
class CustomModalTransition: NSObject, UIViewControllerTransitioningDelegate {
    func animationController(
        forPresented presented: UIViewController,
        presenting: UIViewController,
        source: UIViewController
    ) -> UIViewControllerAnimatedTransitioning? {
        return ModalPresentAnimator()
    }

    func animationController(forDismissed dismissed: UIViewController) -> UIViewControllerAnimatedTransitioning? {
        return ModalDismissAnimator()
    }
}

class ModalPresentAnimator: NSObject, UIViewControllerAnimatedTransitioning {
    func transitionDuration(using transitionContext: UIViewControllerContextTransitioning?) -> TimeInterval {
        return 0.4
    }

    func animateTransition(using transitionContext: UIViewControllerContextTransitioning) {
        guard let toVC = transitionContext.viewController(forKey: .to) else { return }

        let containerView = transitionContext.containerView
        containerView.addSubview(toVC.view)

        // Start: scaled down, transparent
        toVC.view.transform = CGAffineTransform(scaleX: 0.7, y: 0.7)
        toVC.view.alpha = 0

        UIView.animate(
            withDuration: transitionDuration(using: transitionContext),
            delay: 0,
            usingSpringWithDamping: 0.8,
            initialSpringVelocity: 0,
            options: [],
            animations: {
                toVC.view.transform = .identity
                toVC.view.alpha = 1.0
            },
            completion: { finished in
                transitionContext.completeTransition(!transitionContext.transitionWasCancelled)
            }
        )
    }
}
```

---

## Hero Animations

### matchedGeometryEffect (SwiftUI)

**Already covered above**, but key patterns:

```swift
// 1. Create namespace
@Namespace private var namespace

// 2. Match elements across views
.matchedGeometryEffect(id: "uniqueID", in: namespace)

// 3. Animate transitions
withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
    // Change state
}
```

### Hero Library (UIKit)

**Third-party library for hero transitions:**

```swift
// Install: pod 'Hero'
import Hero

// Enable in view controller
override func viewDidLoad() {
    super.viewDidLoad()
    hero.isEnabled = true
}

// Set hero IDs on views
imageView.hero.id = "heroImage"
titleLabel.hero.id = "heroTitle"

// Modifiers for custom effects
imageView.hero.modifiers = [.scale(0.5), .fade]

// Present with hero transition
let detailVC = DetailViewController()
detailVC.hero.isEnabled = true
present(detailVC, animated: true)
```

---

## Performance Optimization

### Best Practices

**1. Use appropriate animation type:**
- SwiftUI animations for simple property changes
- UIView animations for view properties
- Core Animation for complex layer animations
- Metal/Core Graphics for custom rendering

**2. Optimize for 60fps (120fps on Pro):**
```swift
// Monitor frame rate
let displayLink = CADisplayLink(target: self, selector: #selector(update))
displayLink.add(to: .main, forMode: .default)

@objc func update(displayLink: CADisplayLink) {
    let fps = 1.0 / displayLink.targetTimestamp
    print("FPS: \(fps)")
}
```

**3. Avoid expensive operations in animations:**
```swift
// BAD: Animating expensive computation
UIView.animate(withDuration: 0.3) {
    view.layer.shadowPath = complexCalculation()  // Called every frame!
}

// GOOD: Pre-compute before animating
let newShadowPath = complexCalculation()
UIView.animate(withDuration: 0.3) {
    view.layer.shadowPath = newShadowPath
}
```

**4. Use layer backing when possible:**
```swift
// Animate layer properties (hardware accelerated)
view.layer.position = newPosition  // GPU
view.layer.transform = CATransform3DMakeRotation(angle, 0, 0, 1)  // GPU

// Avoid animating frame (triggers layout)
view.frame = newFrame  // CPU (slower)
```

**5. Enable rasterization for complex views:**
```swift
// Cache complex view hierarchy as bitmap
view.layer.shouldRasterize = true
view.layer.rasterizationScale = UIScreen.main.scale

// Disable after animation completes
UIView.animate(withDuration: 0.3, animations: {
    // Animate
}) { _ in
    view.layer.shouldRasterize = false
}
```

---

## Accessibility Considerations

### Reduce Motion

**Always respect accessibility settings:**

```swift
// SwiftUI
if UIAccessibility.isReduceMotionEnabled {
    // No animation
    view.opacity = 0
} else {
    // Animate
    withAnimation {
        view.opacity = 0
    }
}

// Or use conditional animation
.animation(UIAccessibility.isReduceMotionEnabled ? nil : .spring(), value: state)
```

**UIKit:**
```swift
if UIAccessibility.isReduceMotionEnabled {
    // Instant change
    view.alpha = 0
} else {
    // Animate
    UIView.animate(withDuration: 0.3) {
        view.alpha = 0
    }
}
```

**Listen for changes:**
```swift
NotificationCenter.default.addObserver(
    forName: UIAccessibility.reduceMotionStatusDidChangeNotification,
    object: nil,
    queue: .main
) { _ in
    // Update animation behavior
}
```

---

## Animation Libraries

### Popular iOS Animation Libraries

**1. Lottie (After Effects animations):**
```swift
// pod 'lottie-ios'
import Lottie

let animationView = LottieAnimationView(name: "animation")
animationView.frame = view.bounds
animationView.contentMode = .scaleAspectFit
animationView.loopMode = .loop
animationView.play()
view.addSubview(animationView)
```

**2. Hero (View controller transitions):**
```swift
// pod 'Hero'
// Covered in Hero Animations section above
```

**3. Spring (Simplified animations):**
```swift
// pod 'Spring'
import Spring

let springView = SpringView()
springView.animation = "slideLeft"
springView.curve = "spring"
springView.duration = 1.0
springView.animate()
```

**4. Pop (Facebook's animation engine):**
```swift
// pod 'pop'
import pop

let animation = POPSpringAnimation(propertyNamed: kPOPLayerPositionY)
animation?.toValue = 200
animation?.springBounciness = 10
animation?.springSpeed = 10
view.layer.pop_add(animation, forKey: "bounce")
```

---

## Quick Reference

### Recommended Timings

| Animation Type | Duration | Timing Curve |
|---------------|----------|--------------|
| **Button press** | 0.1-0.2s | easeInOut |
| **View transition** | 0.3-0.4s | spring (0.3, 0.7) |
| **Modal present** | 0.4-0.5s | spring (0.4, 0.8) |
| **Tab switch** | 0.25-0.3s | easeInOut |
| **Scroll snap** | 0.3-0.4s | spring (0.3, 0.7) |
| **Pull to refresh** | 0.4-0.6s | spring (0.5, 0.6) |
| **Delete/remove** | 0.3s | easeIn |
| **Add/insert** | 0.3s | spring (0.3, 0.7) |

### Spring Parameter Guide

| Feel | Response | Damping | Use Case |
|------|----------|---------|----------|
| **Snappy** | 0.3 | 0.7 | Buttons, quick interactions |
| **Smooth** | 0.4 | 1.0 | Transitions, no overshoot |
| **Bouncy** | 0.5 | 0.5 | Playful, game-like |
| **Gentle** | 0.6 | 0.75 | Large elements, cards |

---

## Resources

**Apple Documentation:**
- [SwiftUI Animation](https://developer.apple.com/documentation/swiftui/animation)
- [UIView Animations](https://developer.apple.com/documentation/uikit/uiview/1622418-animate)
- [Core Animation Programming Guide](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/CoreAnimation_guide/)

**Recommended Reading:**
- Apple HIG: Motion guidelines
- iOS Animation Tutorial by Ray Wenderlich
- Core Animation book by Marcus Zarra

**Tools:**
- [easings.net](https://easings.net) - Easing function visualizer
- [cubic-bezier.com](https://cubic-bezier.com) - Cubic bezier curve generator
- [LottieFiles](https://lottiefiles.com) - After Effects animations

---

*iOS Animation & Motion Patterns - Huxley Mobile Development*
*Building fluid, expressive, and accessible iOS animations*
