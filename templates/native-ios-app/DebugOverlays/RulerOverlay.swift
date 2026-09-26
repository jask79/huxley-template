//
//  RulerOverlay.swift
//  Huxley Debug Overlays
//
//  Horizontal and vertical rulers for precise measurements
//  Shows coordinates and distances in points
//

import SwiftUI

#if DEBUG
/// Ruler overlay showing pixel coordinates and measurements
/// Displays horizontal and vertical rulers with coordinate tracking
public struct RulerOverlay: View {
    /// Whether to show horizontal ruler
    let showHorizontal: Bool

    /// Whether to show vertical ruler
    let showVertical: Bool

    /// Ruler color
    let color: Color

    /// Ruler thickness
    let thickness: CGFloat

    /// Current touch/hover location
    @State private var touchLocation: CGPoint?

    public init(
        showHorizontal: Bool = true,
        showVertical: Bool = true,
        color: Color = Color.blue.opacity(0.8),
        thickness: CGFloat = 20
    ) {
        self.showHorizontal = showHorizontal
        self.showVertical = showVertical
        self.color = color
        self.thickness = thickness
    }

    public var body: some View {
        GeometryReader { geometry in
            ZStack {
                // Horizontal ruler (top)
                if showHorizontal {
                    HStack(spacing: 0) {
                        ForEach(0..<Int(geometry.size.width / 10) + 1, id: \.self) { index in
                            let x = CGFloat(index) * 10

                            VStack(spacing: 0) {
                                Rectangle()
                                    .fill(color)
                                    .frame(width: 1, height: index % 10 == 0 ? 15 : (index % 5 == 0 ? 10 : 5))

                                if index % 10 == 0 {
                                    Text("\(Int(x))")
                                        .font(.system(size: 8, design: .monospaced))
                                        .foregroundColor(.white)
                                }

                                Spacer()
                            }
                            .frame(width: 10, height: thickness)
                            .background(Color.black.opacity(0.7))
                        }
                    }
                    .frame(height: thickness)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                }

                // Vertical ruler (left)
                if showVertical {
                    VStack(spacing: 0) {
                        ForEach(0..<Int(geometry.size.height / 10) + 1, id: \.self) { index in
                            let y = CGFloat(index) * 10

                            HStack(spacing: 0) {
                                Rectangle()
                                    .fill(color)
                                    .frame(width: index % 10 == 0 ? 15 : (index % 5 == 0 ? 10 : 5), height: 1)

                                if index % 10 == 0 {
                                    Text("\(Int(y))")
                                        .font(.system(size: 8, design: .monospaced))
                                        .foregroundColor(.white)
                                        .rotationEffect(.degrees(-90))
                                        .frame(width: 10)
                                }

                                Spacer()
                            }
                            .frame(width: thickness, height: 10)
                            .background(Color.black.opacity(0.7))
                        }
                    }
                    .frame(width: thickness)
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
                }

                // Crosshair and coordinates (if touch detected)
                if let location = touchLocation {
                    ZStack {
                        // Crosshair lines
                        Path { path in
                            // Horizontal line
                            path.move(to: CGPoint(x: 0, y: location.y))
                            path.addLine(to: CGPoint(x: geometry.size.width, y: location.y))

                            // Vertical line
                            path.move(to: CGPoint(x: location.x, y: 0))
                            path.addLine(to: CGPoint(x: location.x, y: geometry.size.height))
                        }
                        .stroke(Color.yellow, lineWidth: 1)
                        .shadow(color: .black, radius: 1)

                        // Coordinate label
                        Text("(\(Int(location.x)), \(Int(location.y)))")
                            .font(.system(size: 12, design: .monospaced))
                            .padding(4)
                            .background(Color.black.opacity(0.8))
                            .foregroundColor(.yellow)
                            .cornerRadius(4)
                            .position(x: location.x, y: max(location.y - 20, 20))
                    }
                }
            }
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        touchLocation = value.location
                    }
                    .onEnded { _ in
                        touchLocation = nil
                    }
            )
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

// MARK: - Distance Measurement Tool

/// Interactive distance measurement tool
/// Tap to set start point, drag to measure distance
public struct DistanceMeasurementTool: View {
    @State private var startPoint: CGPoint?
    @State private var endPoint: CGPoint?
    @State private var measurements: [(start: CGPoint, end: CGPoint, distance: CGFloat)] = []

    public init() {}

    public var body: some View {
        GeometryReader { geometry in
            ZStack {
                // Draw all completed measurements
                ForEach(Array(measurements.enumerated()), id: \.offset) { index, measurement in
                    MeasurementLine(
                        start: measurement.start,
                        end: measurement.end,
                        distance: measurement.distance
                    )
                }

                // Draw current measurement (if in progress)
                if let start = startPoint, let end = endPoint {
                    MeasurementLine(
                        start: start,
                        end: end,
                        distance: calculateDistance(from: start, to: end),
                        color: .yellow
                    )
                }

                // Clear button
                if !measurements.isEmpty {
                    VStack {
                        HStack {
                            Spacer()

                            Button(action: {
                                measurements.removeAll()
                                startPoint = nil
                                endPoint = nil
                            }) {
                                Image(systemName: "trash")
                                    .foregroundColor(.white)
                                    .padding(8)
                                    .background(Color.red.opacity(0.7))
                                    .cornerRadius(4)
                            }
                            .padding()
                        }

                        Spacer()
                    }
                }
            }
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        if startPoint == nil {
                            startPoint = value.startLocation
                        }
                        endPoint = value.location
                    }
                    .onEnded { value in
                        if let start = startPoint {
                            let distance = calculateDistance(from: start, to: value.location)
                            measurements.append((start: start, end: value.location, distance: distance))
                        }
                        startPoint = nil
                        endPoint = nil
                    }
            )
        }
        .allowsHitTesting(true)
        .accessibilityHidden(true)
    }

    private func calculateDistance(from start: CGPoint, to end: CGPoint) -> CGFloat {
        let dx = end.x - start.x
        let dy = end.y - start.y
        return sqrt(dx * dx + dy * dy)
    }
}

/// Single measurement line with distance label
private struct MeasurementLine: View {
    let start: CGPoint
    let end: CGPoint
    let distance: CGFloat
    let color: Color

    init(start: CGPoint, end: CGPoint, distance: CGFloat, color: Color = .green) {
        self.start = start
        self.end = end
        self.distance = distance
        self.color = color
    }

    var body: some View {
        ZStack {
            // Line
            Path { path in
                path.move(to: start)
                path.addLine(to: end)
            }
            .stroke(color, lineWidth: 2)

            // Start dot
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
                .position(start)

            // End dot
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
                .position(end)

            // Distance label (at midpoint)
            Text("\(Int(distance))pt")
                .font(.system(size: 12, design: .monospaced))
                .padding(4)
                .background(Color.black.opacity(0.8))
                .foregroundColor(color)
                .cornerRadius(4)
                .position(
                    x: (start.x + end.x) / 2,
                    y: (start.y + end.y) / 2
                )
        }
    }
}

// MARK: - View Extension

extension View {
    /// Add rulers to any view for precise measurements
    /// - Parameters:
    ///   - horizontal: Show horizontal ruler (default: true)
    ///   - vertical: Show vertical ruler (default: true)
    ///   - enabled: Whether to show rulers (default: true)
    /// - Returns: View with ruler overlay
    public func debugRulers(
        horizontal: Bool = true,
        vertical: Bool = true,
        enabled: Bool = true
    ) -> some View {
        self.overlay(
            Group {
                if enabled {
                    RulerOverlay(
                        showHorizontal: horizontal,
                        showVertical: vertical
                    )
                }
            }
        )
    }

    /// Add distance measurement tool for measuring between points
    /// - Parameter enabled: Whether to enable the tool (default: true)
    /// - Returns: View with measurement tool
    public func measurementTool(enabled: Bool = true) -> some View {
        self.overlay(
            Group {
                if enabled {
                    DistanceMeasurementTool()
                }
            }
        )
    }
}

// MARK: - Preview

struct RulerOverlay_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 16) {
            Text("Ruler Overlay Example")
                .font(.title)

            Rectangle()
                .fill(Color.blue)
                .frame(width: 200, height: 100)

            Spacer()
        }
        .padding()
        .debugRulers()
    }
}
#endif
