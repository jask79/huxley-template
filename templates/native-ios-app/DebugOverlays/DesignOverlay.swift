//
//  DesignOverlay.swift
//  Huxley Debug Overlays
//
//  Overlay design mockups (from Figma/Sketch) on top of implemented UI
//  for pixel-perfect validation
//

import SwiftUI

#if DEBUG
/// Design mockup overlay for comparing implementation against design files
/// Supports opacity adjustment and blend modes for easy comparison
public struct DesignOverlay: View {
    /// Name of the design image asset
    let imageName: String

    /// Overlay opacity (0.0 to 1.0)
    @State private var opacity: Double = 0.5

    /// Current blend mode
    @State private var blendMode: BlendMode = .normal

    /// Whether controls are visible
    @State private var showControls: Bool = true

    public init(imageName: String) {
        self.imageName = imageName
    }

    public var body: some View {
        ZStack {
            // Design mockup image
            Image(imageName)
                .resizable()
                .aspectRatio(contentMode: .fit)
                .opacity(opacity)
                .blendMode(blendMode)
                .allowsHitTesting(false)

            // Controls (top-right corner)
            if showControls {
                VStack {
                    HStack {
                        Spacer()

                        VStack(alignment: .trailing, spacing: 12) {
                            // Opacity control
                            HStack(spacing: 8) {
                                Text("Opacity:")
                                    .font(.caption)
                                    .foregroundColor(.white)

                                Slider(value: $opacity, in: 0...1)
                                    .frame(width: 100)

                                Text("\(Int(opacity * 100))%")
                                    .font(.caption.monospacedDigit())
                                    .foregroundColor(.white)
                                    .frame(width: 35)
                            }

                            // Blend mode picker
                            HStack(spacing: 8) {
                                Text("Mode:")
                                    .font(.caption)
                                    .foregroundColor(.white)

                                Menu {
                                    Button("Normal") { blendMode = .normal }
                                    Button("Difference") { blendMode = .difference }
                                    Button("Multiply") { blendMode = .multiply }
                                    Button("Screen") { blendMode = .screen }
                                } label: {
                                    Text(blendModeName(blendMode))
                                        .font(.caption)
                                        .foregroundColor(.white)
                                        .padding(.horizontal, 8)
                                        .padding(.vertical, 4)
                                        .background(Color.gray.opacity(0.3))
                                        .cornerRadius(4)
                                }
                            }

                            // Hide button
                            Button(action: { showControls = false }) {
                                Image(systemName: "eye.slash")
                                    .foregroundColor(.white)
                                    .padding(8)
                                    .background(Color.gray.opacity(0.5))
                                    .cornerRadius(4)
                            }
                        }
                        .padding(12)
                        .background(Color.black.opacity(0.7))
                        .cornerRadius(8)
                        .padding()
                    }

                    Spacer()
                }
            } else {
                // Show controls button (minimized)
                VStack {
                    HStack {
                        Spacer()

                        Button(action: { showControls = true }) {
                            Image(systemName: "eye")
                                .foregroundColor(.white)
                                .padding(8)
                                .background(Color.gray.opacity(0.7))
                                .cornerRadius(4)
                        }
                        .padding()
                    }

                    Spacer()
                }
            }
        }
        .accessibilityHidden(true)
    }

    private func blendModeName(_ mode: BlendMode) -> String {
        switch mode {
        case .normal: return "Normal"
        case .difference: return "Difference"
        case .multiply: return "Multiply"
        case .screen: return "Screen"
        default: return "Other"
        }
    }
}

// MARK: - View Extension

extension View {
    /// Overlay a design mockup image for pixel-perfect comparison
    /// - Parameters:
    ///   - imageName: Name of the image asset containing the design
    ///   - enabled: Whether to show the overlay (default: true)
    /// - Returns: View with design overlay
    public func designOverlay(
        _ imageName: String,
        enabled: Bool = true
    ) -> some View {
        self.overlay(
            Group {
                if enabled {
                    DesignOverlay(imageName: imageName)
                }
            }
        )
    }
}

// MARK: - Side-by-Side Comparison View

/// Side-by-side slider comparison between design and implementation
public struct DesignComparisonView: View {
    let designImageName: String
    let implementationView: AnyView

    @State private var sliderPosition: CGFloat = 0.5

    public init<Content: View>(
        designImageName: String,
        @ViewBuilder implementation: () -> Content
    ) {
        self.designImageName = designImageName
        self.implementationView = AnyView(implementation())
    }

    public var body: some View {
        GeometryReader { geometry in
            ZStack {
                // Implementation view (left side)
                implementationView
                    .frame(width: geometry.size.width)
                    .mask(
                        Rectangle()
                            .frame(width: geometry.size.width * sliderPosition)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    )

                // Design image (right side)
                Image(designImageName)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .frame(width: geometry.size.width)
                    .mask(
                        Rectangle()
                            .frame(width: geometry.size.width * (1 - sliderPosition))
                            .frame(maxWidth: .infinity, alignment: .trailing)
                    )

                // Slider handle
                VStack {
                    Spacer()

                    Rectangle()
                        .fill(Color.white)
                        .frame(width: 4)
                        .shadow(radius: 2)
                        .overlay(
                            Image(systemName: "arrow.left.and.right")
                                .foregroundColor(.white)
                                .font(.caption)
                                .padding(4)
                                .background(Color.blue)
                                .cornerRadius(4)
                                .shadow(radius: 2)
                        )
                        .position(
                            x: geometry.size.width * sliderPosition,
                            y: geometry.size.height / 2
                        )
                        .gesture(
                            DragGesture()
                                .onChanged { value in
                                    sliderPosition = min(max(value.location.x / geometry.size.width, 0), 1)
                                }
                        )

                    Spacer()
                }
            }
        }
        .accessibilityHidden(true)
    }
}

// MARK: - Preview

struct DesignOverlay_Previews: PreviewProvider {
    static var previews: some View {
        VStack {
            Text("Design Overlay Example")
                .font(.title)

            Text("Add your design mockup image to Assets.xcassets")
                .font(.caption)
                .foregroundColor(.secondary)

            Spacer()
        }
        .padding()
        // Uncomment when you have a design image:
        // .designOverlay("figma-home-screen")
    }
}
#endif
