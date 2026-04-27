import 'dart:typed_data';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';


class ImagePreviewPage extends StatelessWidget {
  final Uint8List imageBytes;

  const ImagePreviewPage({super.key, required this.imageBytes});


  Future<void> downloadImage(BuildContext context) async {
    try {
      Directory dir;

      if (Platform.isAndroid) {
        dir = Directory('/storage/emulated/0/Download');

        /// 🔥 ensure folder exists
        if (!await dir.exists()) {
          await dir.create(recursive: true);
        }
      } else {
        dir = await getApplicationDocumentsDirectory();
      }

      final filePath =
          "${dir.path}/image_${DateTime.now().millisecondsSinceEpoch}.jpg";

      final file = File(filePath);

      await file.writeAsBytes(imageBytes);

      print("📁 Saved at: $filePath");

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("✅ Saved to Downloads")),
      );
    } catch (e) {
      print("❌ Download error: $e");

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("❌ Failed to save image")),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black, // 🔥 better preview look
      appBar: AppBar(
        backgroundColor: Colors.black,
        title: Text("Preview"),
        actions: [
          IconButton(
            icon: Icon(Icons.download),
            onPressed: () => downloadImage(context),
          )
        ],
      ),
      body: SizedBox.expand(
        child: InteractiveViewer(
          minScale: 1,
          maxScale: 4,
          child: Center(
            child: Image.memory(
              imageBytes,
              fit: BoxFit.contain, // 🔥 fits entire screen properly
              width: double.infinity,
              height: double.infinity,
            ),
          ),
        ),
      ),
    );
  }
}