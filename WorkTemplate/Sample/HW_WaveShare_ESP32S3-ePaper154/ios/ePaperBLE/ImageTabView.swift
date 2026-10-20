//  ImageTabView.swift — Tab 2: pick a photo, convert to 1-bit 200x200, upload
import SwiftUI
import PhotosUI

struct ImageTabView: View {
    @EnvironmentObject var ble: BLEManager
    @State private var pick: PhotosPickerItem?
    @State private var preview: UIImage?
    @State private var packed: Data?

    var body: some View {
        NavigationStack {
            VStack(spacing: 20) {
                // Preview of exactly what the e-paper will show (200x200, 1-bit).
                ZStack {
                    RoundedRectangle(cornerRadius: 12).stroke(.secondary)
                    if let preview {
                        Image(uiImage: preview)
                            .interpolation(.none).resizable().scaledToFit()
                            .frame(width: 200, height: 200)
                    } else {
                        Text("Pick a photo").foregroundStyle(.secondary)
                    }
                }
                .frame(width: 216, height: 216)

                PhotosPicker("Choose photo", selection: $pick, matching: .images)

                if ble.uploading {
                    ProgressView(value: ble.uploadProgress) { Text("Uploading… \(Int(ble.uploadProgress*100))%") }
                }
                if !ble.imageStatus.isEmpty {
                    Text("Device: \(ble.imageStatus)").font(.footnote).foregroundStyle(.secondary)
                }

                Button {
                    if let packed { ble.uploadImage(packed) }
                } label: {
                    Label("Send to e-paper", systemImage: "arrow.up.circle.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .disabled(packed == nil || !ble.connected || ble.uploading)

                Text("Tap the device screen to switch between the home info screen and your picture.")
                    .font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)

                Spacer()
            }
            .padding()
            .navigationTitle("Picture")
            .onChange(of: pick) { _, item in
                Task {
                    guard let item,
                          let data = try? await item.loadTransferable(type: Data.self),
                          let ui = UIImage(data: data),
                          let result = ImageConverter.convert(ui) else { return }
                    preview = result.preview
                    packed = result.packed
                }
            }
        }
    }
}
