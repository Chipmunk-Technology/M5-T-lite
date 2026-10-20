//  InfoTabView.swift — Tab 1: connection + live info + Wi-Fi + name
import SwiftUI

struct InfoTabView: View {
    @EnvironmentObject var ble: BLEManager
    @State private var newName = ""
    @State private var ssid = ""
    @State private var pass = ""

    var body: some View {
        NavigationStack {
            Form {
                Section("Connection") {
                    HStack {
                        Circle().fill(ble.connected ? .green : .secondary).frame(width: 10, height: 10)
                        Text(ble.connected ? "Connected: \(ble.deviceName)" : ble.state)
                        Spacer()
                        if !ble.connected { Button("Scan") { ble.startScan() } }
                    }
                }

                Section("Sensors") {
                    LabeledContent("Temperature", value: "\(ble.temperature) °C")
                    LabeledContent("Humidity", value: "\(ble.humidity) %")
                    LabeledContent("Device time", value: ble.timeString)
                    Button("Set device time to now") { ble.setTimeNow() }
                        .disabled(!ble.connected)
                }

                Section("Bluetooth name") {
                    TextField(ble.deviceName.isEmpty ? "ePaper-154" : ble.deviceName, text: $newName)
                        .autocorrectionDisabled()
                    Button("Rename (device restarts)") {
                        ble.setName(newName); newName = ""
                    }.disabled(!ble.connected || newName.isEmpty)
                }

                Section("Wi-Fi") {
                    TextField("SSID", text: $ssid).autocorrectionDisabled().textInputAutocapitalization(.never)
                    SecureField("Password", text: $pass)
                    HStack {
                        Button("Save") { ble.setWifi(ssid: ssid, pass: pass) }
                        Spacer()
                        Button("Scan") { ble.wifiScan() }
                        Spacer()
                        Button("Connect") { ble.setWifi(ssid: ssid, pass: pass); ble.wifiConnect() }
                    }.disabled(!ble.connected)
                    LabeledContent("Status", value: ble.wifiStatus)
                    if !ble.wifiSSID.isEmpty { LabeledContent("Saved SSID", value: ble.wifiSSID) }
                }
            }
            .navigationTitle("ePaper Device")
        }
    }
}
