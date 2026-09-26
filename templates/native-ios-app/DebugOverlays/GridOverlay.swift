//
//  GridOverlay.swift
//  Huxley Debug Overlays
//
//  Displays a customizable grid overlay for layout alignment
//  Usage: .overlay(GridOverlay(spacing: 8))
//

import SwiftUI

#if DEBUG
/// Grid overlay for layout alignment and spacing validation
/// Shows horizontal and vertical grid lines at specified intervals
public struct GridOverlay: View {
    /// Grid spacing in points
    let spacing: CGFloat

    /// Grid line color
    let color: Color

    /// Grid line width
    let lineWidth: CGFloat

    /// Whether to show major grid lines (every 5th line)
    let showMajorLines: Bool

    public init(
        spacing: CGFloat = 8,
        color: Color = Color.red.opacity(0.3),
        lineWidth: CGFloat = 0.5,
        showMajorLines: Bool = true
    ) {
        self.spacing = spacing
        self.color = color
        self.lineWidth = lineWidth
        self.showMajorLines = showMajorLines
    }

    public var body: some View {
        GeometryReader { geometry in
            ZStack {
                // Vertical lines
                ForEach(0..<Int(geometry.size.width / spacing) + 1, id: \.self) { index in
                    let x = CGFloat(index) * spacing
                    let isMajor = index % 5 == 0

                    Path { path in
                        path.move(to: CGPoint(x: x, y: 0))
                        path.addLine(to: CGPoint(x: x, y: geometry.size.height))
                    }
                    .stroke(
                        showMajorLines && isMajor ? color.opacity(0.6) : color,
                        lineWidth: showMajorLines && isMajor ? lineWidth * 2 : lineWidth
                    )
                }

                // Horizontal lines
                ForEach(0..<Int(geometry.size.height / spacing) + 1, id: \.self) { index in
                    let y = CGFloat(index) * spacing
                    let isMajor = index % 5 == 0

                    Path { path in
                        path.move(to: CGPoint(x: 0, y: y))
                        path.addLine(to: CGPoint(x: geometry.size.width, y: y))
                    }
                    .stroke(
                        showMajorLines && isMajor ? color.opacity(0.6) : color,
                        lineWidth: showMajorLines && isMajor ? lineWidth * 2 : lineWidth
                    )
                }
            }
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

// MARK: - View Extension for Easy Usage

extension View {
    /// Add a grid overlay to any view for layout debugging
    /// - Parameters:
    ///   - spacing: Grid spacing in points (default: 8)
    ///   - color: Grid line color (default: red with opacity)
    ///   - enabled: Whether to show the grid (default: true)
    /// - Returns: View with grid overlay
    public func debugGrid(
        spacing: CGFloat = 8,
        color: Color = Color.red.opacity(0.3),
        enabled: Bool = true
    ) -> some View {
        self.overlay(
            Group {
                if enabled {
                    GridOverlay(spacing: spacing, color: color)
                }
            }
        )
    }
}

// MARK: - Preview

struct GridOverlay_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 16) {
            Text("Grid Overlay Example")
                .font(.title)

            HStack(spacing: 8) {
                Rectangle()
                    .fill(Color.blue)
                    .frame(width: 64, height: 64)

                Rectangle()
                    .fill(Color.green)
                    .frame(width: 64, height: 64)

                Rectangle()
                    .fill(Color.orange)
                    .frame(width: 64, height: 64)
            }

            Spacer()
        }
        .padding()
        .debugGrid(spacing: 8)
    }
}
#endif
