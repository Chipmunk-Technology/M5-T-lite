//  BLEManager.swift
//  Core Bluetooth client for the WaveShare ESP32-S3-ePaper-1.54 (ePaper_BLE firmware).
//  UUIDs MUST match firmware/ePaper_BLE/ePaper_BLE.ino.

import Foundation
import CoreBluetooth

// MARK: - UUIDs (match the firmware)
enum E {
    static let infoSvc = CBUUID(string: "f0a00000-1111-2222-3333-444455556666")
    static let temp    = CBUUID(string: "f0a00001-1111-2222-3333-444455556666")
    static let humi    = CBUUID(string: "f0a00002-1111-2222-3333-444455556666")
    static let time    = CBUUID(string: "f0a00003-1111-2222-3333-444455556666")
    static let name    = CBUUID(string: "f0a00004-1111-2222-3333-444455556666")
    static let wssid   = CBUUID(string: "f0a00005-1111-2222-3333-444455556666")
    static let wpass   = CBUUID(string: "f0a00006-1111-2222-3333-444455556666")
    static let wctrl   = CBUUID(string: "f0a00007-1111-2222-3333-444455556666")
    static let wstat   = CBUUID(string: "f0a00008-1111-2222-3333-444455556666")
    static let imgSvc  = CBUUID(string: "f0b00000-1111-2222-3333-444455556666")
    static let ictrl   = CBUUID(string: "f0b00001-1111-2222-3333-444455556666")
    static let idata   = CBUUID(string: "f0b00002-1111-2222-3333-444455556666")
    static let istat   = CBUUID(string: "f0b00003-1111-2222-3333-444455556666")
}

@MainActor
final class BLEManager: NSObject, ObservableObject {
    @Published var state: String = "Starting…"
    @Published var connected = false
    @Published var deviceName = ""
    @Published var temperature = "--"
    @Published var humidity = "--"
    @Published var timeString = "--"
    @Published var wifiSSID = ""
    @Published var wifiStatus = "idle"
    @Published var imageStatus = ""
    @Published var uploadProgress: Double = 0      // 0…1
    @Published var uploading = false

    private var central: CBCentralManager!
    private var peripheral: CBPeripheral?
    private var chars: [CBUUID: CBCharacteristic] = [:]

    // image upload state
    private var chunks: [Data] = []
    private var chunkIndex = 0

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: nil)
    }

    func startScan() {
        guard central.state == .poweredOn else { return }
        state = "Scanning…"
        central.scanForPeripherals(withServices: [E.infoSvc], options: nil)
    }

    func disconnect() {
        if let p = peripheral { central.cancelPeripheralConnection(p) }
    }

    // MARK: - Writes
    private func write(_ uuid: CBUUID, _ s: String, response: Bool = true) {
        guard let p = peripheral, let c = chars[uuid] else { return }
        p.writeValue(Data(s.utf8), for: c, type: response ? .withResponse : .withoutResponse)
    }

    func setTimeNow() {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        write(E.time, f.string(from: Date()))
    }
    func setName(_ n: String) { write(E.name, n) }           // device reboots to apply
    func setWifi(ssid: String, pass: String) {
        write(E.wssid, ssid); write(E.wpass, pass)
    }
    func wifiScan()    { write(E.wctrl, "scan") }
    func wifiConnect() { write(E.wctrl, "connect") }

    // MARK: - Image upload (packed 5000-byte e-paper buffer)
    func uploadImage(_ packed: Data) {
        guard let p = peripheral, let dataChar = chars[E.idata] else { return }
        let maxLen = max(20, p.maximumWriteValueLength(for: .withoutResponse))
        chunks = stride(from: 0, to: packed.count, by: maxLen).map {
            packed.subdata(in: $0 ..< min($0 + maxLen, packed.count))
        }
        chunkIndex = 0
        uploading = true; uploadProgress = 0; imageStatus = "starting…"
        write(E.ictrl, "START")             // firmware resets its write pointer
        // small delay then stream chunks
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) { [weak self] in self?.sendNext() }
    }

    private func sendNext() {
        guard let p = peripheral, let dataChar = chars[E.idata] else { return }
        while chunkIndex < chunks.count {
            if !p.canSendWriteWithoutResponse { return }   // wait for peripheralIsReady…
            p.writeValue(chunks[chunkIndex], for: dataChar, type: .withoutResponse)
            chunkIndex += 1
            uploadProgress = Double(chunkIndex) / Double(chunks.count)
        }
        // all sent -> commit
        write(E.ictrl, "COMMIT")
        uploading = false
        imageStatus = "sent, committing…"
    }
}

// MARK: - CBCentralManagerDelegate
extension BLEManager: CBCentralManagerDelegate {
    nonisolated func centralManagerDidUpdateState(_ c: CBCentralManager) {
        Task { @MainActor in
            switch c.state {
            case .poweredOn:  self.state = "Ready"; self.startScan()
            case .poweredOff: self.state = "Bluetooth is off"
            case .unauthorized: self.state = "Bluetooth not authorized"
            default: self.state = "Bluetooth unavailable"
            }
        }
    }
    nonisolated func centralManager(_ c: CBCentralManager, didDiscover p: CBPeripheral,
                                    advertisementData: [String: Any], rssi: NSNumber) {
        Task { @MainActor in
            c.stopScan()
            self.peripheral = p
            self.deviceName = p.name ?? "ePaper"
            self.state = "Connecting…"
            p.delegate = self
            c.connect(p, options: nil)
        }
    }
    nonisolated func centralManager(_ c: CBCentralManager, didConnect p: CBPeripheral) {
        Task { @MainActor in self.connected = true; self.state = "Discovering…"; p.discoverServices([E.infoSvc, E.imgSvc]) }
    }
    nonisolated func centralManager(_ c: CBCentralManager, didDisconnectPeripheral p: CBPeripheral, error: Error?) {
        Task { @MainActor in self.connected = false; self.chars.removeAll(); self.state = "Disconnected"; self.startScan() }
    }
}

// MARK: - CBPeripheralDelegate
extension BLEManager: CBPeripheralDelegate {
    nonisolated func peripheral(_ p: CBPeripheral, didDiscoverServices error: Error?) {
        for s in p.services ?? [] { p.discoverCharacteristics(nil, for: s) }
    }
    nonisolated func peripheral(_ p: CBPeripheral, didDiscoverCharacteristicsFor s: CBService, error: Error?) {
        Task { @MainActor in
            for ch in s.characteristics ?? [] {
                self.chars[ch.uuid] = ch
                if ch.properties.contains(.notify) { p.setNotifyValue(true, for: ch) }
                if ch.properties.contains(.read)   { p.readValue(for: ch) }
            }
            if self.chars[E.idata] != nil { self.state = "Connected" }
        }
    }
    nonisolated func peripheral(_ p: CBPeripheral, didUpdateValueFor ch: CBCharacteristic, error: Error?) {
        let s = String(data: ch.value ?? Data(), encoding: .utf8) ?? ""
        Task { @MainActor in
            switch ch.uuid {
            case E.temp:  self.temperature = s
            case E.humi:  self.humidity = s
            case E.time:  self.timeString = s
            case E.name:  self.deviceName = s
            case E.wssid: self.wifiSSID = s
            case E.wstat: self.wifiStatus = s
            case E.istat: self.imageStatus = s
            default: break
            }
        }
    }
    nonisolated func peripheralIsReady(toSendWriteWithoutResponse p: CBPeripheral) {
        Task { @MainActor in self.sendNext() }
    }
}
