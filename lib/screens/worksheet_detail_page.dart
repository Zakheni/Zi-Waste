import 'dart:convert';
import 'dart:io';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:driver_app/screens/pdf_viewer_page.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import '../services/local_db.dart';
import '../services/network_service.dart';
import '../services/odoo_service.dart' hide safeString;
import '../services/sync_service.dart';

import 'dart:typed_data';
import 'package:signature/signature.dart';
import 'package:image_picker/image_picker.dart';

import 'image _preview_page.dart';

class WorksheetDetailPage extends StatefulWidget {
  final Map worksheet;
  final int worksheetId; // ✅ ADD THIS

  const WorksheetDetailPage({
    super.key,
    required this.worksheet,
    required this.worksheetId, // ✅ ADD THIS
  });

  @override
  State<WorksheetDetailPage> createState() => _WorksheetDetailPageState();
}

class _WorksheetDetailPageState extends State<WorksheetDetailPage> {
  final service = OdooService();

  late TextEditingController arrivalController;
  late TextEditingController returnController;
  late TextEditingController kmController;
  late TextEditingController notesController;
  late TextEditingController qtyController;

  String? manifest;
  String? weighbridge;
  String? safety;


  /// ✅ ADD THESE HERE
  final SignatureController _driverController = SignatureController();
  final SignatureController _providerController = SignatureController();

  Map<String, dynamic> worksheet = {};

  List allDroppedBins = [];

  List units = [];
  int? selectedUnit;

  List pickupPoints = [];
  List bins = [];

  int? selectedPickup;
  List<int> selectedLifted = [];
  List<int> selectedDropped = [];

  List<Map<String, dynamic>> images = [];

  List managers = [];
  int? selectedManagerId;


  List formatLines(List lines) {
    return lines.map((l) {
      return [
        0,
        0,
        {
          "pickup_point_id": l["pickup_point_id"],
          "dropoff_point_id": l["dropoff_point_id"],

          "bin_lifted_ids": [
            [6, 0, l["bin_lifted_ids"] ?? []],
          ],

          "bin_dropped_ids": [
            [6, 0, l["bin_dropped_ids"] ?? []],
          ],
        },
      ];
    }).toList();
  }


  Widget buildImage(String? base64, BuildContext context) {
    if (base64 == null || base64.isEmpty) {
      return Text("No image");
    }

    final bytes = OdooService().safeDecode(base64);

    if (bytes == null) {
      return Text("Invalid image");
    }

    return GestureDetector(
      onTap: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => ImagePreviewPage(imageBytes: bytes),
          ),
        );
      },
      child: Image.memory(
        bytes,
        height: 120,
        fit: BoxFit.cover,
      ),
    );
  }


  Uint8List? decodeBase64Image(dynamic base64String) {
    if (base64String == null ||
        base64String == false ||
        base64String == "") {
      return null;
    }

    try {
      return base64Decode(base64String);
    } catch (e) {
      print("Image decode error: $e");
      return null;
    }
  }

  bool isPdf(String base64) {
    return base64.startsWith("JVBER"); // PDF signature
  }

  Future<Map<String, dynamic>?> pickPdf() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf'],
        withData: true,
      );

      if (result == null || result.files.isEmpty) return null;

      final file = result.files.first;

      final bytes = file.bytes;
      if (bytes == null) return null;

      final base64 = base64Encode(bytes);

      print("📦 FILE SIZE: ${bytes.length}");
      print("📦 BASE64 LENGTH: ${base64.length}");

      return {
        "base64": base64,
        "name": file.name,
      };
    } catch (e) {
      print("❌ PICK ERROR: $e");
      return null;
    }
  }

  Widget buildSignatureCard(String title, String? base64Image) {
    final imageBytes = decodeBase64Image(base64Image);

    return Card(
      elevation: 3,
      margin: EdgeInsets.symmetric(vertical: 10),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),

            SizedBox(height: 10),

            Container(
              height: 120,
              width: double.infinity,
              decoration: BoxDecoration(
                border: Border.all(color: Colors.grey),
                borderRadius: BorderRadius.circular(8),
              ),
              child: imageBytes != null
                  ? ClipRRect(
                      borderRadius: BorderRadius.circular(8),
                      child: Image.memory(imageBytes, fit: BoxFit.contain),
                    )
                  : Center(child: Text("No signature")),
            ),
          ],
        ),
      ),
    );
  }


  Widget buildDocumentCard(String title, dynamic base64File) {
    // 🔥 STEP 1: HANDLE ODOO EMPTY VALUES
    if (base64File == null ||
        base64File == false ||
        base64File == 0 ||
        base64File.toString().trim().isEmpty) {
      return _emptyDocCard(title);
    }

    final String base64 = base64File.toString().trim();

    Uint8List? bytes;

    // 🔥 STEP 2: SAFE DECODE
    try {
      bytes = base64Decode(base64);
    } catch (e) {
      print("❌ BASE64 ERROR ($title): $e");
      return _emptyDocCard("$title (corrupted)");
    }

    if (base64.length > 5000000) {
      print("⚠️ FILE TOO LARGE");
    }

    // 🔥 STEP 3: DETECT PDF SAFELY
    final bool pdf = isPdf(base64);

    return Card(
      // key: ValueKey(base64),
      // key: ValueKey(title),
      elevation: 3,
      margin: EdgeInsets.symmetric(vertical: 10),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title,
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),

            SizedBox(height: 10),

            Container(
              height: 120,
              width: double.infinity,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                border: Border.all(color: Colors.grey),
                borderRadius: BorderRadius.circular(8),
              ),

              child: pdf
                  ? Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.picture_as_pdf,
                      size: 40, color: Colors.red),
                  Text("PDF Document"),
                ],
              )
                  : Image.memory(bytes, fit: BoxFit.contain),
            ),

            SizedBox(height: 8),

            ElevatedButton.icon(
              icon: Icon(Icons.open_in_new),
              label: Text("Open Document"),
              onPressed: () {
                if (bytes == null) return;

                Navigator.push(
                  context,
                  MaterialPageRoute(
                    builder: (_) => PdfViewerPage(bytes: bytes!),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Map<String, bool> getRequiredDocs(String service, String wasteType) {
    final isHazardous = wasteType.toLowerCase() == "hazardous";

    if (isHazardous) {
      return {
        "manifest": true,
        "weighbridge": true,
        "safety": true,
      };
    }

    switch (service.toLowerCase()) {
      case "placement of bins":
      case "shunting of bins":
        return {
          "manifest": true,
          "weighbridge": false,
          "safety": false,
        };

      case "waste collection & disposal":
      case "swapping of bins":
      case "removal of bins":
        return {
          "manifest": true,
          "weighbridge": true,
          "safety": false,
        };

      default:
        return {
          "manifest": false,
          "weighbridge": false,
          "safety": false,
        };
    }
  }



  // =========================
  // HELPERS (SAFE ODOO HANDLING)
  // =========================

  Widget _emptyDocCard(String title) {
    return Card(
      elevation: 3,
      margin: EdgeInsets.symmetric(vertical: 10),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title,
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
            SizedBox(height: 10),
            Container(
              height: 120,
              alignment: Alignment.center,
              child: Text("No document"),
            )
          ],
        ),
      ),
    );
  }

  void openSignaturePopup({required bool isDriver}) {
    final controller = SignatureController();

    showDialog(
      context: context,
      builder: (context) {
        return Dialog(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                /// TITLE
                Text(
                  isDriver ? "Driver Signature" : "Service Provider Signature",
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),

                SizedBox(height: 12),

                /// SIGNATURE PAD
                Container(
                  height: 180,
                  decoration: BoxDecoration(
                    border: Border.all(color: Colors.grey.shade300),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Signature(
                    controller: controller,
                    backgroundColor: Colors.white,
                  ),
                ),

                SizedBox(height: 12),

                /// BUTTONS
                Row(
                  children: [
                    /// CLEAR
                    Expanded(
                      child: OutlinedButton(
                        // onPressed: () {
                        //   controller.clear();
                        // },
                        onPressed: () async {
                          controller.clear();

                          print("Clearing signature in Odoo...");

                          await service.updateSignature(
                            worksheetId: widget.worksheet["id"],
                            driverSignature: isDriver ? "" : null,
                            providerSignature: !isDriver ? "" : null,
                          );

                          await refreshWorksheet();

                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text("Signature cleared")),
                          );
                        },
                        child: Text("Clear"),
                      ),
                    ),

                    // Expanded(
                    //   child: OutlinedButton(
                    //     onPressed: () async {
                    //       controller.clear();
                    //
                    //       print("🧹 Clearing signature locally ONLY");
                    //
                    //       /// ❌ DO NOT CALL ODOO
                    //       await LocalDB().updateSignatureLocal(
                    //         widget.worksheet["id"],
                    //         driverSignature: isDriver ? "" : null,
                    //         providerSignature: !isDriver ? "" : null,
                    //       );
                    //
                    //       /// ✅ Update UI immediately
                    //       setState(() {
                    //         if (isDriver) {
                    //           worksheet["driver_signature"] = "";
                    //         } else {
                    //           worksheet["service_provider_signature"] = "";
                    //         }
                    //       });
                    //
                    //       Navigator.pop(context);
                    //
                    //       ScaffoldMessenger.of(context).showSnackBar(
                    //         const SnackBar(content: Text("Signature cleared locally")),
                    //       );
                    //     },
                    //     child: const Text("Clear"),
                    //   ),
                    // ),

                    SizedBox(width: 10),

                    /// SAVE
                    Expanded(
                      child: ElevatedButton(

                        onPressed: () async {
                          final signatureBytes = await controller.toPngBytes();

                          if (signatureBytes == null) return;

                          final base64Signature = base64Encode(signatureBytes);

                          print("BASE64 LENGTH: ${base64Signature.length}");

                          /// 🔥 SAVE (handles BOTH online + offline internally now)
                          bool success = await service.updateSignature(
                            worksheetId: widget.worksheet["id"],
                            driverSignature: isDriver ? base64Signature : null,
                            providerSignature: isDriver ? null : base64Signature,
                          );

                          if (success) {
                            print("✅ SIGNATURE SAVED (ONLINE or OFFLINE)");

                            /// ✅ UPDATE UI IMMEDIATELY (NO REFRESH)
                            // setState(() {
                            //   if (isDriver) {
                            //     widget.worksheet["driver_signature"] = base64Signature;
                            //   } else {
                            //     widget.worksheet["service_provider_signature"] = base64Signature;
                            //   }
                            // });

                            setState(() {
                              if (isDriver) {
                                worksheet["driver_signature"] = base64Signature;
                              } else {
                                worksheet["service_provider_signature"] = base64Signature;
                              }
                            });

                            Navigator.pop(context);
                          } else {
                            print("❌ FAILED TO SAVE SIGNATURE");

                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text("Failed to save signature")),
                            );
                          }
                        },

                        child: Text("Save"),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }



  dynamic parseJsonField(dynamic field) {
    if (field == null) return null;

    dynamic value = field;

    // 🔥 keep decoding until it's no longer a string
    while (value is String) {
      try {
        final decoded = jsonDecode(value);
        if (decoded == value) break;
        value = decoded;
      } catch (e) {
        break;
      }
    }

    return value;
  }

  int? getId(dynamic field) {
    if (field == null) return null;

    if (field is List && field.isNotEmpty) {
      return int.tryParse(field[0].toString());
    }

    if (field is String) {
      try {
        final decoded = jsonDecode(field);
        if (decoded is List && decoded.isNotEmpty) {
          return int.tryParse(decoded[0].toString());
        }
      } catch (_) {}
    }

    return null;
  }

  String getName(dynamic field) {
    field = parseJsonField(field);

    if (field == null || field == false) return "";

    if (field is List && field.length > 1) {
      return field[1];
    }

    return field.toString();
  }

  List<String> getListNames(dynamic field) {
    field = parseJsonField(field); // 🔥 ADD THIS

    if (field == null || field == false) return [];

    if (field is List) {
      return field.map<String>((e) {
        if (e is List && e.length > 1) return e[1];
        if (e is String) return e;
        return e.toString();
      }).toList();
    }

    return [];
  }

  String two(int n) => n.toString().padLeft(2, '0');

  String _formatLocal(dynamic date) {
    if (date == null || date == false) return "";

    DateTime utc = DateTime.parse(date).toUtc();
    DateTime local = utc.toLocal();

    return "${local.year}-${two(local.month)}-${two(local.day)} "
        "${two(local.hour)}:${two(local.minute)}:00";
  }

  @override
  void initState() {
    super.initState();

    worksheet = Map<String, dynamic>.from(widget.worksheet);

    arrivalController = TextEditingController(
      text: widget.worksheet["arrival_time"] == false
          ? ""
          : _formatLocal(widget.worksheet["arrival_time"]),
    );

    returnController = TextEditingController(
      text: widget.worksheet["return_date"] == false
          ? ""
          : _formatLocal(widget.worksheet["return_date"]),
    );

    kmController = TextEditingController(
      text: (widget.worksheet["kilometers"] ?? 0).toString(),
    );

    notesController = TextEditingController(
      text: getName(widget.worksheet["notes_html"]),
    );

    qtyController = TextEditingController(
      text: (widget.worksheet["product_uom_qty"] ?? "").toString(),
    );

    final uom = widget.worksheet["unit_of_measure"];

    if (uom is List && uom.isNotEmpty) {
      selectedUnit = uom[0]; // online
    } else if (uom is int) {
      selectedUnit = uom; // offline ✅ FIX
    }

    final ws = worksheet;

    ws["partner_id"] = parseJsonField(ws["partner_id"]);
    ws["container_type_id"] = parseJsonField(ws["container_type_id"]);
    ws["bin_type_id"] = parseJsonField(ws["bin_type_id"]);
    ws["tank_volume_id"] = parseJsonField(ws["tank_volume_id"]);
    ws["truck_tanker_id"] = parseJsonField(ws["truck_tanker_id"]);

    ws["pickup_point_ids"] = parseJsonField(ws["pickup_point_ids"]);
    ws["bin_lifted_ids"] = parseJsonField(ws["bin_lifted_ids"]);
    ws["bin_dropped_ids"] = parseJsonField(ws["bin_dropped_ids"]);

    loadUnits();
    loadPickupPoints();
    startAutoSyncWatcher(); // 🔥 ADD THIS



    Future.microtask(() async {
      try {
        final online = await NetworkService.isOnline();

        if (online) {
          print("🚀 APP START → AUTO SYNC");

          await SyncService.syncAll();

          final fresh = await service.getWorksheets(forceOnline: true);

          final updated = fresh.firstWhere(
                (w) => w["id"] == widget.worksheet["id"],
            orElse: () => worksheet,
          );

          if (!mounted) return;

          setState(() {
            worksheet = Map<String, dynamic>.from(updated);
          });
        }
      } catch (e) {
        print("❌ INIT SYNC FAILED: $e");
      }
    });

    refreshDocuments();
    loadManagers();
    // loadDocuments();
    //
    // final online = await NetworkService.isOnline();
    // if (online) {
    //   loadDocuments();
    // }

    _init();

    loadImages();
  }

  // Future<void> loadManagers() async {
  //   final data = await service.getManagers();
  //
  //   setState(() {
  //     managers = data;
  //   });
  // }

  Future<void> loadManagers() async {
    bool online = await NetworkService.isOnline();

    if (online) {
      try {
        final data = await service.getManagers();

        /// 🔥 SAVE LOCALLY
        await LocalDB().saveManagers(data);

        setState(() {
          managers = data;
        });

      } catch (e) {
        print("❌ ERROR loading managers online: $e");

        /// 🔁 FALLBACK TO LOCAL
        final local = await LocalDB().getManagers();

        setState(() {
          managers = local;
        });
      }

    } else {
      /// 🔴 OFFLINE MODE
      final local = await LocalDB().getManagers();

      setState(() {
        managers = local;
      });
    }
  }

  Future<void> _init() async {
    worksheet = Map<String, dynamic>.from(widget.worksheet);

    await refreshDocuments(); // ✅ LOCAL FIRST

    final online = await NetworkService.isOnline();

    if (online) {
      await loadDocuments();  // ✅ ONLY if online
    }

    loadUnits();
    loadPickupPoints();
    startAutoSyncWatcher();
    loadImages();
  }

  Future<void> loadDocuments() async{
  // void loadDocuments() async {
    try {
      final docs = await service.getWorksheetDocuments(widget.worksheetId);

      if (docs == null) {
        print("❌ DOCS RETURNED NULL");
        return;
      }

      print("📄 DOCS RAW: $docs");

      // setState(() {
      //   worksheet["manifest_document"] = docs["manifest_document"] ?? "";
      //   worksheet["weighbridge_slip"] = docs["weighbridge_slip"] ?? "";
      //   worksheet["safety_certificate"] = docs["safety_certificate"] ?? "";
      // });

      setState(() {
        // if (docs["manifest_document"] != null && docs["manifest_document"] != false) {
        if (docs["manifest_document"] != null &&
            docs["manifest_document"] != false &&
            docs["manifest_document"].toString().isNotEmpty){
          // worksheet["manifest_document"] = docs["manifest_document"];
          worksheet["manifest_document"] = safeString(docs["manifest_document"]);
        }

        // if (docs["weighbridge_slip"] != null && docs["weighbridge_slip"] != false) {

        if (docs["weighbridge_slip"] != null &&
            docs["weighbridge_slip"] != false &&
            docs["weighbridge_slip"].toString().isNotEmpty){
          // worksheet["weighbridge_slip"] = docs["weighbridge_slip"];
          worksheet["weighbridge_slip"] = safeString(docs["weighbridge_slip"]);

        }

        // if (docs["safety_certificate"] != null && docs["safety_certificate"] != false) {

        if (docs["safety_certificate"] != null &&
            docs["safety_certificate"] != false &&
            docs["safety_certificate"].toString().isNotEmpty){
          // worksheet["safety_certificate"] = docs["safety_certificate"];
          worksheet["safety_certificate"] = safeString(docs["safety_certificate"]);

        }
      });

      print("✅ DOCUMENTS LOADED INTO UI");

    } catch (e) {
      print("❌ DOCUMENT LOAD FAILED: $e");
    }
  }

  startAutoSyncWatcher() {
    Connectivity().onConnectivityChanged.listen((result) async {
      if (!mounted) return;

      final isOnline = !result.contains(ConnectivityResult.none);

      if (isOnline) {
        print("🌐 INTERNET BACK → AUTO SYNC START");

        await SyncService.syncAll();        // 🔥 FULL SYNC
        await refreshWorksheet();           // 🔥 update UI

        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Auto sync completed ✅")),
        );

        print("✅ AUTO SYNC DONE");
      }
    });
  }

  Future<void> updateLocalBins(List lines) async {
    List lifted = [];
    List dropped = [];

    for (var l in lines) {
      /// 🔵 LIFTED
      final liftedBinsList = List<Map<String, dynamic>>.from(
        l["liftedBins"] ?? [],
      );

      for (var id in (l["lifted"] ?? [])) {
        Map<String, dynamic>? found;

        for (var b in liftedBinsList) {
          if (b["id"] == id) {
            found = b;
            break;
          }
        }

        lifted.add([id, found != null ? found["name"] : "Bin $id"]);
      }

      /// 🟠 DROPPED
      final droppedBinsList = List<Map<String, dynamic>>.from(
        l["droppedBins"] ?? [],
      );

      for (var id in (l["dropped"] ?? [])) {
        Map<String, dynamic>? found;

        for (var b in droppedBinsList) {
          if (b["id"] == id) {
            found = b;
            break;
          }
        }

        dropped.add([id, found != null ? found["name"] : "Bin $id"]);
      }
    }

    /// 🔥 UPDATE WORKSHEET MEMORY
    widget.worksheet["bin_lifted_ids"] = lifted;
    widget.worksheet["bin_dropped_ids"] = dropped;

    /// 🔥 SAVE TO SQLITE
    await LocalDB().saveWorksheets([widget.worksheet]);

    /// 🔥 REFRESH UI
    setState(() {});
  }

  Future loadUnits() async {
    final data = await service.getUnits();
    if (!mounted) return;

    setState(() {
      units = data;
    });
  }

  Future loadPickupPoints() async {
    final partnerField = parseJsonField(widget.worksheet["partner_id"]);
    final partnerId = getId(partnerField);

    if (partnerId == null) {
      print("❌ partnerId is null → cannot load pickup points");
      return;
    }

    final data = await service.getPickupPoints(partnerId);

    print("PICKUP POINTS LOADED: $data");

    if (!mounted) return;

    setState(() {
      pickupPoints = data;
    });
  }

  Future pickArrival() async {
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.now(),
    );

    if (time != null) {
      final now = DateTime.now();
      arrivalController.text =
          "${now.year}-${two(now.month)}-${two(now.day)} "
          "${two(time.hour)}:${two(time.minute)}:00";
    }
  }

  Future pickReturn() async {
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.now(),
    );

    if (time != null) {
      final now = DateTime.now();
      returnController.text =
          "${now.year}-${two(now.month)}-${two(now.day)} "
          "${two(time.hour)}:${two(time.minute)}:00";
    }
  }

  @override
  void dispose() {
    arrivalController.dispose();
    returnController.dispose();
    kmController.dispose();
    notesController.dispose();
    qtyController.dispose();
    super.dispose();
  }



  String formatOdooDate(DateTime dt) {
    return dt.toString().substring(0, 19);
  }

  Future<bool> saveWorksheet() async {
    try {
      String arrival = arrivalController.text.trim();
      String returnDate = returnController.text.trim();
      String kmText = kmController.text.trim();
      String notes = notesController.text.trim();
      double qty = double.tryParse(qtyController.text.trim()) ?? 0.0;

      /// 🔥 VALIDATION
      if (arrival.isEmpty ||
          returnDate.isEmpty ||
          kmText.isEmpty ||
          selectedUnit == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("All fields are required")),
        );
        return false;
      }

      int? kilometers = int.tryParse(kmText);

      if (kilometers == null || kilometers <= 0) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Kilometers must be greater than 0")),
        );
        return false;
      }

      DateTime arr = DateTime.parse(arrival).toUtc();
      DateTime ret = DateTime.parse(returnDate).toUtc();

      if (ret.isBefore(arr)) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Return must be after arrival")),
        );
        return false;
      }

      bool online = await NetworkService.isOnline();

      /// 🔴 OFFLINE MODE
      if (!online) {
        await LocalDB().insertPending({
          "worksheet_id": widget.worksheet["id"],
          "arrival_time": arrival,
          "return_date": returnDate,
          "kilometers": kilometers,
          "unit_of_measure": selectedUnit,
          "notes_html": notes,
          "product_uom_qty": qty,
        });

        await LocalDB().saveDocumentLocal(
          worksheetId: widget.worksheet["id"],
          manifest: safeString(worksheet["manifest_document"]),
          weighbridge: safeString(worksheet["weighbridge_slip"]),
          safety: safeString(worksheet["safety_certificate"]),
        );

        print("📦 DOCUMENTS SAVED LOCALLY");

        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("📴 Saved offline")),
        );

        return true;
      }

      /// 🟢 ONLINE MODE
      // final success = await service.updateWorksheet(
      //   int.parse(widget.worksheet["id"].toString()),
      //   arr.toIso8601String().substring(0, 19),
      //   ret.toIso8601String().substring(0, 19),
      //   kilometers,
      //   selectedUnit,
      //   notes,
      //   qty,
      // );

      final success = await service.updateWorksheet(
        int.parse(widget.worksheet["id"].toString()),
        formatOdooDate(arr),   // ✅ FIXED
        formatOdooDate(ret),   // ✅ FIXED
        kilometers,
        selectedUnit,
        notes,
        qty,
      );

      /// 🔥 DEBUG (VERY IMPORTANT)
      print("📡 UPDATE RESULT: $success");

      if (!mounted) return false;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(success ? "✅ Saved" : "❌ Failed")),
      );

      return success;
    } catch (e) {
      print("❌ SAVE ERROR: $e");

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("❌ Unexpected error occurred")),
      );

      return false;
    }
  }


  Future<List<int>?> openBinSelectorDialog(
    BuildContext context,
    List bins,
    List<int> selected, {
    required String title,
  }) async {
    List filtered = List.from(bins);
    List<int> tempSelected = List.from(selected);

    return showDialog<List<int>>(
      context: context,
      builder: (_) {
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              title: Text(title),

              content: SizedBox(
                width: double.maxFinite,
                height: 400,
                child: Column(
                  children: [
                    /// 🔍 SEARCH
                    TextField(
                      decoration: const InputDecoration(
                        hintText: "Search bins...",
                        prefixIcon: Icon(Icons.search),
                      ),
                      onChanged: (value) {
                        setState(() {
                          filtered = bins
                              .where(
                                (b) => b["name"].toLowerCase().contains(
                                  value.toLowerCase(),
                                ),
                              )
                              .toList();
                        });
                      },
                    ),

                    const SizedBox(height: 10),

                    /// 📋 LIST
                    Expanded(
                      child: ListView.builder(
                        itemCount: filtered.length,
                        itemBuilder: (_, i) {
                          final bin = filtered[i];
                          final id = bin["id"];
                          final selected = tempSelected.contains(id);

                          return CheckboxListTile(
                            title: Text(bin["name"]),
                            value: selected,
                            onChanged: (v) {
                              setState(() {
                                if (v == true) {
                                  tempSelected.add(id);
                                } else {
                                  tempSelected.remove(id);
                                }
                              });
                            },
                          );
                        },
                      ),
                    ),
                  ],
                ),
              ),

              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text("Cancel"),
                ),
                ElevatedButton(
                  onPressed: () => Navigator.pop(context, tempSelected),
                  child: const Text("Apply"),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> refreshWorksheet() async {
    try {
      final updated = List<Map<String, dynamic>>.from(
        await service.getWorksheets(),
      );

      final updatedWs = updated.firstWhere(
        (w) => w["id"] == widget.worksheet["id"],
        orElse: () => Map<String, dynamic>.from(widget.worksheet),
      );

      print("Driver signature: ${updatedWs["driver_signature"]}");
      print("Provider signature: ${updatedWs["service_provider_signature"]}");

      /// 🔥 CLEAN JSON FIELDS
      updatedWs["container_type_id"] = parseJsonField(
        updatedWs["container_type_id"],
      );
      updatedWs["bin_type_id"] = parseJsonField(updatedWs["bin_type_id"]);
      updatedWs["tank_volume_id"] = parseJsonField(updatedWs["tank_volume_id"]);
      updatedWs["truck_tanker_id"] = parseJsonField(
        updatedWs["truck_tanker_id"],
      );

      updatedWs["pickup_point_ids"] = parseJsonField(
        updatedWs["pickup_point_ids"],
      );
      updatedWs["bin_lifted_ids"] = parseJsonField(updatedWs["bin_lifted_ids"]);
      updatedWs["bin_dropped_ids"] = parseJsonField(
        updatedWs["bin_dropped_ids"],
      );

      /// 🔥 IMPORTANT FIX: check mounted
      if (!mounted) return;

      /// 🔥 IMPORTANT FIX: DO NOT mutate widget
      setState(() {
        worksheet = Map<String, dynamic>.from(updatedWs);
      });
    } catch (e) {
      print("❌ refreshWorksheet error: $e");
    }
  }

  Future<void> autoRefreshAfterSync() async {
    final online = await NetworkService.isOnline();

    if (!online) return;

    if (!mounted) return; // 🔥 add this

    await refreshWorksheet();
  }

  bool validateBins(List lines, String serviceName) {
    final svc = serviceName.toLowerCase();

    bool hasLifted = false;
    bool hasDropped = false;

    for (var l in lines) {
      if ((l["lifted"] ?? []).isNotEmpty) {
        hasLifted = true;
      }
      if ((l["dropped"] ?? []).isNotEmpty) {
        hasDropped = true;
      }
    }

    if (svc.contains("placement")) {
      if (!hasDropped) {
        showError("Bin Dropped is required for Placement of Bins 🗑️");
        return false;
      }
    } else if (svc.contains("shunting") || svc.contains("removal")) {
      if (!hasLifted) {
        showError("Bin Lifted is required 🗑️");
        return false;
      }
    } else if (svc.contains("collection")) {
      if (!hasLifted) {
        showError("Bin Lifted is required 🚮");
        return false;
      }
    } else if (svc.contains("swapping")) {
      if (!hasLifted || !hasDropped) {
        showError("Both Bin Lifted and Dropped are required 🗑️");
        return false;
      }
    }

    return true;
  }

  void showError(String msg) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(msg), backgroundColor: Colors.red));
  }

  Future openBinDialog() async {
    print("🔥 WORKSHEET OPEN:");
    print(widget.worksheet);

    final ws = worksheet;

    /// 🔥 FIX STRING → LIST
    ws["partner_id"] = parseJsonField(ws["partner_id"]);
    ws["bin_type_id"] = parseJsonField(ws["bin_type_id"]);

    List<Map<String, dynamic>> lines = [];

    final serviceName = getName(
      widget.worksheet["service_requested_id"],
    ).toLowerCase();

    final isPlacement = serviceName.contains("placement");
    final isRemoval = serviceName.contains("removal");
    final isCollection = serviceName.contains("collection");
    final isShunting = serviceName.contains("shunting");
    final isSwap = serviceName.contains("swapping");

    await showDialog(
      context: context,
      builder: (_) {
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              title: const Text("Assign Bins"),

              content: SizedBox(
                width: double.maxFinite,
                child: SingleChildScrollView(
                  child: Column(
                    children: [
                      /// 🔁 LINES
                      ...lines.asMap().entries.map((entry) {
                        var line = entry.value;

                        return Card(
                          margin: const EdgeInsets.only(bottom: 10),
                          child: Padding(
                            padding: const EdgeInsets.all(10),
                            child: Column(
                              children: [
                                /// ✅ PICKUP POINT (NOT FOR PLACEMENT)
                                if (!isPlacement)
                                  DropdownButton<int>(
                                    hint: const Text("Pickup Point"),
                                    value: line["pickup"],
                                    isExpanded: true,
                                    items: pickupPoints
                                        .map<DropdownMenuItem<int>>((p) {
                                          return DropdownMenuItem(
                                            value: p["id"],
                                            child: Text(p["name"]),
                                          );
                                        })
                                        .toList(),

                                    onChanged: (v) async {
                                      line["pickup"] = v;

                                      /// ✅ SAFE ID EXTRACTION
                                      int? getId(dynamic field) {
                                        if (field == null) return null;

                                        if (field is List && field.isNotEmpty) {
                                          return int.tryParse(
                                            field[0].toString(),
                                          );
                                        }

                                        if (field is String) {
                                          try {
                                            final decoded = jsonDecode(field);
                                            if (decoded is List &&
                                                decoded.isNotEmpty) {
                                              return int.tryParse(
                                                decoded[0].toString(),
                                              );
                                            }
                                          } catch (_) {}
                                        }

                                        return null;
                                      }

                                      final partnerId = getId(ws["partner_id"]);
                                      final binTypeId = getId(
                                        ws["bin_type_id"],
                                      );

                                      List lifted = [];
                                      List dropped = [];

                                      /// 🔵 LIFTED BINS
                                      if (v != null) {
                                        /// ✅ PREVENT CRASH
                                        if (partnerId == null ||
                                            binTypeId == null) {
                                          showError("Missing required data ❌");
                                          return;
                                        }

                                        bool online =
                                            await NetworkService.isOnline();

                                        if (online) {
                                          lifted = await service.getLiftedBins(
                                            partnerId,
                                            v,
                                            binTypeId,
                                          );
                                        } else {
                                          lifted = await LocalDB()
                                              .getLiftedBinsLocal(
                                                partnerId,
                                                v,
                                                binTypeId,
                                              );
                                        }
                                      }

                                      /// 🟠 DROPPED BINS
                                      // if (isPlacement && v != null) {
                                      if ((isPlacement ||
                                              isCollection ||
                                              isSwap) &&
                                          v != null) {
                                        if (partnerId == null ||
                                            binTypeId == null) {
                                          print(
                                            "⚠️ Missing IDs → partner: $partnerId, binType: $binTypeId",
                                          );
                                          showError("Missing required data ❌");
                                          return;
                                        }

                                        bool online =
                                            await NetworkService.isOnline();

                                        if (online) {
                                          dropped = await service
                                              .getDroppedBins(binTypeId);
                                        } else {
                                          dropped = await LocalDB()
                                              .getDroppedBinsLocal(binTypeId);
                                        }
                                      }

                                      /// 🐞 DEBUG
                                      print("📍 PICKUP SELECTED: $v");
                                      print("🔵 LIFTED BINS RAW: $lifted");
                                      print("🟠 DROPPED BINS RAW: $dropped");

                                      /// ✅ UPDATE UI
                                      setState(() {
                                        line["liftedBins"] = lifted;
                                        line["droppedBins"] = dropped;
                                      });
                                    },
                                  ),

                                /// ✅ DROPOFF POINT (FOR PLACEMENT / SWAP / SHUNTING)
                                if (isPlacement || isShunting || isSwap)
                                  DropdownButton<int>(
                                    hint: const Text("Drop-off Point"),
                                    value: line["dropoff"],
                                    isExpanded: true,
                                    items: pickupPoints
                                        .map<DropdownMenuItem<int>>((p) {
                                          return DropdownMenuItem(
                                            value: p["id"],
                                            child: Text(p["name"]),
                                          );
                                        })
                                        .toList(),

                                    onChanged: (v) async {
                                      line["dropoff"] = v;

                                      // 🔥 ADD THIS
                                      if (isPlacement) {
                                        line["pickup"] = v; // ✅ CRITICAL FIX
                                      }

                                      final binTypeId =
                                          widget.worksheet["bin_type_id"]?[0];

                                      if (isPlacement && v != null) {
                                        final dropped = await service
                                            .getDroppedBins(binTypeId);

                                        setState(() {
                                          line["droppedBins"] = dropped;
                                        });
                                      }

                                      setState(() {});
                                    },
                                  ),

                                const SizedBox(height: 10),

                                /// 🔵 LIFTED BINS
                                if (!isPlacement)
                                  Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      const Text(
                                        "Bins Lifted",
                                        style: TextStyle(
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),

                                      Wrap(
                                        children: (line["liftedBins"] ?? [])
                                            .take(6)
                                            .map<Widget>((b) {
                                              // final id = b["id"];
                                              print("🐞 BIN RAW: $b");
                                              print(
                                                "🐞 BIN ID TYPE: ${b["id"].runtimeType}",
                                              );
                                              final id =
                                                  int.tryParse(
                                                    b["id"].toString(),
                                                  ) ??
                                                  0;
                                              final selected =
                                                  (line["lifted"] ?? [])
                                                      .contains(id);

                                              return FilterChip(
                                                label: Text(b["name"]),
                                                selected: selected,
                                                onSelected: (s) {
                                                  setState(() {
                                                    line["lifted"] ??= [];

                                                    if (s) {
                                                      line["lifted"].add(id);
                                                    } else {
                                                      line["lifted"].remove(id);
                                                    }
                                                  });
                                                },
                                              );
                                            })
                                            .toList(),
                                      ),

                                      if ((line["liftedBins"] ?? []).length > 6)
                                        TextButton(
                                          onPressed: () async {
                                            final selected =
                                                await openBinSelectorDialog(
                                                  context,
                                                  line["liftedBins"],
                                                  line["lifted"] ?? [],
                                                  title: "Select Lifted Bins",
                                                );

                                            if (selected != null) {
                                              setState(() {
                                                line["lifted"] = selected;
                                              });
                                            }
                                          },
                                          child: const Text("View All"),
                                        ),
                                    ],
                                  ),

                                const SizedBox(height: 10),

                                /// 🟠 DROPPED BINS
                                if (isPlacement || isCollection || isSwap)
                                  Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      const Text(
                                        "Bins Dropped",
                                        style: TextStyle(
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),

                                      Wrap(
                                        children: (line["droppedBins"] ?? [])
                                            .take(6)
                                            .map<Widget>((b) {
                                              // final id = b["id"];
                                              final id =
                                                  int.tryParse(
                                                    b["id"].toString(),
                                                  ) ??
                                                  0;
                                              final selected =
                                                  (line["dropped"] ?? [])
                                                      .contains(id);

                                              return FilterChip(
                                                label: Text(b["name"]),
                                                selected: selected,
                                                onSelected: (s) {
                                                  setState(() {
                                                    line["dropped"] ??= [];

                                                    if (s) {
                                                      line["dropped"].add(id);
                                                    } else {
                                                      line["dropped"].remove(
                                                        id,
                                                      );
                                                    }
                                                  });
                                                },
                                              );
                                            })
                                            .toList(),
                                      ),

                                      if ((line["droppedBins"] ?? []).length >
                                          6)
                                        TextButton(
                                          onPressed: () async {
                                            final selected =
                                                await openBinSelectorDialog(
                                                  context,
                                                  line["droppedBins"],
                                                  line["dropped"] ?? [],
                                                  title: "Select Dropped Bins",
                                                );

                                            if (selected != null) {
                                              setState(() {
                                                line["dropped"] = selected;
                                              });
                                            }
                                          },
                                          child: const Text("View All"),
                                        ),
                                    ],
                                  ),
                              ],
                            ),
                          ),
                        );
                      }),

                      /// ➕ ADD LINE
                      TextButton.icon(
                        onPressed: () async {
                          print("➕ ADD LINE CLICKED");
                          final binTypeId = getId(
                            widget.worksheet["bin_type_id"],
                          );
                          print("🧱 BIN TYPE RAW: $binTypeId");
                          if (binTypeId == null) {
                            showError("Bin Type missing ❌");
                            return;
                          }

                          List dropped = [];

                          if (isPlacement || isCollection || isSwap) {
                            dropped = await service.getDroppedBins(binTypeId);
                          }

                          setState(() {
                            lines.add({
                              "droppedBins": dropped, // ✅ preload
                            });
                          });
                        },

                        icon: const Icon(Icons.add),
                        label: const Text("Add Line"),
                      ),
                    ],
                  ),
                ),
              ),

              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text("Cancel"),
                ),

                ElevatedButton(
                  onPressed: () async {
                    if (lines.isEmpty) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text("Add at least one line")),
                      );
                      return;
                    }

                    for (var l in lines) {
                      if (l["pickup"] == null && l["dropoff"] == null) {
                        showError("Please select Pickup or Drop-off point 📍");
                        return;
                      }
                    }

                    // ✅ FORMAT AFTER VALIDATION
                    final formattedLines = lines.map((l) {
                      final pickup = l["pickup"] ?? l["dropoff"];

                      return {
                        "pickup_point_id": pickup,
                        "dropoff_point_id": l["dropoff"] ?? pickup,
                        "bin_lifted_ids": l["lifted"] ?? [],
                        "bin_dropped_ids": l["dropped"] ?? [],
                      };
                    }).toList();

                    print("SUBMIT LINES: $formattedLines");

                    // 🔥 VALIDATE FIRST (BEFORE SUBMIT)
                    if (!validateBins(lines, serviceName)) {
                      return; // ❌ STOP HERE
                    }

                    await submitBins(formattedLines);
                    updateLocalBins(lines);

                    // 🔥 FORCE REFRESH FROM SERVER

                    final updated = List<Map<String, dynamic>>.from(
                      await service.getWorksheets(),
                    );

                    // 🔥 FIND CURRENT WORKSHEET
                    final updatedWs = updated.firstWhere(
                      (w) => w["id"] == widget.worksheet["id"],
                      orElse: () => Map<String, dynamic>.from(widget.worksheet),
                    );

                    // 🔥 UPDATE LOCAL STATE
                    setState(() {
                      widget.worksheet.clear();
                      widget.worksheet.addAll(updatedWs);
                    });

                    Navigator.pop(context);
                  },
                  child: const Text("Confirm"),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future submitBins(List lines) async {
    bool online = await NetworkService.isOnline();

    /// 🔴 OFFLINE MODE
    if (!online) {
      for (var l in lines) {
        await LocalDB().saveBinTransaction({
          "worksheet_id": widget.worksheet["id"],
          "pickup_point_id": l["pickup_point_id"],
          "dropoff_point_id": l["dropoff_point_id"],
          "lifted_bins": jsonEncode(l["bin_lifted_ids"] ?? []),
          "dropped_bins": jsonEncode(l["bin_dropped_ids"] ?? []),
        });
      }

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text("Bins saved offline")));

      return;
    }

    /// 🟢 ONLINE MODE (your existing logic)
    final requestId = widget.worksheet["service_request_id"][0];

    final wizardId = await service.createBinWizard(requestId);

    if (wizardId == null) return;

    final formatted = formatLines(lines);

    await service.addWizardLines(wizardId, formatted);

    final success = await service.confirmWizard(wizardId);

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(success ? "Bins Updated" : "Failed")),
    );
  }


  Future<void> refreshDocuments() async {
    final id = worksheet["id"];

    final localDocs = await LocalDB().getDocumentLocal(id);

    if (localDocs != null) {
      setState(() {
        worksheet["manifest_document"] = localDocs["manifest_document"] ?? worksheet["manifest_document"];
        worksheet["weighbridge_slip"] = localDocs["weighbridge_slip"] ?? worksheet["weighbridge_slip"];
        worksheet["safety_certificate"] = localDocs["safety_certificate"] ?? worksheet["safety_certificate"];
      });
    }
  }

  Future<void> takePicture() async {
    final picker = ImagePicker();

    final XFile? image = await picker.pickImage(
      source: ImageSource.camera,
      imageQuality: 30,
      maxWidth: 600,
    );

    if (image == null) return;

    final bytes = await image.readAsBytes();

    if (bytes.length < 1000) {
      print("⚠️ Image too small");
      return;
    }

    final base64Image = base64Encode(bytes);

    print("📦 IMAGE SIZE: ${bytes.length}");
    print("📦 BASE64 SIZE: ${base64Image.length}");

    /// ✅ SAVE LOCALLY FIRST
    await LocalDB().saveImage(
      worksheetId: worksheet["id"],
      filePath: image.path,
    );

    /// ✅ TRY UPLOAD
    bool online = await NetworkService.isOnline();

    if (online) {
      print("🚀 Uploading image to Odoo...");

      final int? serverId = await service.uploadImage(
        worksheetId: worksheet["id"],
        base64: base64Image,
      );

      if (serverId != null) {
        print("✅ Uploaded → server_id: $serverId");

        /// 🔥 UPDATE LOCAL RECORD IMMEDIATELY
        final db = await LocalDB().database;

        await db.update(
          "images",
          {
            "synced": 1,
            "server_id": serverId,
          },
          where: "file_path = ? AND worksheet_id = ?",
          whereArgs: [image.path, worksheet["id"]],
        );
      } else {
        print("❌ Upload failed");
      }
    }

    await loadImages();
  }

  Future<void> pickFromGallery() async {
    try {
      final picker = ImagePicker();

      print("📸 Opening gallery...");

      final XFile? image = await picker.pickImage(
        source: ImageSource.gallery,
        imageQuality: 30,
        maxWidth: 600,
      );

      if (image == null) {
        print("❌ No image selected");
        return;
      }

      final bytes = await image.readAsBytes();

      print("📦 Image size: ${bytes.length}");

      if (bytes.length < 1000) {
        print("⚠️ Image too small");
        return;
      }

      final base64Image = base64Encode(bytes);

      print("📦 BASE64 SIZE: ${base64Image.length}");

      /// ✅ SAVE LOCALLY FIRST
      await LocalDB().saveImage(
        worksheetId: worksheet["id"],
        filePath: image.path,
      );

      /// ✅ TRY UPLOAD
      bool online = await NetworkService.isOnline();

      if (online) {
        print("🚀 Uploading image to Odoo...");

        final int? serverId = await service.uploadImage(
          worksheetId: worksheet["id"],
          base64: base64Image,
        );

        if (serverId != null) {
          print("✅ Uploaded → server_id: $serverId");

          /// 🔥 UPDATE LOCAL RECORD
          final db = await LocalDB().database;

          await db.update(
            "images",
            {
              "synced": 1,
              "server_id": serverId,
            },
            where: "file_path = ? AND worksheet_id = ?",
            whereArgs: [image.path, worksheet["id"]],
          );
        } else {
          print("❌ Upload failed");
        }
      }

      await loadImages();

    } catch (e) {
      print("❌ PICK ERROR: $e");
    }
  }

  Future<void> deleteImage(Map<String, dynamic> image) async {
    final db = LocalDB();
    final service = OdooService();

    final int localId = image["id"];
    final int? serverId = image["server_id"];

    bool online = await NetworkService.isOnline();

    /// 🔥 CASE 1: local-only image
    if (serverId == null) {
      print("🗑️ Local-only image → deleting");

      await db.deleteImageLocal(localId);
      await loadImages();
      return;
    }

    /// 🔥 CASE 2: delete from Odoo
    if (online) {
      print("🌐 Deleting from Odoo → ID $serverId");

      final success = await service.deleteImageFromServer(serverId);

      if (success) {
        print("✅ Deleted from Odoo");

        await db.deleteImageLocal(localId);
      } else {
        print("❌ Failed to delete from Odoo");
        return;
      }
    } else {
      print("📴 Offline → deleting locally only");

      await db.deleteImageLocal(localId);
    }

    await loadImages();
  }


  // Future<void> loadImages() async {
  //   bool online = await NetworkService.isOnline();
  //
  //   if (online) {
  //     try {
  //       final serverImages =
  //       await service.getWorksheetImages(widget.worksheetId);
  //
  //       await LocalDB().saveImagesFromServer(
  //           widget.worksheetId, serverImages);
  //     } catch (e) {
  //       print("ERROR loading server images: $e");
  //     }
  //   }
  //
  //   final localImages =
  //   await LocalDB().getImages(widget.worksheetId);
  //
  //   setState(() {
  //     images = localImages;
  //   });
  // }

  Future<void> loadImages() async {
    final db = LocalDB();
    final service = OdooService();

    final worksheetId = widget.worksheetId;

    bool online = await NetworkService.isOnline();

    print("🌐 ONLINE STATUS: $online");

    /// 🔥 STEP 1: TRY FETCH FROM SERVER
    if (online) {
      try {
        final serverImages =
        await service.getWorksheetImages(worksheetId);

        print("📥 SERVER IMAGES: ${serverImages.length}");

        if (serverImages.isNotEmpty) {
          await db.saveImagesFromServer(
            worksheetId,
            serverImages,
          );
          print("💾 Saved server images locally");
        } else {
          print("⚠️ No images from server");
        }
      } catch (e) {
        print("❌ ERROR loading server images: $e");
      }
    } else {
      print("📴 OFFLINE → loading local images only");
    }

    /// 🔥 STEP 2: ALWAYS LOAD FROM LOCAL DB
    final localImages = await db.getImages(worksheetId);

    print("📸 LOCAL IMAGES COUNT: ${localImages.length}");

    /// 🔥 STEP 3: UPDATE UI
    if (mounted) {
      setState(() {
        images = localImages;
      });
    }
  }


  @override
  Widget build(BuildContext context) {
    final ws = worksheet;
    final serviceName = getName(ws["service_requested_id"]).toLowerCase();

    final isPlacement = serviceName.contains("placement");
    final plannedDateFormatted = _formatLocal(ws["planned_date"]);

    final isBin = getName(
      ws["container_type_id"],
    ).toLowerCase().contains("bin");
    final isTank = getName(
      ws["container_type_id"],
    ).toLowerCase().contains("tank");

    final pickupPoints = getListNames(ws["pickup_point_ids"]);
    final binsLifted = getListNames(ws["bin_lifted_ids"]);
    final binsDropped = getListNames(ws["bin_dropped_ids"]);

    final summary = getName(ws["pickup_point_bins_summary"]);

    final containerType = getName(ws["container_type_id"]);
    final binType = getName(ws["bin_type_id"]);
    final tankVolume = getName(ws["tank_volume_id"]);
    final truck = getName(ws["truck_tanker_id"]);

    print("Driver signature: ${worksheet["driver_signature"]}");
    print("Provider signature: ${worksheet["service_provider_signature"]}");

    print("🔥 BUILD CALLED");
    print("Manifest: ${worksheet["manifest_document"]}");
    print("Weighbridge: ${worksheet["weighbridge_slip"]}");
    print("Safety: ${worksheet["safety_certificate"]}");

    print("📄 LOCAL MANIFEST LENGTH: ${worksheet["manifest_document"]?.length}");


    // final serviceName = worksheet["service_requested_id"]?[1] ?? "";
    final wasteType = worksheet["waste_type_id"]?[1] ?? "";

    final requiredDocs = getRequiredDocs(serviceName, wasteType);

    return Scaffold(
      appBar: AppBar(
        title: Text(getName(ws["name"])),

          actions: [

            /// 🔄 SYNC BUTTON
            IconButton(
              icon: const Icon(Icons.sync),

                onPressed: () async {
                  print("🔄 MANUAL SYNC START");

                  final online = await NetworkService.isOnline();

                  if (!online) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text("No internet connection ❌")),
                    );
                    return;
                  }

                  await SyncService.syncAll();     // 🔥 FULL SYNC
                  await refreshWorksheet();        // 🔥 refresh UI

                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text("Synced successfully ✅")),
                  );

                  print("✅ MANUAL SYNC DONE");
                }

            ),

          ],

      ),

      body: Column(
        children: [
          /// SCROLLABLE CONTENT
          Expanded(
            child: RefreshIndicator(
              onRefresh: refreshWorksheet,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Row(
                    children: [
                      /// ✅ STATUS (from Odoo state)
                      statusPill(getName(ws["state"]), color: Colors.green),

                      const SizedBox(width: 8),

                      /// ✅ PLANNED DATE
                      statusPill(
                        plannedDateFormatted.isEmpty
                            ? 'No Plan'
                            : 'Planned $plannedDateFormatted',
                        color: Colors.indigo,
                      ),
                      const Spacer(),

                    ],
                  ),



                  const SizedBox(height: 12),

                  modernCard('Manifest Details', [
                    infoTile(
                      'Service Request',
                      getName(ws["service_request_id"]),
                      Icons.receipt_long,
                      color: Colors.blue,
                    ),
                    infoTile(
                      'Customer',
                      getName(ws["partner_id"]),
                      Icons.business,
                      color: Colors.deepPurple,
                    ),
                    infoTile(
                      'Service',
                      getName(ws["service_requested_id"]),
                      Icons.build,
                      color: Colors.green,
                    ),

                    infoTile(
                      'Container Type',
                      getName(ws["container_type_id"]),
                      Icons.inventory_2,
                      color: Colors.teal,
                    ),
                    infoTile(
                      'Bin Type',
                      getName(ws["bin_type_id"]),
                      Icons.delete,
                      color: Colors.redAccent,
                    ),

                    /// ✅ CONDITIONAL HIDE
                    if (!isPlacement)
                      infoTile(
                        'Waste Type',
                        getName(ws["waste_type_id"]),
                        Icons.category,
                        color: Colors.brown,
                      ),

                    if (!isPlacement)
                      infoTile(
                        'Waste Details',
                        getName(ws["waste_details_id"]),
                        Icons.description,
                        color: Colors.orange,
                      ),

                    infoTile(
                      'Summary',
                      summary,
                      Icons.description,
                      color: Colors.orange,
                    ),
                  ]),

                  if (isBin)
                    modernCard('Bin Details', [
                      /// 📍 Pickup Points
                      chipsBlock(
                        'Pickup Points',
                        pickupPoints, // ✅ already converted to List<String>
                        icon: Icons.location_on,
                        color: Colors.green,
                      ),

                      /// 🔵 Lifted Bins
                      if (!isPlacement)
                        chipsBlock(
                          'Bins Lifted',
                          binsLifted,
                          icon: Icons.upload,
                          color: Colors.blue,
                        ),

                      /// 🟠 Dropped Bins
                      chipsBlock(
                        'Bins Dropped',
                        binsDropped,
                        icon: Icons.download,
                        color: Colors.orange,
                      ),

                      const SizedBox(height: 6),

                      ElevatedButton.icon(
                        icon: const Icon(Icons.inventory),
                        label: const Text("Assign Bins"),
                        onPressed: () => openBinDialog(),
                      ),
                    ]),

                  if (isTank)
                    modernCard('Tank Details', [
                      infoTile(
                        'Truck',
                        getName(ws["truck_tanker_id"]),
                        Icons.local_shipping,
                        color: Colors.blueGrey,
                      ),
                      infoTile(
                        'Liters',
                        "${ws["liters_collected"] ?? 0} L",
                        Icons.water_drop,
                        color: Colors.green,
                      ),
                      infoTile(
                        'Billing',
                        "R ${ws["billing_amount"] ?? 0}",
                        Icons.payments,
                        color: Colors.orange,
                      ),
                    ]),

                  modernCard('Worksheet Input', [
                    inputField(
                      "Arrival Time",
                      arrivalController,
                      readOnly: true,
                      onTap: pickArrival,
                      icon: Icons.access_time,
                      color: Colors.green,
                    ),

                    inputField(
                      "Return Time",
                      returnController,
                      readOnly: true,
                      onTap: pickReturn,
                      icon: Icons.schedule,
                      color: Colors.orange,
                    ),

                    inputField(
                      "Kilometers",
                      kmController,
                      icon: Icons.speed,
                      color: Colors.deepPurple,
                    ),

                    inputField(
                      "Planned Quantity",
                      qtyController,
                      icon: Icons.format_list_numbered,
                      color: Colors.blue,
                    ),

                    inputField(
                      "Notes",
                      notesController,
                      icon: Icons.note_alt,
                      color: Colors.teal,
                    ),

                    dropdownField(
                      value: selectedUnit,
                      items: units,
                      onChanged: (v) => setState(() => selectedUnit = v),
                    ),

                    /// 🔥 ADD BUTTON HERE
                    SizedBox(height: 12),

                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton.icon(
                        icon: Icon(Icons.save),
                        label: Text("Save Inputs"),
                        style: ElevatedButton.styleFrom(
                          padding: EdgeInsets.symmetric(vertical: 14),
                          backgroundColor: Colors.green,
                        ),
                        onPressed: () async {
                          /// 👉 only saves worksheet (no email)
                          bool saved = await saveWorksheet();

                          if (!mounted) return;

                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(saved ? "✅ Inputs Saved" : "❌ Failed to save"),
                            ),
                          );
                        },
                      ),
                    ),
                  ]),

                  SizedBox(height: 20),

                  /// ✍️ SIGNATURE CARD (SEPARATE)
                  modernCard('Signatures', [
                    GestureDetector(
                      onTap: () => openSignaturePopup(isDriver: true),
                      child: buildSignatureCard(
                        "Driver Signature",
                        // worksheet["driver_signature"],
                        safeString(worksheet["driver_signature"]),

                      ),
                    ),

                    GestureDetector(
                      onTap: () => openSignaturePopup(isDriver: false),
                      child: buildSignatureCard(
                        "Service Provider Signature",
                        // worksheet["service_provider_signature"],
                        safeString(worksheet["service_provider_signature"]),
                      ),
                    ),
                  ]),



                  modernCard('Documents', [

                    /// 📄 MANIFEST
                    if (requiredDocs["manifest"] == true) ...[
                      buildDocumentCard(
                        "Manifest Document",
                        // worksheet["manifest_document"],
                        safeString(worksheet["manifest_document"]),
                      ),

                      ElevatedButton.icon(
                        icon: Icon(Icons.upload_file),
                        label: Text("Upload Manifest"),
                        onPressed: () async {
                          final file = await pickPdf();
                          if (file == null) return;

                          final success = await service.uploadDocument(
                            worksheetId: worksheet["id"],
                            manifest: file["base64"],
                            filename: file["name"],
                          );

                          if (success) {
                            setState(() {
                              worksheet["manifest_document"] = file["base64"];
                            });

                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text("Manifest uploaded ✅")),
                            );
                          }
                        },
                      ),

                      SizedBox(height: 10),
                    ],

                    /// ⚖️ WEIGHBRIDGE
                    if (requiredDocs["weighbridge"] == true) ...[
                      buildDocumentCard(
                        "Weighbridge Slip",
                        // worksheet["weighbridge_slip"],
                        safeString(worksheet["weighbridge_slip"]),
                      ),

                      ElevatedButton.icon(
                        icon: Icon(Icons.upload_file),
                        label: Text("Upload Weighbridge"),
                        onPressed: () async {
                          final file = await pickPdf();
                          if (file == null) return;

                          final success = await service.uploadDocument(
                            worksheetId: worksheet["id"],
                            weighbridge: file["base64"],
                            filename: file["name"],
                          );

                          if (success) {
                            setState(() {
                              worksheet["weighbridge_slip"] = file["base64"];
                            });

                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text("Weighbridge uploaded ✅")),
                            );
                          }
                        },
                      ),

                      SizedBox(height: 10),
                    ],

                    /// 🛡️ SAFETY
                    if (requiredDocs["safety"] == true) ...[
                      buildDocumentCard(
                        "Safety Certificate",
                        // worksheet["safety_certificate"],
                        safeString(worksheet["safety_certificate"]),
                      ),

                      ElevatedButton.icon(
                        icon: Icon(Icons.upload_file),
                        label: Text("Upload Safety Certificate"),
                        onPressed: () async {
                          final file = await pickPdf();
                          if (file == null) return;

                          final success = await service.uploadDocument(
                            worksheetId: worksheet["id"],
                            safety: file["base64"],
                            filename: file["name"],
                          );

                          if (success) {
                            setState(() {
                              worksheet["safety_certificate"] = file["base64"];
                            });

                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text("Safety uploaded ✅")),
                            );
                          }
                        },
                      ),
                    ],

                  ]),

                  modernCard('Photo Gallery', [
                    Row(
                      children: [

                        /// 📸 CAMERA
                        Expanded(
                          child: ElevatedButton.icon(
                            icon: Icon(Icons.camera_alt),
                            label: Text("Camera"),
                            onPressed: takePicture,
                          ),
                        ),

                        SizedBox(width: 10),

                        /// 🖼️ GALLERY
                        Expanded(
                          child: ElevatedButton.icon(
                            icon: Icon(Icons.photo_library),
                            label: Text("Gallery"),
                            onPressed: pickFromGallery,
                          ),
                        ),

                      ],
                    ),

                    SizedBox(height: 10),

                    /// 🖼️ GRID GALLERY
                    GridView.builder(
                      shrinkWrap: true,
                      physics: NeverScrollableScrollPhysics(),
                      itemCount: images.length,
                      gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 3,
                        crossAxisSpacing: 6,
                        mainAxisSpacing: 6,
                      ),
                      itemBuilder: (_, i) {
                        final img = images[i];

                        Uint8List? bytes;

                        /// ✅ FILE PATH (PRIMARY)
                        if (img["file_path"] != null) {
                          final file = File(img["file_path"]);

                          if (file.existsSync()) {
                            bytes = file.readAsBytesSync();
                          }
                        }

                        /// ✅ BASE64 (FALLBACK)
                        else if (img["image_base64"] != null) {
                          try {
                            bytes = base64Decode(img["image_base64"]);
                          } catch (e) {
                            print("❌ Base64 error: $e");
                          }
                        }

                        /// ❌ SAFE FALLBACK
                        if (bytes == null) {
                          return Container(
                            decoration: BoxDecoration(
                              color: Colors.grey[300],
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Icon(Icons.broken_image),
                          );
                        }

                        return Stack(
                          children: [
                            /// 📸 IMAGE
                            GestureDetector(
                              onTap: () {
                                Navigator.push(
                                  context,
                                  MaterialPageRoute(
                                    builder: (_) => ImagePreviewPage(imageBytes: bytes!),
                                  ),
                                );
                              },
                              child: ClipRRect(
                                borderRadius: BorderRadius.circular(8),
                                child: Image.memory(
                                  bytes!,
                                  fit: BoxFit.cover,
                                  width: double.infinity,
                                  height: double.infinity,
                                ),
                              ),
                            ),

                            /// 🔥 DELETE BUTTON (TOP RIGHT)
                            Positioned(
                              top: 4,
                              right: 4,
                              child: GestureDetector(
                                onTap: () async {
                                  final confirm = await showDialog<bool>(
                                    context: context,
                                    builder: (_) => AlertDialog(
                                      title: Text("Delete Image"),
                                      content: Text("Are you sure you want to delete this image?"),
                                      actions: [
                                        TextButton(
                                          onPressed: () => Navigator.pop(context, false),
                                          child: Text("Cancel"),
                                        ),
                                        TextButton(
                                          onPressed: () => Navigator.pop(context, true),
                                          child: Text("Delete", style: TextStyle(color: Colors.red)),
                                        ),
                                      ],
                                    ),
                                  );

                                  if (confirm == true) {
                                    await deleteImage(img); // 🔥 YOUR FUNCTION
                                  }
                                },
                                child: Container(
                                  padding: EdgeInsets.all(4),
                                  decoration: BoxDecoration(
                                    color: Colors.black54,
                                    shape: BoxShape.circle,
                                  ),
                                  child: Icon(
                                    Icons.delete,
                                    color: Colors.white,
                                    size: 18,
                                  ),
                                ),
                              ),
                            ),

                            /// 🔁 OPTIONAL: SYNC STATUS INDICATOR
                            if (img["synced"] == 0)
                              Positioned(
                                bottom: 4,
                                left: 4,
                                child: Container(
                                  padding: EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: Colors.orange,
                                    borderRadius: BorderRadius.circular(6),
                                  ),
                                  child: Text(
                                    "Pending",
                                    style: TextStyle(color: Colors.white, fontSize: 10),
                                  ),
                                ),
                              ),
                          ],
                        );
                      },
                    )

                  ]),


                  modernCard('Mailto', [

                    DropdownButtonFormField<int>(
                      value: managers.any((m) => m["id"] == selectedManagerId)
                          ? selectedManagerId
                          : null, // 🔥 prevents crash when offline list changes

                      decoration: InputDecoration(
                        labelText: "Manager",
                        border: OutlineInputBorder(),
                      ),

                      hint: const Text("Select Manager"),

                      items: managers.map<DropdownMenuItem<int>>((m) {
                        return DropdownMenuItem<int>(
                          value: m["id"],
                          child: Text(m["name"] ?? "No Name"),
                        );
                      }).toList(),

                      onChanged: (value) async {
                        setState(() {
                          selectedManagerId = value;
                        });

                        /// 🔥 SAVE SELECTION LOCALLY (CRITICAL FOR OFFLINE)
                        if (value != null) {
                          await LocalDB().saveLastManager(value);
                        }
                      },

                      validator: (value) {
                        if (value == null) {
                          return "Manager is required";
                        }
                        return null;
                      },
                    ),

                  ]),



                ],
              ),
            ),
          ),

          /// 🔥 FIXED SAVE BUTTON
          // Container(
          //   padding: const EdgeInsets.all(12),
          //   width: double.infinity,
          //   child: ElevatedButton.icon(
          //     style: ElevatedButton.styleFrom(
          //       padding: const EdgeInsets.symmetric(vertical: 14),
          //     ),
          //     icon: const Icon(Icons.save),
          //     label: const Text(
          //       "Save Worksheet",
          //       style: TextStyle(fontSize: 16),
          //     ),
          //
          //
          //     onPressed: () async {
          //
          //       /// 🔥 VALIDATE MANAGER
          //       if (selectedManagerId == null) {
          //         ScaffoldMessenger.of(context).showSnackBar(
          //           const SnackBar(content: Text("⚠️ Please select a manager")),
          //         );
          //         return;
          //       }
          //
          //       /// 1. SAVE DATA
          //       await saveWorksheet();
          //
          //       /// 2. CALL WIZARD (THIS SENDS EMAIL)
          //       bool success = await service.finishWorksheet(
          //         worksheetId: widget.worksheet["id"],
          //         managerId: selectedManagerId!,
          //       );
          //
          //       if (!mounted) return;
          //
          //       if (success) {
          //
          //         setState(() {
          //           worksheet["state"] = "done";
          //         });
          //
          //         await LocalDB().updateWorksheetState(worksheet["id"], "done");
          //
          //         ScaffoldMessenger.of(context).showSnackBar(
          //           const SnackBar(content: Text("✅ Completed & Email Sent")),
          //         );
          //
          //       } else {
          //         ScaffoldMessenger.of(context).showSnackBar(
          //           const SnackBar(content: Text("❌ Failed to complete")),
          //         );
          //       }
          //     },
          //
          //   ),
          // ),

        ],
      ),

      /// 🔥 ✅ ADD THIS HERE (NOT inside Column)
      bottomNavigationBar: Container(
        padding: EdgeInsets.fromLTRB(
          12,
          12,
          12,
          MediaQuery.of(context).padding.bottom + 12,
        ),
        decoration: BoxDecoration(
          color: Colors.white,
          boxShadow: [
            BoxShadow(
              blurRadius: 8,
              color: Colors.black12,
            ),
          ],
        ),
        child: ElevatedButton.icon(
          style: ElevatedButton.styleFrom(
            padding: const EdgeInsets.symmetric(vertical: 16),
          ),
          icon: const Icon(Icons.save),
          label: const Text(
            "Save Worksheet",
            style: TextStyle(fontSize: 16),
          ),
          onPressed: () async {
            if (selectedManagerId == null) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text("⚠️ Please select a manager")),
              );
              return;
            }

            await saveWorksheet();

            bool success = await service.finishWorksheet(
              worksheetId: widget.worksheet["id"],
              managerId: selectedManagerId!,
            );

            if (!mounted) return;

            if (success) {
              setState(() {
                worksheet["state"] = "done";
              });

              await LocalDB().updateWorksheetState(
                worksheet["id"],
                "done",
              );

              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text("✅ Completed & Email Sent")),
              );
            } else {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text("❌ Failed to complete")),
              );
            }
          },
        ),
      ),


    );

  }


}



// ========================= UI HELPERS =========================

Widget modernCard(String title, List<Widget> children) {
  return SizedBox(
    width: double.infinity, // ✅ FORCE FULL WIDTH
    child: Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      elevation: 3,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              title,
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
            const SizedBox(height: 10),
            ...children,
          ],
        ),
      ),
    ),
  );
}

Widget infoTile(
  String label,
  String value,
  IconData icon, {
  Color color = Colors.green,
}) {
  return ListTile(
    contentPadding: EdgeInsets.zero,
    leading: CircleAvatar(
      backgroundColor: color.withOpacity(0.15),
      child: Icon(icon, color: color),
    ),
    title: Text(label),
    subtitle: Text(value, style: const TextStyle(fontWeight: FontWeight.w500)),
  );
}

Widget chipsBlock(
  String title,
  List<String> items, {
  required IconData icon,
  required Color color,
}) {
  return Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Row(
        children: [
          Icon(icon, color: color, size: 18),
          const SizedBox(width: 6),
          Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
        ],
      ),
      const SizedBox(height: 6),
      Wrap(
        spacing: 6,
        children: items
            .map(
              (e) =>
                  Chip(label: Text(e), backgroundColor: color.withOpacity(0.1)),
            )
            .toList(),
      ),
      const SizedBox(height: 10),
    ],
  );
}

Widget inputField(
  String label,
  TextEditingController controller, {
  bool readOnly = false,
  VoidCallback? onTap,
  IconData? icon, // ✅ ADD THIS
  Color color = Colors.green, // ✅ ADD THIS
}) {
  return Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: TextField(
      controller: controller,
      readOnly: readOnly,
      onTap: onTap,
      decoration: InputDecoration(
        labelText: label,

        // ✅ ICON SUPPORT
        prefixIcon: icon != null ? Icon(icon, color: color) : null,

        filled: true,
        fillColor: color.withOpacity(0.05),

        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),

        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: color.withOpacity(0.3)),
        ),

        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: color, width: 2),
        ),
      ),
    ),
  );
}

Widget dropdownField({
  required int? value,
  required List items,
  required Function(int?) onChanged,
}) {
  return Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: InputDecorator(
      decoration: InputDecoration(
        labelText: "Unit of Measure",
        prefixIcon: const Icon(Icons.straighten, color: Colors.blue),

        filled: true,
        fillColor: Colors.blue.withOpacity(0.05),

        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),

        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide(color: Colors.blue.withOpacity(0.3)),
        ),

        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: Colors.blue, width: 2),
        ),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<int>(
          value: value,
          isExpanded: true,
          hint: const Text("Select Unit"),
          items: items.map<DropdownMenuItem<int>>((u) {
            return DropdownMenuItem(value: u["id"], child: Text(u["name"]));
          }).toList(),
          onChanged: onChanged,
        ),
      ),
    ),
  );
}

Widget statusPill(String text, {Color color = Colors.grey}) {
  return Container(
    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
    decoration: BoxDecoration(
      color: color.withOpacity(0.1),
      borderRadius: BorderRadius.circular(20),
    ),
    child: Text(
      text,
      style: TextStyle(color: color, fontWeight: FontWeight.w600),
    ),
  );
}
