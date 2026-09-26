# iOS 18+ ScrollGeometry & Modern Scroll Tracking Patterns

**The Apple-blessed way to track scroll position, content size, and visible region.**

---

## Overview

iOS 18 introduced `onScrollGeometryChange` and the `ScrollGeometry` struct, replacing the hacky GeometryReader-in-background pattern that caused performance issues. This is now the correct way to reactively observe scroll state.

**Key Principles:**
- **Native API** — No more preference keys or invisible geometry readers
- **Performant** — Only fires closures when values actually change
- **Composable** — Transform raw geometry into exactly what you need
- **Threshold-friendly** — Built-in support for gating state updates

---

## Table of Contents

1. [onScrollGeometryChange](#onscrollgeometrychange)
2. [ScrollGeometry Struct](#scrollgeometry-struct)
3. [Common Patterns](#common-patterns)
4. [ScrollPosition (iOS 18)](#scrollposition-ios-18)
5. [Migration from Legacy Patterns](#migration-from-legacy-patterns)
6. [Performance Guidelines](#performance-guidelines)

---

## onScrollGeometryChange

### Basic Usage

```swift
ScrollView {
    content
}
.onScrollGeometryChange(for: CGFloat.self) { geometry in
    // Transform: extract what you need
    geometry.contentOffset.y
} action: { oldValue, newValue in
    // Act: only fires when transformed value changes
    showHeader = newValue < 100
}
```

**Two closures, one purpose:**
1. **`transform`** — Maps `ScrollGeometry` to any `Equatable` type
2. **`action`** — Fires only when the transformed value changes

### API Signature

```swift
func onScrollGeometryChange<T: Equatable>(
    for type: T.Type,
    of transform: @escaping (ScrollGeometry) -> T,
    action: @escaping (_ oldValue: T, _ newValue: T) -> Void
) -> some View
```

---

## ScrollGeometry Struct

```swift
struct ScrollGeometry {
    /// The offset of the content relative to the scroll view's origin
    var contentOffset: CGPoint

    /// The total size of the scrollable content
    var contentSize: CGSize

    /// The insets applied to the content area
    var contentInsets: EdgeInsets

    /// The visible size of the scroll view (viewport)
    var containerSize: CGSize

    /// The visible rect of the content
    var visibleRect: CGRect
}
```

### Key Properties Explained

| Property | What It Tells You |
|----------|-------------------|
| `contentOffset` | How far the user has scrolled (x/y) |
| `contentSize` | Total scrollable content dimensions |
| `containerSize` | Viewport dimensions (visible area) |
| `contentInsets` | Safe area / custom insets applied |
| `visibleRect` | The exact rectangle currently visible |

---

## Common Patterns

### 1. Hide/Show Header on Scroll

```swift
struct ScrollHideHeaderView: View {
    @State private var showHeader = true

    var body: some View {
        VStack(spacing: 0) {
            if showHeader {
                HeaderView()
                    .transition(.move(edge: .top).combined(with: .opacity))
            }

            ScrollView {
                LazyVStack {
                    ForEach(items) { item in
                        ItemRow(item: item)
                    }
                }
            }
            .onScrollGeometryChange(for: Bool.self) { geometry in
                geometry.contentOffset.y < 50
            } action: { _, shouldShow in
                withAnimation(.snappy) {
                    showHeader = shouldShow
                }
            }
        }
    }
}
```

### 2. Scroll-to-Bottom Detection (Infinite Scroll)

```swift
ScrollView {
    LazyVStack {
        ForEach(items) { item in
            ItemRow(item: item)
        }

        if isLoading {
            ProgressView()
        }
    }
}
.onScrollGeometryChange(for: Bool.self) { geometry in
    let maxOffset = geometry.contentSize.height - geometry.containerSize.height
    let currentOffset = geometry.contentOffset.y
    return currentOffset >= maxOffset - 100 // 100pt threshold
} action: { wasNearBottom, isNearBottom in
    if isNearBottom && !wasNearBottom {
        Task { await loadMoreItems() }
    }
}
```

### 3. Scroll Progress (0.0 to 1.0)

```swift
@State private var scrollProgress: CGFloat = 0

ScrollView {
    content
}
.onScrollGeometryChange(for: CGFloat.self) { geometry in
    let maxOffset = geometry.contentSize.height - geometry.containerSize.height
    guard maxOffset > 0 else { return 0 }
    return min(max(geometry.contentOffset.y / maxOffset, 0), 1)
} action: { _, newProgress in
    scrollProgress = newProgress
}
```

### 4. Parallax Header Effect

```swift
@State private var headerOffset: CGFloat = 0

ScrollView {
    VStack(spacing: 0) {
        Image("hero")
            .resizable()
            .aspectRatio(contentMode: .fill)
            .frame(height: 300)
            .offset(y: headerOffset)
            .clipped()

        ContentView()
    }
}
.onScrollGeometryChange(for: CGFloat.self) { geometry in
    geometry.contentOffset.y
} action: { _, offset in
    headerOffset = offset > 0 ? 0 : -offset * 0.5
}
```

### 5. Scroll Direction Detection

```swift
enum ScrollDirection { case up, down, idle }

@State private var scrollDirection: ScrollDirection = .idle

ScrollView {
    content
}
.onScrollGeometryChange(for: CGFloat.self) { geometry in
    geometry.contentOffset.y
} action: { oldOffset, newOffset in
    let delta = newOffset - oldOffset
    if delta > 2 {
        scrollDirection = .down
    } else if delta < -2 {
        scrollDirection = .up
    }
}
```

### 6. Content Size Tracking

```swift
@State private var hasScrollableContent = false

ScrollView {
    content
}
.onScrollGeometryChange(for: Bool.self) { geometry in
    geometry.contentSize.height > geometry.containerSize.height
} action: { _, isScrollable in
    hasScrollableContent = isScrollable
}
```

---

## ScrollPosition (iOS 18)

iOS 18 also introduces `ScrollPosition` for programmatic scroll control with identity-based or offset-based positioning.

```swift
@State private var scrollPosition = ScrollPosition(edge: .top)

ScrollView {
    LazyVStack {
        ForEach(items) { item in
            ItemRow(item: item)
                .id(item.id)
        }
    }
}
.scrollPosition($scrollPosition)

// Scroll to specific item
Button("Go to Item") {
    withAnimation {
        scrollPosition.scrollTo(id: targetItem.id, anchor: .center)
    }
}

// Scroll to offset
Button("Scroll to Top") {
    withAnimation {
        scrollPosition.scrollTo(edge: .top)
    }
}

// Scroll to exact point
Button("Scroll to Y=500") {
    withAnimation {
        scrollPosition.scrollTo(point: CGPoint(x: 0, y: 500))
    }
}
```

### Reading Current Position

```swift
// Check if at edge
if scrollPosition.isPositionedByUser {
    // User has scrolled, not programmatically positioned
}

// Combine with onScrollGeometryChange for full control
.onScrollGeometryChange(for: CGPoint.self) { geometry in
    geometry.contentOffset
} action: { _, offset in
    currentOffset = offset
}
```

---

## Migration from Legacy Patterns

### Before (iOS 16-17): GeometryReader Hack

```swift
// OLD - Avoid this pattern
ScrollView {
    content
        .background(
            GeometryReader { geometry in
                Color.clear
                    .preference(
                        key: ScrollOffsetKey.self,
                        value: geometry.frame(in: .named("scroll")).minY
                    )
            }
        )
}
.coordinateSpace(name: "scroll")
.onPreferenceChange(ScrollOffsetKey.self) { value in
    scrollOffset = value // Fires every frame!
}
```

### After (iOS 18+): onScrollGeometryChange

```swift
// NEW - Use this
ScrollView {
    content
}
.onScrollGeometryChange(for: Bool.self) { geometry in
    geometry.contentOffset.y > 100 // Transform to what you need
} action: { _, crossed in
    showTitle = crossed // Only fires when threshold crossed
}
```

### Migration Checklist

- [ ] Replace all `GeometryReader`-in-background patterns with `onScrollGeometryChange`
- [ ] Replace `PreferenceKey` scroll tracking with geometry transform closures
- [ ] Replace `.coordinateSpace(name:)` with direct geometry access
- [ ] Add `@available(iOS 18, *)` guards with fallback to old pattern
- [ ] Use `ScrollPosition` instead of `ScrollViewReader` where possible

### Availability Guard Pattern

```swift
if #available(iOS 18, *) {
    ScrollView {
        content
    }
    .onScrollGeometryChange(for: Bool.self) { geometry in
        geometry.contentOffset.y > threshold
    } action: { _, show in
        withAnimation { showHeader = show }
    }
} else {
    // Fallback to GeometryReader + PreferenceKey pattern
    LegacyScrollTrackingView(content: content, showHeader: $showHeader)
}
```

---

## Performance Guidelines

### Do

- Transform to the **minimal type** needed (Bool for thresholds, CGFloat for progress)
- Use `Bool` transforms for show/hide decisions — fires only on crossing
- Gate continuous values behind meaningful thresholds
- Combine with `withAnimation` for smooth state transitions

### Don't

- Don't transform to `ScrollGeometry` itself (defeats deduplication)
- Don't store raw `contentOffset` unless you genuinely need continuous tracking
- Don't forget that `action` closure runs on main thread — keep it lightweight
- Don't use this for per-frame animation — use `.visualEffect` or `.scrollTransition` instead

### When to Use What

| Need | API |
|------|-----|
| Scroll position threshold (show/hide) | `onScrollGeometryChange` with Bool transform |
| Scroll progress (0-1) | `onScrollGeometryChange` with CGFloat transform |
| Per-item scroll effects | `.scrollTransition` (iOS 17+) |
| Per-item visual effects based on position | `.visualEffect` (iOS 17+) |
| Programmatic scroll-to | `ScrollPosition` (iOS 18+) or `ScrollViewReader` |
| Paging / snap behavior | `.scrollTargetBehavior` (iOS 17+) |
| Continuous position for animation | `.visualEffect` modifier (avoids state updates) |

---

## scrollTransition Modifier (iOS 17+)

For per-item scroll-based effects (scale, opacity, rotation as items enter/exit), use `.scrollTransition` instead of tracking scroll position:

```swift
ScrollView(.horizontal) {
    LazyHStack(spacing: 16) {
        ForEach(items) { item in
            CardView(item: item)
                .scrollTransition { content, phase in
                    content
                        .opacity(phase.isIdentity ? 1 : 0.3)
                        .scaleEffect(phase.isIdentity ? 1 : 0.8)
                        .rotationEffect(.degrees(phase.isIdentity ? 0 : -5))
                }
        }
    }
    .scrollTargetLayout()
}
.scrollTargetBehavior(.viewAligned)
```

### ScrollTransitionPhase

```swift
enum ScrollTransitionPhase {
    case topLeading    // Item approaching from top/leading
    case identity      // Item is fully visible
    case bottomTrailing // Item departing toward bottom/trailing

    var isIdentity: Bool  // True when item is in the visible area
    var value: Double     // -1.0 (entering) → 0.0 (visible) → 1.0 (exiting)
}
```

---

*iOS 18+ ScrollGeometry Patterns — Huxley Mobile Development*
*The definitive reference for modern scroll position tracking in SwiftUI*
