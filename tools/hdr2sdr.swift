// hdr2sdr — tonemap an HDR (HLG/PQ, bt2020) video to SDR bt709 using Apple's system tonemapper.
// This is the same HDR->SDR path Photos/QuickTime use, so the output matches how the clip looks
// on-device instead of the washed-out result you get from passing HDR through as 8-bit.
//
//   swiftc -O tools/hdr2sdr.swift -o tools/hdr2sdr
//   tools/hdr2sdr <input.mov> <output.mp4>
//
// Reads frames as SDR-tagged BGRA (AVFoundation tonemaps on read), writes H.264 bt709.
import AVFoundation
import Foundation

func fail(_ m: String) -> Never { FileHandle.standardError.write((m + "\n").data(using: .utf8)!); exit(1) }

let args = CommandLine.arguments
guard args.count == 3 else { fail("usage: hdr2sdr <input> <output>") }
let inURL = URL(fileURLWithPath: args[1])
let outURL = URL(fileURLWithPath: args[2])
try? FileManager.default.removeItem(at: outURL)

let asset = AVURLAsset(url: inURL)
let sema = DispatchSemaphore(value: 0)
var track: AVAssetTrack?
var natSize = CGSize.zero
var xf = CGAffineTransform.identity
var nomFR: Float = 30

Task {
    let tracks = try await asset.loadTracks(withMediaType: .video)
    guard let t = tracks.first else { fail("no video track") }
    track = t
    natSize = try await t.load(.naturalSize)
    xf = try await t.load(.preferredTransform)
    nomFR = try await t.load(.nominalFrameRate)
    sema.signal()
}
sema.wait()
guard let vtrack = track else { fail("no track") }

// Reader: request BGRA with bt709 working color space -> AVFoundation applies the HDR->SDR tonemap.
let reader = try AVAssetReader(asset: asset)
let readerSettings: [String: Any] = [
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
    AVVideoColorPropertiesKey as String: [
        AVVideoColorPrimariesKey: AVVideoColorPrimaries_ITU_R_709_2,
        AVVideoTransferFunctionKey: AVVideoTransferFunction_ITU_R_709_2,
        AVVideoYCbCrMatrixKey: AVVideoYCbCrMatrix_ITU_R_709_2,
    ],
]
let output = AVAssetReaderTrackOutput(track: vtrack, outputSettings: readerSettings)
output.alwaysCopiesSampleData = false
reader.add(output)

// Writer: H.264, SDR bt709 tagged, preserve orientation.
let writer = try AVAssetWriter(outputURL: outURL, fileType: .mp4)
let px = Int(abs(natSize.width)), py = Int(abs(natSize.height))
let writerSettings: [String: Any] = [
    AVVideoCodecKey: AVVideoCodecType.h264,
    AVVideoWidthKey: px,
    AVVideoHeightKey: py,
    AVVideoColorPropertiesKey: [
        AVVideoColorPrimariesKey: AVVideoColorPrimaries_ITU_R_709_2,
        AVVideoTransferFunctionKey: AVVideoTransferFunction_ITU_R_709_2,
        AVVideoYCbCrMatrixKey: AVVideoYCbCrMatrix_ITU_R_709_2,
    ],
    AVVideoCompressionPropertiesKey: [
        AVVideoAverageBitRateKey: max(8_000_000, px * py * 6),
        AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
    ],
]
let writerInput = AVAssetWriterInput(mediaType: .video, outputSettings: writerSettings)
writerInput.transform = xf
writerInput.expectsMediaDataInRealTime = false
writer.add(writerInput)

guard reader.startReading() else { fail("reader: \(reader.error?.localizedDescription ?? "?")") }
writer.startWriting()
writer.startSession(atSourceTime: .zero)

let queue = DispatchQueue(label: "hdr2sdr")
let done = DispatchSemaphore(value: 0)
writerInput.requestMediaDataWhenReady(on: queue) {
    while writerInput.isReadyForMoreMediaData {
        if let sb = output.copyNextSampleBuffer() {
            if !writerInput.append(sb) { reader.cancelReading(); done.signal(); return }
        } else {
            writerInput.markAsFinished()
            done.signal()
            return
        }
    }
}
done.wait()
if reader.status == .failed { fail("read failed: \(reader.error?.localizedDescription ?? "?")") }
let fin = DispatchSemaphore(value: 0)
writer.finishWriting { fin.signal() }
fin.wait()
if writer.status != .completed { fail("write failed: \(writer.error?.localizedDescription ?? "?")") }
print("ok \(px)x\(py) @\(nomFR)fps -> \(outURL.lastPathComponent)")
