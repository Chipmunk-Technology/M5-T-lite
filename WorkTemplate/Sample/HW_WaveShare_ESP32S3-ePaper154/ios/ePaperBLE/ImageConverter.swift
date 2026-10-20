//  ImageConverter.swift
//  Resize any photo to 200x200, dither to 1-bit, and pack into the exact byte
//  layout the e-paper firmware expects:
//    5000 bytes, row-major, 25 bytes per row, MSB = leftmost pixel,
//    bit value 1 = WHITE, 0 = BLACK  (matches EPD_DrawColorPixel in firmware).

import UIKit

enum ImageConverter {
    static let W = 200, H = 200
    static let BYTES = 200 * 200 / 8   // 5000

    /// Returns (packedBuffer, previewImage). previewImage is the 1-bit result
    /// upscaled for on-screen preview so the user sees what the device will show.
    static func convert(_ image: UIImage) -> (packed: Data, preview: UIImage)? {
        guard let gray = grayscalePixels(image, w: W, h: H) else { return nil }

        // Floyd–Steinberg dithering on a mutable Float buffer.
        var buf = gray.map { Float($0) }
        func at(_ x: Int, _ y: Int) -> Int { y * W + x }
        for y in 0..<H {
            for x in 0..<W {
                let old = buf[at(x, y)]
                let new: Float = old < 128 ? 0 : 255
                let err = old - new
                buf[at(x, y)] = new
                if x + 1 < W            { buf[at(x+1, y)]   += err * 7/16 }
                if x - 1 >= 0 && y+1 < H { buf[at(x-1, y+1)] += err * 3/16 }
                if y + 1 < H            { buf[at(x,   y+1)] += err * 5/16 }
                if x + 1 < W && y+1 < H { buf[at(x+1, y+1)] += err * 1/16 }
            }
        }

        // Pack to the e-paper buffer (init 0 = all black; set bit for WHITE).
        var packed = [UInt8](repeating: 0, count: BYTES)
        for y in 0..<H {
            for x in 0..<W {
                if buf[at(x, y)] >= 128 {                       // white pixel
                    packed[y * 25 + (x >> 3)] |= (0x80 >> (x & 7))
                }
            }
        }

        let preview = previewImage(from: buf)
        return (Data(packed), preview ?? image)
    }

    /// Draw the image into a 200x200 grayscale (0…255) byte array.
    private static func grayscalePixels(_ image: UIImage, w: Int, h: Int) -> [UInt8]? {
        let cs = CGColorSpaceCreateDeviceGray()
        var pixels = [UInt8](repeating: 255, count: w * h)
        guard let ctx = CGContext(data: &pixels, width: w, height: h, bitsPerComponent: 8,
                                  bytesPerRow: w, space: cs,
                                  bitmapInfo: CGImageAlphaInfo.none.rawValue),
              let cg = image.cgImage else { return nil }
        // Aspect-fill into 200x200, white background.
        ctx.setFillColor(gray: 1, alpha: 1); ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
        let s = max(CGFloat(w) / CGFloat(cg.width), CGFloat(h) / CGFloat(cg.height))
        let dw = CGFloat(cg.width) * s, dh = CGFloat(cg.height) * s
        ctx.draw(cg, in: CGRect(x: (CGFloat(w)-dw)/2, y: (CGFloat(h)-dh)/2, width: dw, height: dh))
        return pixels
    }

    /// Build a black/white UIImage from the dithered buffer for preview.
    private static func previewImage(from buf: [Float]) -> UIImage? {
        var px = [UInt8](repeating: 0, count: W * H)
        for i in 0..<(W*H) { px[i] = buf[i] >= 128 ? 255 : 0 }
        let cs = CGColorSpaceCreateDeviceGray()
        guard let ctx = CGContext(data: &px, width: W, height: H, bitsPerComponent: 8,
                                  bytesPerRow: W, space: cs,
                                  bitmapInfo: CGImageAlphaInfo.none.rawValue),
              let cg = ctx.makeImage() else { return nil }
        return UIImage(cgImage: cg)
    }
}
