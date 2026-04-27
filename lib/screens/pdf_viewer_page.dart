import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_pdfview/flutter_pdfview.dart';
import 'package:path_provider/path_provider.dart';

class PdfViewerPage extends StatefulWidget {
  final Uint8List bytes;

  const PdfViewerPage({super.key, required this.bytes});

  @override
  State<PdfViewerPage> createState() => _PdfViewerPageState();
}

class _PdfViewerPageState extends State<PdfViewerPage> {
  String? filePath;

  @override
  void initState() {
    super.initState();
    _loadPdf();
  }

  Future<void> _downloadPdf() async {
    try {
      final dir = await getExternalStorageDirectory();

      final file = File(
        "${dir!.path}/PDF_${DateTime.now().millisecondsSinceEpoch}.pdf",
      );

      await file.writeAsBytes(widget.bytes);

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("PDF saved successfully ✅")),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Failed to save PDF ❌")),
      );
    }
  }

  Future<void> _loadPdf() async {
    final dir = await getTemporaryDirectory();
    final file = File("${dir.path}/temp.pdf");

    await file.writeAsBytes(widget.bytes, flush: true);

    setState(() {
      filePath = file.path;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (filePath == null) {
      return Scaffold(
        // appBar: AppBar(title: Text("Loading PDF...")),
        appBar: AppBar(
          title: Text("PDF Document"),
          actions: [
            IconButton(
              icon: Icon(Icons.download),
              onPressed: _downloadPdf,
            )
          ],
        ),
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      appBar: AppBar(title: Text("PDF Document")),
      body: PDFView(
        filePath: filePath!,
      ),
    );
  }
}