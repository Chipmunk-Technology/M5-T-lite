//  ePaperBLEApp.swift — app entry
import SwiftUI

@main
struct ePaperBLEApp: App {
    @StateObject private var ble = BLEManager()
    var body: some Scene {
        WindowGroup {
            ContentView().environmentObject(ble)
        }
    }
}

struct ContentView: View {
    @EnvironmentObject var ble: BLEManager
    var body: some View {
        TabView {
            InfoTabView()
                .tabItem { Label("Device", systemImage: "thermometer.medium") }
            ImageTabView()
                .tabItem { Label("Picture", systemImage: "photo") }
        }
    }
}
