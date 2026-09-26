//
//  ColorPickerOverlay.swift
//  Huxley Debug Overlays
//
//  Color picker tool for extracting colors from UI
//  Provides SwiftUI Color, UIColor, and hex code formats
//

import SwiftUI

#if DEBUG
/// Color picker overlay for extracting colors from any point on screen
/// Tap to sample color and copy code to clipboard
public struct ColorPickerOverlay: View {
    @State private var selectedLocation: CGPoint?
    @State private var selectedColor: UIColor?
    @State private var showColorInfo: Bool = false
    @State private var copiedFormat: String?

    public init() {}

    public var body: some View {
        GeometryReader { geometry in
            ZStack {
                // Magnifier loupe (when touching)
                if let location = selectedLocation {
                    VStack(spacing: 0) {
                        // Magnified view (would need UIView snapshot in real implementation)
                        Circle()
                            .fill(Color(selectedColor ?? .clear))
                            .frame(width: 80, height: 80)
                            .overlay(
                                Circle()
                                    .stroke(Color.white, lineWidth: 3)
                                    .shadow(radius: 2)
                            )

                        // Crosshair
                        Image(systemName: "plus")
                            .font(.system(size: 12, weight: .bold))
                            .foregroundColor(.white)
                            .padding(4)
                            .background(Color.black.opacity(0.7))
                            .clipShape(Circle())
                    }
                    .position(x: location.x, y: max(location.y - 60, 60))
                }

                // Color information panel
                if showColorInfo, let color = selectedColor {
                    VStack {
                        Spacer()

                        ColorInfoPanel(
                            color: color,
                            onCopy: { format in
                                copiedFormat = format
                                DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                                    copiedFormat = nil
                                }
                            },
                            onClose: {
                                showColorInfo = false
                                selectedColor = nil
                            }
                        )
                        .padding()
                    }
                }

                // "Copied" toast
                if let format = copiedFormat {
                    VStack {
                        Text("Copied \(format) ✓")
                            .font(.caption)
                            .foregroundColor(.white)
                            .padding(8)
                            .background(Color.green.opacity(0.9))
                            .cornerRadius(8)
                            .padding(.top, 50)

                        Spacer()
                    }
                    .transition(.move(edge: .top).combined(with: .opacity))
                    .animation(.easeInOut, value: copiedFormat)
                }
            }
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        selectedLocation = value.location
                        // In real implementation, would capture pixel color here
                        // For now, using a placeholder
                        selectedColor = UIColor.systemBlue
                    }
                    .onEnded { _ in
                        selectedLocation = nil
                        if selectedColor != nil {
                            showColorInfo = true
                        }
                    }
            )
        }
        .accessibilityHidden(true)
    }
}

/// Color information panel showing all format options
private struct ColorInfoPanel: View {
    let color: UIColor
    let onCopy: (String) -> Void
    let onClose: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // Header
            HStack {
                // Color swatch
                RoundedRectangle(cornerRadius: 8)
                    .fill(Color(color))
                    .frame(width: 60, height: 60)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(Color.white.opacity(0.3), lineWidth: 1)
                    )

                VStack(alignment: .leading, spacing: 4) {
                    Text("Sampled Color")
                        .font(.headline)
                        .foregroundColor(.white)

                    Text("Tap format to copy")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.7))
                }

                Spacer()

                Button(action: onClose) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title2)
                        .foregroundColor(.white.opacity(0.7))
                }
            }

            Divider()
                .background(Color.white.opacity(0.3))

            // Format options
            ColorFormatButton(
                title: "SwiftUI Color",
                code: swiftUIColorCode,
                onTap: { onCopy("SwiftUI Color") }
            )

            ColorFormatButton(
                title: "UIColor",
                code: uiColorCode,
                onTap: { onCopy("UIColor") }
            )

            ColorFormatButton(
                title: "Hex",
                code: hexCode,
                onTap: { onCopy("Hex") }
            )

            ColorFormatButton(
                title: "RGB",
                code: rgbCode,
                onTap: { onCopy("RGB") }
            )
        }
        .padding()
        .background(Color.black.opacity(0.9))
        .cornerRadius(16)
    }

    private var swiftUIColorCode: String {
        let (r, g, b, a) = rgbaComponents
        return "Color(red: \(String(format: "%.3f", r)), green: \(String(format: "%.3f", g)), blue: \(String(format: "%.3f", b)), opacity: \(String(format: "%.3f", a)))"
    }

    private var uiColorCode: String {
        let (r, g, b, a) = rgbaComponents
        return "UIColor(red: \(String(format: "%.3f", r)), green: \(String(format: "%.3f", g)), blue: \(String(format: "%.3f", b)), alpha: \(String(format: "%.3f", a)))"
    }

    private var hexCode: String {
        let (r, g, b, _) = rgbaComponents
        return String(format: "#%02X%02X%02X", Int(r * 255), Int(g * 255), Int(b * 255))
    }

    private var rgbCode: String {
        let (r, g, b, _) = rgbaComponents
        return "rgb(\(Int(r * 255)), \(Int(g * 255)), \(Int(b * 255)))"
    }

    private var rgbaComponents: (CGFloat, CGFloat, CGFloat, CGFloat) {
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        color.getRed(&r, green: &g, blue: &b, alpha: &a)
        return (r, g, b, a)
    }
}

/// Button for a color format option
private struct ColorFormatButton: View {
    let title: String
    let code: String
    let onTap: () -> Void

    var body: some View {
        Button(action: {
            UIPasteboard.general.string = code
            onTap()
        }) {
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.caption.weight(.semibold))
                    .foregroundColor(.white.opacity(0.7))

                Text(code)
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundColor(.white)
                    .lineLimit(1)
                    .truncationMode(.tail)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(8)
            .background(Color.white.opacity(0.1))
            .cornerRadius(8)
        }
    }
}

// MARK: - View Extension

extension View {
    /// Add color picker tool for extracting colors from UI
    /// - Parameter enabled: Whether to enable the tool (default: true)
    /// - Returns: View with color picker overlay
    public func colorPicker(enabled: Bool = true) -> some View {
        self.overlay(
            Group {
                if enabled {
                    ColorPickerOverlay()
                }
            }
        )
    }
}

// MARK: - Preview

struct ColorPickerOverlay_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 20) {
            Text("Color Picker Example")
                .font(.title)

            HStack(spacing: 16) {
                Circle()
                    .fill(Color.blue)
                    .frame(width: 60, height: 60)

                Circle()
                    .fill(Color.green)
                    .frame(width: 60, height: 60)

                Circle()
                    .fill(Color.orange)
                    .frame(width: 60, height: 60)
            }

            Text("Tap and hold to sample colors")
                .font(.caption)
                .foregroundColor(.secondary)

            Spacer()
        }
        .padding()
        .colorPicker()
    }
}
#endif
