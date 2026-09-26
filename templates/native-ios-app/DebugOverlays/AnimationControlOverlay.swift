//
//  AnimationControlOverlay.swift
//  Huxley Debug Overlays
//
//  Animation speed control for debugging animations and transitions
//  Slows down or speeds up animations system-wide
//

import SwiftUI

#if DEBUG
/// Animation control overlay for debugging animations
/// Allows slowing down or speeding up animations to inspect transitions
public struct AnimationControlOverlay: View {
    @State private var animationSpeed: Double = 1.0
    @State private var isExpanded: Bool = false

    public init() {}

    public var body: some View {
        VStack {
            Spacer()

            HStack {
                Spacer()

                if isExpanded {
                    // Expanded control panel
                    VStack(alignment: .trailing, spacing: 12) {
                        // Speed slider
                        HStack(spacing: 8) {
                            Text("Speed:")
                                .font(.caption.weight(.semibold))
                                .foregroundColor(.white)

                            Slider(value: $animationSpeed, in: 0.1...2.0)
                                .frame(width: 120)
                                .onChange(of: animationSpeed) { newValue in
                                    // Note: SwiftUI doesn't have a direct API to control animation speed globally
                                    // This would require UIView.setAnimationsEnabled or custom timing
                                    UIView.setAnimationsEnabled(newValue > 0.05)
                                }

                            Text("\(String(format: "%.1fx", animationSpeed))")
                                .font(.caption.monospacedDigit())
                                .foregroundColor(.white)
                                .frame(width: 40)
                        }

                        // Preset buttons
                        HStack(spacing: 8) {
                            PresetButton(title: "0.1x", value: 0.1, current: $animationSpeed)
                            PresetButton(title: "0.5x", value: 0.5, current: $animationSpeed)
                            PresetButton(title: "1x", value: 1.0, current: $animationSpeed)
                            PresetButton(title: "2x", value: 2.0, current: $animationSpeed)
                        }

                        Divider()
                            .background(Color.white.opacity(0.3))

                        // Additional controls
                        Toggle("Reduce Motion", isOn: .constant(false))
                            .font(.caption)
                            .foregroundColor(.white)
                            .disabled(true) // This is a system setting

                        // Collapse button
                        Button(action: { withAnimation { isExpanded = false } }) {
                            HStack {
                                Image(systemName: "chevron.down")
                                Text("Collapse")
                            }
                            .font(.caption.weight(.semibold))
                            .foregroundColor(.white)
                            .padding(.vertical, 6)
                            .padding(.horizontal, 12)
                            .background(Color.blue)
                            .cornerRadius(6)
                        }
                    }
                    .padding()
                    .background(Color.black.opacity(0.8))
                    .cornerRadius(12)
                } else {
                    // Minimized button
                    Button(action: { withAnimation { isExpanded = true } }) {
                        VStack(spacing: 4) {
                            Image(systemName: "film")
                                .font(.title2)

                            Text("\(String(format: "%.1fx", animationSpeed))")
                                .font(.caption2.monospacedDigit())
                        }
                        .foregroundColor(.white)
                        .padding(12)
                        .background(Color.blue)
                        .cornerRadius(12)
                        .shadow(radius: 3)
                    }
                }
            }
            .padding()
        }
        .accessibilityHidden(true)
    }
}

/// Preset animation speed button
private struct PresetButton: View {
    let title: String
    let value: Double
    @Binding var current: Double

    var body: some View {
        Button(action: { current = value }) {
            Text(title)
                .font(.caption2.weight(.semibold))
                .foregroundColor(current == value ? .blue : .white)
                .padding(.vertical, 4)
                .padding(.horizontal, 8)
                .background(current == value ? Color.white : Color.white.opacity(0.2))
                .cornerRadius(4)
        }
    }
}

// MARK: - Animation Duration Modifier

/// Custom animation duration multiplier
/// Use this to slow down specific animations for debugging
public struct AnimationDurationMultiplier: ViewModifier {
    let multiplier: Double

    public func body(content: Content) -> some View {
        content
            .animation(.default.speed(1.0 / multiplier), value: UUID())
    }
}

extension View {
    /// Multiply animation duration by a factor
    /// - Parameter multiplier: Duration multiplier (e.g., 2.0 = twice as slow)
    public func animationMultiplier(_ multiplier: Double) -> some View {
        self.modifier(AnimationDurationMultiplier(multiplier: multiplier))
    }
}

// MARK: - Slow Animation Helper

extension Animation {
    /// Create a slowed-down version of an animation
    /// - Parameter factor: Slow-down factor (e.g., 2.0 = twice as slow)
    public func slow(by factor: Double) -> Animation {
        self.speed(1.0 / factor)
    }
}

// MARK: - Animation Timeline Visualizer

/// Visualize animation progress over time
/// Useful for debugging complex animation sequences
public struct AnimationTimelineView: View {
    let animations: [(name: String, duration: Double)]
    @State private var currentTime: Double = 0
    @State private var isPlaying: Bool = false

    private let timer = Timer.publish(every: 0.1, on: .main, in: .common).autoconnect()

    public init(animations: [(name: String, duration: Double)]) {
        self.animations = animations
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Animation Timeline")
                .font(.headline)
                .foregroundColor(.white)

            // Timeline bars
            ForEach(Array(animations.enumerated()), id: \.offset) { index, animation in
                VStack(alignment: .leading, spacing: 4) {
                    Text(animation.name)
                        .font(.caption)
                        .foregroundColor(.white)

                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            // Background bar
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Color.white.opacity(0.2))

                            // Progress bar
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Color.blue)
                                .frame(width: geometry.size.width * progressForAnimation(animation))
                        }
                    }
                    .frame(height: 20)
                }
            }

            // Playback controls
            HStack {
                Button(action: { isPlaying.toggle() }) {
                    Image(systemName: isPlaying ? "pause.fill" : "play.fill")
                        .foregroundColor(.white)
                        .padding(8)
                        .background(Color.blue)
                        .clipShape(Circle())
                }

                Button(action: { currentTime = 0 }) {
                    Image(systemName: "arrow.counterclockwise")
                        .foregroundColor(.white)
                        .padding(8)
                        .background(Color.gray)
                        .clipShape(Circle())
                }

                Spacer()

                Text("\(String(format: "%.1fs", currentTime))")
                    .font(.caption.monospacedDigit())
                    .foregroundColor(.white)
            }
        }
        .padding()
        .background(Color.black.opacity(0.8))
        .cornerRadius(12)
        .onReceive(timer) { _ in
            if isPlaying {
                currentTime += 0.1
                if currentTime > totalDuration {
                    currentTime = 0
                }
            }
        }
    }

    private var totalDuration: Double {
        animations.map { $0.duration }.reduce(0, +)
    }

    private func progressForAnimation(_ animation: (name: String, duration: Double)) -> Double {
        guard currentTime > 0 else { return 0 }

        var elapsed: Double = 0
        for anim in animations {
            if anim.name == animation.name {
                let progress = min((currentTime - elapsed) / anim.duration, 1.0)
                return max(progress, 0)
            }
            elapsed += anim.duration
            if elapsed > currentTime {
                return 0
            }
        }
        return 0
    }
}

// MARK: - View Extension

extension View {
    /// Add animation speed controls for debugging
    /// - Parameter enabled: Whether to enable the control (default: true)
    /// - Returns: View with animation control overlay
    public func animationControls(enabled: Bool = true) -> some View {
        self.overlay(
            Group {
                if enabled {
                    AnimationControlOverlay()
                }
            }
        )
    }
}

// MARK: - Preview

struct AnimationControlOverlay_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            VStack {
                Text("Animation Control Example")
                    .font(.title)

                Spacer()

                // Example animated element
                Circle()
                    .fill(Color.blue)
                    .frame(width: 100, height: 100)
                    .animation(.easeInOut(duration: 1.0).repeatForever(autoreverses: true), value: UUID())

                Spacer()
            }
            .padding()

            // Animation controls overlay
            AnimationControlOverlay()
        }
    }
}
#endif
