// lib/screens/camera_capture_screen.dart
import 'dart:io';
import 'dart:typed_data';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:image/image.dart' as img;
import 'package:provider/provider.dart';
import '../providers/scan_provider.dart';
import '../models/scan_model.dart';
import '../theme/app_theme.dart';
import 'results_screen.dart';

class CameraCaptureScreen extends StatefulWidget {
  const CameraCaptureScreen({super.key});

  @override
  State<CameraCaptureScreen> createState() => _CameraCaptureScreenState();
}

class _CameraCaptureScreenState extends State<CameraCaptureScreen> {
  CameraController? _cameraController;
  List<CameraDescription> _cameras = [];
  bool _isCameraReady = false;
  bool _isPermissionDenied = false;
  bool _isSimulatedMode = false;

  @override
  void initState() {
    super.initState();
    _initializeCamera();
  }

  Future<void> _initializeCamera() async {
    try {
      _cameras = await availableCameras();
      if (_cameras.isNotEmpty) {
        _cameraController = CameraController(
          _cameras.first,
          ResolutionPreset.high,
          enableAudio: false,
        );
        await _cameraController!.initialize();
        if (mounted) {
          setState(() {
            _isCameraReady = true;
            _isPermissionDenied = false;
            _isSimulatedMode = false;
          });
        }
      } else {
        // Fallback to simulated high-fidelity capture for emulators / tests
        setState(() {
          _isSimulatedMode = true;
          _isCameraReady = true;
        });
      }
    } catch (e) {
      setState(() {
        _isPermissionDenied = true;
        _isSimulatedMode = true; // Allow testing in headless/emulator environments
        _isCameraReady = true;
      });
    }
  }

  /// Generates a realistic 640x640 synthetic onion sample image for testing & emulator paths
  Uint8List _generateRealisticOnionSampleBytes(SamplingAngle angle) {
    final image = img.Image(width: 640, height: 640);
    // Fill neutral light background (procurement tray)
    img.fill(image, color: img.ColorRgb8(235, 235, 230));

    final random = Random(angle.index * 17 + 42);
    // Draw 9-16 realistic onion ellipses with reddish-brown copper skins
    final int onionCount = 12;
    for (int i = 0; i < onionCount; i++) {
      final int row = i ~/ 4;
      final int col = i % 4;
      final int cx = (col * 140 + 100 + random.nextInt(20)).clamp(50, 590);
      final int cy = (row * 140 + 100 + random.nextInt(20)).clamp(50, 590);
      final int radiusX = (45 + random.nextInt(18)).clamp(30, 70);
      final int radiusY = (42 + random.nextInt(18)).clamp(30, 70);

      // Distinct colors for defects: mostly healthy copper, occasional green sprout or dark rot
      img.ColorRgb8 onionColor;
      if (i == 3) {
        // Sprouted green defect
        onionColor = img.ColorRgb8(120, 160, 40);
      } else if (i == 7) {
        // Rotten defect
        onionColor = img.ColorRgb8(40, 35, 30);
      } else if (i == 10) {
        // Undersized defect
        onionColor = img.ColorRgb8(180, 100, 50);
      } else {
        // Grade A Healthy Onion Copper-Red
        onionColor = img.ColorRgb8(190 + random.nextInt(30), 105 + random.nextInt(25), 60);
      }

      img.fillCircle(image, x: cx, y: cy, radius: (radiusX + radiusY) ~/ 2, color: onionColor);
    }

    return Uint8List.fromList(img.encodeJpg(image, quality: 90));
  }

  Future<void> _handleCapture() async {
    final scanProvider = context.read<ScanProvider>();
    if (scanProvider.isProcessing) return;

    // Every capture is one VIEW of the same physical batch (never new
    // onions). The suggested angle cycles so the 10-15 view set keeps
    // covering fresh perspectives.
    final angle = scanProvider.nextAngle;

    Uint8List imageBytes;
    if (!_isSimulatedMode && _cameraController != null && _cameraController!.value.isInitialized) {
      final xFile = await _cameraController!.takePicture();
      imageBytes = await File(xFile.path).readAsBytes();
    } else {
      imageBytes = _generateRealisticOnionSampleBytes(angle);
    }

    final success = await scanProvider.processCapturedImage(imageBytes, angle);

    if (!success && mounted) {
      // Show Quality Rejection Dialog
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Row(
            children: [
              Icon(Icons.error_outline, color: AppTheme.defectRed),
              SizedBox(width: 8),
              Text('Quality Check Failed'),
            ],
          ),
          content: Text(scanProvider.statusMessage ?? 'Please retake with better focus and lighting.'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Retake Photo'),
            ),
          ],
        ),
      );
    } else if (scanProvider.batchCaptureFull && mounted) {
      // View set full (15/15) -> Navigate to Results Screen
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const ResultsScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final scanProvider = context.watch<ScanProvider>();
    final session = scanProvider.currentSession;
    final nextAngle = scanProvider.nextAngle;
    final captured = scanProvider.viewsCaptured;

    String angleName(SamplingAngle a) {
      switch (a) {
        case SamplingAngle.topView:
          return 'Top View';
        case SamplingAngle.sideView:
          return 'Side 45° Angle';
        case SamplingAngle.spreadView:
          return 'Spread / Roll View';
      }
    }

    String angleGuide(SamplingAngle a) {
      switch (a) {
        case SamplingAngle.topView:
          return 'Position camera directly above the batch (90° overhead). Same batch, new perspective.';
        case SamplingAngle.sideView:
          return 'Tilt camera to 45° to capture neck and root profiles. Same batch, new perspective.';
        case SamplingAngle.spreadView:
          return 'Gently roll onions 90° and capture the reverse side. Same batch, new perspective.';
      }
    }

    final stepTitle = scanProvider.batchCaptureFull
        ? 'View set complete'
        : 'View ${captured + 1} of ${ScanProvider.maxBatchViews}: ${angleName(nextAngle)}';
    final stepGuide = scanProvider.batchCaptureFull
        ? 'All ${ScanProvider.maxBatchViews} views captured — finishing opens grading.'
        : '${angleGuide(nextAngle)} Minimum ${ScanProvider.minBatchViews} views before grading.';

    return Scaffold(
      appBar: AppBar(
        title: Text(session != null ? 'Lot: ${session.lotNumber}' : 'Guided Capture'),
        actions: [
          IconButton(
            icon: const Icon(Icons.flash_auto),
            onPressed: () {},
          ),
        ],
      ),
      body: Stack(
        children: [
          // 1. Camera View or Simulation View
          if (!_isSimulatedMode && _cameraController != null && _cameraController!.value.isInitialized)
            Positioned.fill(
              child: CameraPreview(_cameraController!),
            )
          else
            Positioned.fill(
              child: Container(
                color: const Color(0xFF1E1E1E),
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.camera_alt, size: 64, color: Colors.white54),
                      const SizedBox(height: 12),
                      Text(
                        _isSimulatedMode
                            ? 'Simulator Active — synthetic test images only'
                            : 'AI Quality Capture Viewfinder',
                        style: const TextStyle(color: Colors.white, fontSize: 16),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _isSimulatedMode && _isPermissionDenied
                            ? 'Camera permission denied — captures are synthetic and for testing only'
                            : 'Align sample within the calibration guidelines',
                        style: TextStyle(color: Colors.white70, fontSize: 12),
                      ),
                    ],
                  ),
                ),
              ),
            ),

          // 2. Guided Viewfinder Alignment Frame
          Positioned.fill(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 80),
              child: Container(
                decoration: BoxDecoration(
                  border: Border.all(color: AppTheme.primaryLight.withOpacity(0.8), width: 2),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Align(
                  alignment: Alignment.topCenter,
                  child: Padding(
                    padding: const EdgeInsets.all(8.0),
                    child: Text(
                      'Procurement Batch (${session?.assessedOnions ?? '—'} onions declared)',
                      style: const TextStyle(color: Colors.white, fontSize: 11, backgroundColor: Colors.black54),
                    ),
                  ),
                ),
              ),
            ),
          ),

          // 3. Guided Step Instructions Header
          Positioned(
            top: 16,
            left: 16,
            right: 16,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: Colors.black.withOpacity(0.8),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        stepTitle,
                        style: const TextStyle(color: AppTheme.primaryLight, fontWeight: FontWeight.bold, fontSize: 14),
                      ),
                      Text(
                        '$captured/${ScanProvider.maxBatchViews} Views'
                        '${scanProvider.canFinishBatchCapture ? '' : ' (min ${ScanProvider.minBatchViews})'}',
                        style: const TextStyle(color: Colors.white, fontSize: 12),
                      ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Text(
                    stepGuide,
                    style: const TextStyle(color: Colors.white, fontSize: 12),
                  ),
                ],
              ),
            ),
          ),

          // 4. Processing Overlay
          if (scanProvider.isProcessing)
            Positioned.fill(
              child: Container(
                color: Colors.black54,
                child: Center(
                  child: Card(
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const CircularProgressIndicator(color: AppTheme.primaryAmber),
                          const SizedBox(height: 16),
                          Text(
                             scanProvider.statusMessage ?? 'Uploading for AI analysis...',
                            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),

          // 5. Capture Control Footer
          Positioned(
            bottom: 24,
            left: 16,
            right: 16,
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                // Cancel Button
                IconButton(
                  icon: const Icon(Icons.close, color: Colors.white, size: 28),
                  onPressed: () => Navigator.pop(context),
                ),
                
                // Shutter / Capture Button
                GestureDetector(
                  onTap: scanProvider.isProcessing ? null : _handleCapture,
                  child: Container(
                    width: 76,
                    height: 76,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: Colors.white,
                      border: Border.all(color: AppTheme.primaryAmber, width: 4),
                    ),
                    child: Center(
                      child: Container(
                        width: 58,
                        height: 58,
                        decoration: const BoxDecoration(
                          shape: BoxShape.circle,
                          color: AppTheme.primaryAmber,
                        ),
                        child: const Icon(Icons.camera, color: Colors.white, size: 30),
                      ),
                    ),
                  ),
                ),

                // Finish early (allowed once the 10-view minimum is met)
                IconButton(
                  icon: const Icon(Icons.arrow_forward, color: Colors.white, size: 28),
                  tooltip: 'Finish capture and grade',
                  onPressed: scanProvider.canFinishBatchCapture
                      ? () => Navigator.pushReplacement(
                            context,
                            MaterialPageRoute(builder: (_) => const ResultsScreen()),
                          )
                      : null,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _cameraController?.dispose();
    super.dispose();
  }
}
