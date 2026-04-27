import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:driver_app/services/local_db.dart';

import 'local_db.dart';
import 'network_service.dart';



String? safeString(dynamic v) {
  if (v == null || v == false) return null;
  return v.toString();
}

class OdooService {


  static final OdooService _instance = OdooService._internal();

  factory OdooService() {
    return _instance;
  }

  OdooService._internal();

  final String baseUrl = "http://10.142.26.136:8019";
  // final String baseUrl = "http://192.168.0.24:8019";
  // final String baseUrl = "http://10.0.2.2:8019";
  // final String baseUrl = "http://dwmis.co.za";
  // final String db = "ziwaste-db";
  // final String db = "waste_db_live";
  final String db = "ziwaste_qa";
  String? sessionId;

  int? uid;
  int? partnerId;



  /// LOAD SESSION FROM DEVICE
  Future<void> loadSession() async {

    final prefs = await SharedPreferences.getInstance();

    sessionId = prefs.getString("session_id");
    uid = prefs.getInt("uid");
    partnerId = prefs.getInt("partner_id");

    print("SESSION LOADED: $sessionId");
    print("UID LOADED: $uid");
    print("PARTNER ID LOADED: $partnerId");
  }

  /// SAVE SESSION
  Future<void> saveSession(String cookie) async {

    final prefs = await SharedPreferences.getInstance();

    await prefs.setString("session_id", cookie);
    await prefs.setInt("uid", uid ?? 0);
    await prefs.setInt("partner_id", partnerId ?? 0);

    sessionId = cookie;
  }

  /// CLEAR SESSION
  Future<void> clearSession() async {

    final prefs = await SharedPreferences.getInstance();
    await prefs.remove("session_id");

    sessionId = null;

  }


  Future<bool> login(String email, String password) async {
    try {
      print("🔗 LOGIN URL: $baseUrl");

      final response = await http.post(
        Uri.parse("$baseUrl/web/session/authenticate"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "db": db,
            "login": email,
            "password": password
          }
        }),
      );

      print("📡 RESPONSE STATUS: ${response.statusCode}");
      print("📡 RESPONSE BODY: ${response.body}");

      final data = jsonDecode(response.body);

      if (data["result"] == null) {
        print("❌ LOGIN FAILED: No result");
        return false;
      }

      final result = data["result"];

      sessionId = response.headers['set-cookie']?.split(';').first;
      uid = result["uid"];
      partnerId = result["partner_id"];

      print("✅ LOGIN UID: $uid");
      print("✅ LOGIN PARTNER: $partnerId");

      final prefs = await SharedPreferences.getInstance();

      await prefs.setString("session_id", sessionId!);
      await prefs.setInt("uid", uid!);
      await prefs.setInt("partner_id", partnerId!);

      return true;

    } catch (e) {
      print("❌ LOGIN ERROR: $e");
      return false;
    }
  }

  // Future<List<dynamic>> getWorksheets() async {
  Future<List<dynamic>> getWorksheets({bool forceOnline = false}) async {

    await loadSession(); // ✅ ENSURE SESSION EXISTS

    try {

      final client = http.Client();

      // final response = await http.post(
      final response = await client.post(

        Uri.parse("$baseUrl/web/dataset/call_kw"),
        headers: {
          "Content-Type": "application/json",
          "Cookie": sessionId!
        },
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "model": "waste.worksheet",
            "method": "search_read",
            "args": [
              [
                ["driver_id", "=", partnerId]
              ]
            ],
            "kwargs": {
              "fields": [
                "id",
                "name",
                "arrival_time",
                "return_date",
                "kilometers",
                "state",
                "driver_id",
                "unit_of_measure",

                "service_request_id",
                "partner_id",
                "pickup_point_id",
                "service_requested_id",

                "truck_tanker_id",
                "waste_type_id",
                "waste_details_id",
                "bin_type_id",
                "tank_volume_id",
                "container_type_id",

                "liters_collected",
                "sale_order_id",

                "notes_html",
                "pickup_point_bins_summary",

                "product_uom_qty",

                "planned_date",

                "pickup_point_ids",
                "dropoff_point_ids",
                "bin_lifted_ids",
                "bin_dropped_ids",

                "billing_amount",

                "driver_signature",
                "service_provider_signature",

                "manifest_document",
                "weighbridge_slip",
                "safety_certificate"

              ]
            }
          }
        }),
      ).timeout(const Duration(seconds: 120)); // 🔥 ONLY ADD THIS
      // ).timeout(const Duration(seconds: 120));
      client.close();

      print("GET WORKSHEETS RESPONSE: ${response.body}");

      final data = jsonDecode(response.body);

      final worksheets = List<Map<String, dynamic>>.from(data["result"] ?? []);

      for (var ws in worksheets) {
        print("📄 ID: ${ws["id"]}");

        final manifest = ws["manifest_document"];
        final weighbridge = ws["weighbridge_slip"];
        final safety = ws["safety_certificate"];

        print("📄 MANIFEST LENGTH: ${manifest is String ? manifest.length : 0}");
        print("📄 WEIGHBRIDGE LENGTH: ${weighbridge is String ? weighbridge.length : 0}");
        print("📄 SAFETY LENGTH: ${safety is String ? safety.length : 0}");
      }


      // ✅ FIX Many2many fields → convert IDs to [id, name]
      for (var ws in worksheets) {

        // Pickup Points
        if (ws["pickup_point_ids"] is List) {
          final ids = List<int>.from(ws["pickup_point_ids"]);

          if (ids.isNotEmpty) {
            final names = await _getNames("pickup.point", ids);
            ws["pickup_point_ids"] = names;
          }
        }

        // Bins Lifted
        if (ws["bin_lifted_ids"] is List) {
          final ids = List<int>.from(ws["bin_lifted_ids"]);

          if (ids.isNotEmpty) {
            final names = await _getNames("waste.container", ids);
            ws["bin_lifted_ids"] = names;
          }
        }

        // Bins Dropped
        if (ws["bin_dropped_ids"] is List) {
          final ids = List<int>.from(ws["bin_dropped_ids"]);

          if (ids.isNotEmpty) {
            final names = await _getNames("waste.container", ids);
            ws["bin_dropped_ids"] = names;
          }
        }
      }

      /// SAVE ONLINE DATA LOCALLY
      // await LocalDB().saveWorksheets(worksheets);

      for (var ws in worksheets) {
        final localDocs = await LocalDB().getDocumentLocal(ws["id"]);


        if (localDocs != null) {
          if (ws["manifest_document"] == false || ws["manifest_document"] == null) {
            ws["manifest_document"] = localDocs["manifest_document"];
          }

          if (ws["weighbridge_slip"] == false || ws["weighbridge_slip"] == null) {
            ws["weighbridge_slip"] = localDocs["weighbridge_slip"];
          }

          if (ws["safety_certificate"] == false || ws["safety_certificate"] == null) {
            ws["safety_certificate"] = localDocs["safety_certificate"];
          }
        }

      }

      for (var ws in worksheets) {
        ws["manifest_document"] = safeString(ws["manifest_document"]);
        ws["weighbridge_slip"] = safeString(ws["weighbridge_slip"]);
        ws["safety_certificate"] = safeString(ws["safety_certificate"]);
        ws["driver_signature"] = safeString(ws["driver_signature"]);
        ws["service_provider_signature"] = safeString(ws["service_provider_signature"]);
      }

      await LocalDB().saveWorksheets(worksheets);

      /// LOAD PENDING OFFLINE UPDATES
      final pending = await LocalDB().getPending();

      /// MERGE OFFLINE DATA

      for (var p in pending) {

        Map<String, dynamic>? ws;

        try {
          ws = worksheets.firstWhere(
                (w) => w["id"] == p["worksheet_id"],
          );
        } catch (e) {
          ws = null;
        }

        if (ws != null) {

          ws["arrival_time"] = p["arrival_time"];
          ws["return_date"] = p["return_date"];
          ws["kilometers"] = p["kilometers"];
          ws["unit_of_measure"] = p["unit_of_measure"];
          ws["notes_html"] = p["notes_html"];
          ws["product_uom_qty"] = p["product_uom_qty"];


          ws["offline"] = true;

        }

      }

      return worksheets;

    }


    catch (e) {
      print("❌ FETCH FAILED: $e");

      if (forceOnline) {
        // throw Exception("FORCED ONLINE FAILED → $e");
        print("❌ FORCED ONLINE FAILED → using fallback");

      }

      print("⚠️ FALLING BACK TO SQLITE");

      final worksheets =
      (await LocalDB().getWorksheets())
          .map((e) => Map<String, dynamic>.from(e))
          .toList();

      // ✅ KEEP YOUR OFFLINE MERGE (SAFE)
      final pending = await LocalDB().getPending();

      for (var ws in worksheets) {
        Map? p;

        try {
          p = pending.firstWhere(
                (e) => e["worksheet_id"] == ws["id"],
          );
        } catch (e) {
          p = null;
        }

        if (p != null) {
          ws["arrival_time"] = p["arrival_time"];
          ws["return_date"] = p["return_date"];
          ws["kilometers"] = p["kilometers"];
          ws["unit_of_measure"] = p["unit_of_measure"];
          ws["notes_html"] = p["notes_html"];
          ws["product_uom_qty"] = p["product_uom_qty"];

          ws["offline"] = true;
        }
      }

      return worksheets;
    }

  }


  // Future<bool> updateWorksheet(
  //     int id,
  //     String arrival,
  //     String returnDate,
  //     int kilometers,
  //     int? unitId,
  //     String notes,
  //     double qty,
  //
  //     ) async {
  //
  //   Map<String, dynamic> values = {
  //     "kilometers": kilometers,
  //     "notes_html": notes,
  //     "product_uom_qty": qty,
  //   };
  //
  //   if (arrival.isNotEmpty) {
  //     values["arrival_time"] = arrival;
  //   }
  //
  //   if (returnDate.isNotEmpty) {
  //     values["return_date"] = returnDate;
  //   }
  //
  //   if (unitId != null) {
  //     values["unit_of_measure"] = unitId;
  //   }
  //
  //   try {
  //
  //     final response = await http.post(
  //       Uri.parse("$baseUrl/web/dataset/call_kw"),
  //       headers: {
  //         "Content-Type": "application/json",
  //         "Cookie": sessionId!
  //       },
  //       body: jsonEncode({
  //         "jsonrpc": "2.0",
  //         "method": "call",
  //         "params": {
  //           "model": "waste.worksheet",
  //           "method": "write",
  //           "args": [
  //             [id],
  //             values
  //           ],
  //           "kwargs": {}
  //         }
  //       }),
  //     );
  //
  //     final data = jsonDecode(response.body);
  //
  //     if (data["result"] == true) {
  //       return true;
  //     }
  //
  //   } catch (e) {
  //
  //     print("OFFLINE MODE → SAVING TO SQLITE");
  //
  //     await LocalDB().insertPending({
  //       "worksheet_id": id,
  //       "arrival_time": arrival,
  //       "return_date": returnDate,
  //       "kilometers": kilometers,
  //       "unit_of_measure": unitId,
  //       "notes_html": notes,              // ✅ ADD
  //       "product_uom_qty": qty,
  //     });
  //
  //     return true;
  //   }
  //     print("UPDATE BODY: $values");
  //
  //   return false;
  // }

  Future<bool> updateWorksheet(
      int id,
      String arrival,
      String returnDate,
      int kilometers,
      int? unitId,
      String notes,
      double qty,
      ) async {

    Map<String, dynamic> values = {
      "kilometers": kilometers,
      "notes_html": notes,
      "product_uom_qty": qty,
    };

    if (arrival.isNotEmpty) {
      values["arrival_time"] = arrival;
    }

    if (returnDate.isNotEmpty) {
      values["return_date"] = returnDate;
    }

    if (unitId != null) {
      /// 🔥 TRY BOTH (safe fix)
      values["unit_of_measure"] = unitId;
      // values["product_uom_id"] = unitId; // 👈 use this if needed
    }

    try {
      print("📤 SENDING UPDATE: $values");

      final response = await http.post(
        Uri.parse("$baseUrl/web/dataset/call_kw"),
        headers: {
          "Content-Type": "application/json",
          "Cookie": sessionId!
        },
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "model": "waste.worksheet",
            "method": "write",
            "args": [
              [id],
              values
            ],
            "kwargs": {}
          }
        }),
      );

      print("📡 STATUS: ${response.statusCode}");
      print("📡 BODY: ${response.body}");

      final data = jsonDecode(response.body);

      /// 🔥 HANDLE ODOO ERROR (THIS WAS MISSING)
      if (data["error"] != null) {
        print("❌ ODOO ERROR: ${data["error"]}");
        return false;
      }

      print("✅ RESULT: ${data["result"]}");

      return data["result"] == true;

    } catch (e) {

      print("⚠️ OFFLINE → SAVING LOCALLY: $e");

      await LocalDB().insertPending({
        "worksheet_id": id,
        "arrival_time": arrival,
        "return_date": returnDate,
        "kilometers": kilometers,
        "unit_of_measure": unitId,
        "notes_html": notes,
        "product_uom_qty": qty,
      });

      return true;
    }
  }

  Future<List<dynamic>> getUnits() async {

    try {

      final response = await http.post(
        Uri.parse("$baseUrl/web/dataset/call_kw"),
        headers: {
          "Content-Type": "application/json",
          "Cookie": sessionId!
        },
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "model": "uom.uom",
            "method": "search_read",
            "args": [[]],
            "kwargs": {
              "fields": ["id", "name"]
            }
          }
        }),
      );

      final data = jsonDecode(response.body);

      final units = data["result"] ?? [];

      /// Save locally
      await LocalDB().saveUnits(units);

      return units;

    } catch (e) {

      print("Offline mode: loading units from local DB");

      return await LocalDB().getUnits();

    }

  }

  Future<List<List<dynamic>>> _getNames(String model, List<int> ids) async {

    // ✅ ensure session
    if (sessionId == null) {
      await loadSession();
    }

    if (sessionId == null) {
      print("ERROR: sessionId is null");
      return [];
    }

    try {
      final response = await http.post(
        Uri.parse("$baseUrl/web/dataset/call_kw"),
        headers: {
          "Content-Type": "application/json",
          "Cookie": sessionId!,
        },
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "model": model,
            "method": "name_get",
            "args": [ids],
            "kwargs": {}
          }
        }),
      );

      final data = jsonDecode(response.body);

      return List<List<dynamic>>.from(data["result"] ?? []);

    } catch (e) {
      print("ERROR fetching names for $model: $e");
      return [];
    }
  }

  Future<List> getPickupPoints(int partnerId) async {
    try {
      bool online = await NetworkService.isOnline();

      if (online) {
        final response = await http.post(
          Uri.parse("$baseUrl/web/dataset/call_kw"),
          headers: {
            "Content-Type": "application/json",
            "Cookie": sessionId!
          },
          body: jsonEncode({
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
              "model": "pickup.point",
              "method": "search_read",
              "args": [
                [
                  ["partner_id", "=", partnerId]
                ]
              ],
              "kwargs": {
                "fields": ["id", "name", "partner_id"]
              }
            }
          }),
        );

        final data = jsonDecode(response.body)["result"] ?? [];

        print("ONLINE PICKUP POINTS: $data");

        await LocalDB().savePickupPoints(data);

        return data;
      }
    } catch (e) {
      print("ERROR pickup points → fallback to SQLite: $e");
    }

    print("OFFLINE → loading pickup points from SQLite");

    return await LocalDB().getPickupPoints(partnerId);
  }
  Future<List> getAvailableBins(int? pickupPointId, int? binTypeId) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/web/dataset/call_kw"),
        headers: {
          "Content-Type": "application/json",
          "Cookie": sessionId!
        },
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "model": "waste.container",
            "method": "search_read",
            "args": [[]], // 🔥 GET ALL BINS FIRST
            "kwargs": {
              "fields": ["id", "name", "status", "inUse"]
            }
          }
        }),
      );

      print("BINS RESPONSE: ${response.body}");

      return jsonDecode(response.body)["result"] ?? [];
    } catch (e) {
      print("ERROR bins: $e");
      return [];
    }
  }

  Future<int?> createBinWizard(int requestId) async {
    final response = await http.post(
      Uri.parse("$baseUrl/web/dataset/call_kw"),
      headers: {
        "Content-Type": "application/json",
        "Cookie": sessionId!
      },
      body: jsonEncode({
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
          "model": "waste.request.assign.bin.wizard",
          "method": "create",
          "args": [
            {
              "request_id": requestId,
              "partner_id": partnerId, // ✅ ADD THIS
            }
          ],
          "kwargs": {}
        }
      }),
    );

    final data = jsonDecode(response.body);
    return data["result"];
  }

  Future<bool> addWizardLines(int wizardId, List lines) async {
    final response = await http.post(
      Uri.parse("$baseUrl/web/dataset/call_kw"),
      headers: {
        "Content-Type": "application/json",
        "Cookie": sessionId!
      },
      body: jsonEncode({
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
          "model": "waste.request.assign.bin.wizard",
          "method": "write",
          "args": [
            [wizardId],
            {
              "line_ids": lines
            }
          ],
          "kwargs": {}
        }
      }),
    );

    final data = jsonDecode(response.body);
    return data["result"] == true;
  }

  Future<bool> assignBins(int worksheetId, List lines) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/web/dataset/call_kw"),
        headers: {
          "Content-Type": "application/json",
          "Cookie": sessionId!
        },
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "model": "waste.worksheet",
            "method": "mobile_assign_bins",
            "args": [worksheetId, lines],
            "kwargs": {}
          }
        }),
      );

      final data = jsonDecode(response.body);

      return data["result"] == true;

    } catch (e) {
      print("ERROR assign bins: $e");
      return false;
    }
  }

  Future<bool> confirmWizard(int wizardId) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/web/dataset/call_kw"),
        headers: {
          "Content-Type": "application/json",
          "Cookie": sessionId!
        },
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "model": "waste.request.assign.bin.wizard",
            "method": "action_confirm",
            "args": [[wizardId]],
            "kwargs": {}
          }
        }),
      );

      print("CONFIRM RESPONSE: ${response.body}");

      final data = jsonDecode(response.body);

      /// 🔥 HANDLE ODOO ERROR
      if (data["error"] != null) {
        print("ODOO ERROR: ${data["error"]["data"]["message"]}");
        return false;
      }

      return true;

    } catch (e) {
      print("NETWORK ERROR confirmWizard: $e");
      return false;
    }
  }

  Future<List> getLiftedBins(
      int partnerId,
      int pickupPointId,
      int binTypeId,
      ) async {
    bool online = await NetworkService.isOnline();

    if (online) {
      try {
        final response = await http.post(
          Uri.parse("$baseUrl/web/dataset/call_kw"),
          headers: {
            "Content-Type": "application/json",
            "Cookie": sessionId!
          },
          body: jsonEncode({
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
              "model": "waste.container",
              "method": "search_read",
              "args": [
                [
                  ["partner_id", "=", partnerId],
                  ["pickup_point_id", "=", pickupPointId],
                  ["status", "=", "in_use"],
                  ["inUse", "=", true],
                  ["reserved_request_id", "=", false],
                  ["bin_type_id", "=", binTypeId]
                ]
              ],
              "kwargs": {

                "fields": [
                  "id",
                  "name",
                  "pickup_point_id",
                  "partner_id",
                  "bin_type_id",
                  "status",
                  "container_type_id",
                  "tank_volume_id"
                ]
              }
            }
          }),
        );

        final data = jsonDecode(response.body)["result"] ?? [];

        print("LIFTED BINS: $data");

        /// ✅ SAVE TO SQLITE
        await LocalDB().saveBins(data);

        return data;

      } catch (e) {
        print("ERROR lifted bins: $e");
        return [];
      }

    } else {
      /// ✅ FIXED OFFLINE MODE
      print("OFFLINE → loading lifted bins from SQLite");

      return await LocalDB().getLiftedBinsLocal(
        partnerId,
        pickupPointId,
        binTypeId,
      );
    }
  }


  Future<List> getDroppedBins(int binTypeId) async {
    bool online = await NetworkService.isOnline();

    if (online) {
      try {
        final response = await http.post(
          Uri.parse("$baseUrl/web/dataset/call_kw"),
          headers: {
            "Content-Type": "application/json",
            "Cookie": sessionId!
          },
          body: jsonEncode({
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
              "model": "waste.container",
              "method": "search_read",
              "args": [
                [
                  ["partner_id", "=", false],
                  ["pickup_point_id", "=", false],
                  ["status", "=", "intact"],
                  ["inUse", "=", false],
                  ["reserved_request_id", "=", false],
                  ["bin_type_id", "=", binTypeId]
                ]
              ],
              "kwargs": {
                "fields": [
                  "id",
                  "name",
                  "pickup_point_id",
                  "partner_id",
                  "bin_type_id",
                  "status",
                  "container_type_id",
                  "tank_volume_id"
                ]
              }
            }
          }),
        );

        final data = jsonDecode(response.body)["result"] ?? [];

        print("DROPPED BINS: $data");

        /// ✅ SAVE TO SQLITE
        await LocalDB().saveBins(data);

        return data;

      } catch (e) {
        print("ERROR dropped bins: $e");
        return [];
      }

    } else {
      /// ✅ FIXED OFFLINE MODE
      print("OFFLINE → loading dropped bins from SQLite");

      return await LocalDB().getDroppedBinsLocal(binTypeId);
    }
  }


  Future<bool> updateSignature({
    required int worksheetId,
    String? driverSignature,
    String? providerSignature,
  }) async {

    bool online = await NetworkService.isOnline();

    /// 🔥 FILTER EMPTY VALUES
    Map<String, dynamic> values = {};

    bool isValid(String? val) {
      if (val == null) return false;

      final v = val.trim();

      return v.isNotEmpty &&
          v != "0" &&
          v.toLowerCase() != "false" &&
          v.length > 50; // base64 safety
    }

    if (isValid(driverSignature)) {
      values["driver_signature"] = driverSignature;
    }

    if (isValid(providerSignature)) {
      values["service_provider_signature"] = providerSignature;
    }

    /// 🚫 NOTHING TO SEND → STOP
    if (values.isEmpty) {
      print("⚠️ Skipping empty signature update");
      return false;
    }

    if (online) {
      try {
        final response = await http.post(
          Uri.parse("$baseUrl/web/dataset/call_kw"),
          headers: {
            "Content-Type": "application/json",
            "Cookie": sessionId!,
          },
          body: jsonEncode({
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
              "model": "waste.worksheet",
              "method": "write",
              "args": [
                [worksheetId],
                values
              ],
              "kwargs": {},
            }
          }),
        );

        final result = jsonDecode(response.body)["result"];

        return result == true;

      } catch (e) {
        print("ERROR updating signature: $e");
      }
    }

    /// OFFLINE SAVE
    await LocalDB().updateSignatureLocal(
      worksheetId,
      driverSignature: values["driver_signature"],
      providerSignature: values["service_provider_signature"],
    );

    return true;
  }



  String cleanBase64(String base64) {
    try {
      String cleaned = base64.trim();

      // remove data prefix if exists
      if (cleaned.contains(",")) {
        cleaned = cleaned.split(",").last;
      }

      // remove spaces / line breaks
      cleaned = cleaned.replaceAll("\n", "");
      cleaned = cleaned.replaceAll("\r", "");

      // 🔥 VERY IMPORTANT: validate base64
      base64Decode(cleaned);

      return cleaned;
    } catch (e) {
      print("❌ INVALID BASE64: $e");
      return "";
    }
  }




  Uint8List? safeDecode(dynamic data) {
    if (data == null || data == false || data == 0) return null;

    try {
      String cleaned = data.toString().trim();

      if (cleaned.contains(",")) {
        cleaned = cleaned.split(",").last;
      }

      return base64Decode(cleaned);
    } catch (e) {
      print("❌ BASE64 ERROR: $e");
      return null;
    }
  }




  Future<bool> uploadDocument({
    required int worksheetId,
    String? manifest,
    String? weighbridge,
    String? safety,
    String? filename,
  }) async {



    final existing = await LocalDB().getDocumentLocal(worksheetId);

    await LocalDB().saveDocumentLocal(
      worksheetId: worksheetId,
      // manifest: manifest ?? existing?["manifest_document"],
      // weighbridge: weighbridge ?? existing?["weighbridge_slip"],
      // safety: safety ?? existing?["safety_certificate"],

      manifest: (manifest != null && manifest.isNotEmpty)
          ? manifest
          : existing?["manifest_document"],
      weighbridge: (weighbridge != null && weighbridge.isNotEmpty)
          ? weighbridge
          : existing?["weighbridge_slip"],
      safety: (safety != null && safety.isNotEmpty)
          ? safety
          : existing?["safety_certificate"],
    );

    final url = "$baseUrl/web/dataset/call_kw";

    final Map<String, dynamic> body = {};

    bool isValid(String? value) {
      if (value == null) return false;

      final v = value.trim();

      return v.isNotEmpty &&
          v != "0" &&
          v.toLowerCase() != "false" &&
          v.length > 50;
    }

    if (isValid(manifest)) {
      final cleaned = cleanBase64(manifest!);
      if (cleaned.isNotEmpty) {
        body["manifest_document"] = cleaned;
        body["manifest_document_filename"] =
            filename ?? "manifest.pdf";
      }
    }

    if (isValid(weighbridge)) {
      final cleaned = cleanBase64(weighbridge!);
      if (cleaned.isNotEmpty) {
        body["weighbridge_slip"] = cleaned;
        body["weighbridge_slip_filename"] =
            filename ?? "weighbridge.pdf";
      }
    }

    if (isValid(safety)) {
      final cleaned = cleanBase64(safety!);
      if (cleaned.isNotEmpty) {
        body["safety_certificate"] = cleaned;
        body["safety_certificate_filename"] =
            filename ?? "safety.pdf";
      }
    }

    if (body.isEmpty) {
      print("⚠️ No valid document to upload");
      return false;
    }

    print("📡 CLEAN PAYLOAD: $body");

    try {
      final response = await http.post(
        Uri.parse(url),
        headers: {
          "Content-Type": "application/json",
          "Cookie": sessionId!,
        },
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "model": "waste.worksheet",
            "method": "write",
            "args": [
              [worksheetId],
              body
            ],
            "kwargs": {}, // 🔥🔥🔥 THIS FIXES YOUR ERROR
          }
        }),
      );

      print("📦 FINAL BODY:");
      body.forEach((k, v) {
        print("$k → length: ${v.toString().length}");
      });

      print("📥 STATUS: ${response.statusCode}");
      print("📥 BODY: ${response.body}");

      final decoded = jsonDecode(response.body);

      if (decoded["error"] != null) {
        print("❌ ODOO ERROR: ${decoded["error"]}");
        return false;
      }

      return decoded["result"] == true;

    } catch (e) {
      print("❌ UPLOAD ERROR: $e");
      return false;
    }
  }

  Future<Map<String, dynamic>?> getProfile() async {
    await loadSession();

    try {
      final response = await http.post(
        Uri.parse("$baseUrl/web/dataset/call_kw"),
        headers: {
          "Content-Type": "application/json",
          "Cookie": sessionId!,
        },
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "model": "res.partner",
            "method": "read",
            "args": [
              [partnerId],
              ["name", "street", "city", "email", "phone", "mobile"]
            ],
            "kwargs": {}
          }
        }),
      );

      final data = jsonDecode(response.body);
      final result = data["result"];

      if (result != null && result.isNotEmpty) {
        return result[0];
      }

    } catch (e) {
      print("❌ PROFILE ERROR: $e");
    }

    return null;
  }

  Future<Map<String, dynamic>?> getWorksheetDocuments(int id) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/web/dataset/call_kw"),
        headers: {
          "Content-Type": "application/json",
          "Cookie": sessionId!
        },
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "model": "waste.worksheet", // 🔥 REPLACE WITH REAL MODEL
            "method": "read",
            "args": [
              [id],
              [
                "manifest_document",
                "weighbridge_slip",
                "safety_certificate"
              ]
            ],
            "kwargs": {},
          }
        }),
      ).timeout(const Duration(seconds: 120));

      final data = jsonDecode(response.body);

      print("📥 RAW ODOO RESPONSE: $data");

      final result = data["result"];

      // 🔴 FIX 1: Check null
      if (result == null) {
        print("❌ RESULT IS NULL");
        return null;
      }

      // 🔴 FIX 2: Check empty list
      if (result is List && result.isEmpty) {
        print("❌ RESULT IS EMPTY");
        return null;
      }

      // 🔴 FIX 3: Safe access
      final record = result[0];

      print("📄 RECORD: $record");

// 🔥 ADD THESE LINES HERE
      print("📄 MANIFEST TYPE: ${record["manifest_document"].runtimeType}");
      print("📄 MANIFEST VALUE: ${record["manifest_document"]}");

      print("📄 WEIGHBRIDGE TYPE: ${record["weighbridge_slip"].runtimeType}");
      print("📄 WEIGHBRIDGE VALUE: ${record["weighbridge_slip"]}");

      print("📄 SAFETY TYPE: ${record["safety_certificate"].runtimeType}");
      print("📄 SAFETY VALUE: ${record["safety_certificate"]}");

      return {
        // "manifest_document": record["manifest_document"] ?? "",
        // "weighbridge_slip": record["weighbridge_slip"] ?? "",
        // "safety_certificate": record["safety_certificate"] ?? "",
        "manifest_document": safeString(record["manifest_document"]),
        "weighbridge_slip": safeString(record["weighbridge_slip"]),
        "safety_certificate": safeString(record["safety_certificate"]),
      };

    } catch (e) {
      print("❌ GET DOCUMENTS ERROR: $e");
      return null;
    }
  }

  Future<bool> updateWorksheetState({
    required int worksheetId,
    required String state,
  }) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/web/dataset/call_kw"),
        headers: {
          "Content-Type": "application/json",
          "Cookie": sessionId!,
        },
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "model": "waste.worksheet", // 🔥 REPLACE WITH YOUR MODEL
            "method": "write",
            "args": [
              [worksheetId],
              {"state": state}
            ],
            "kwargs": {},
          }
        }),
      );

      final data = jsonDecode(response.body);

      return data["result"] == true;
    }
    catch (e) {
      print("❌ STATE UPDATE ERROR: $e");
      return false;
    }
  }

  Future<bool> completeWorksheet(int worksheetId) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/web/dataset/call_kw"),
        headers: {
          "Content-Type": "application/json",
          "Cookie": sessionId!,
        },
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "model": "waste.worksheet",
            "method": "action_done", // ✅ THIS IS THE KEY
            "args": [
              [worksheetId]
            ],
            "kwargs": {},
          }
        }),
      );

      final data = jsonDecode(response.body);

      print("📩 ACTION DONE RESPONSE: $data");

      // return data["result"] != null; // usually true/None
      if (data.containsKey("error")) {
        print("❌ ODOO ERROR: ${data["error"]}");
        return false;
      }

      return true; // ✅ success if no error
    } catch (e) {
      print("❌ COMPLETE ERROR: $e");
      return false;
    }
  }

  Future<List> getWorksheetImages(int worksheetId) async {
    final response = await http.post(
      Uri.parse("$baseUrl/web/dataset/call_kw"),
      headers: {
        "Content-Type": "application/json",
        "Cookie": sessionId!
      },
      body: jsonEncode({
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
          "model": "waste.worksheet",
          "method": "mobile_get_images",
          "args": [worksheetId],
          "kwargs": {}
        }
      }),
    );

    // final data = jsonDecode(response.body);
    // return data["result"] ?? [];

    final data = jsonDecode(response.body);

    if (data == null || data["result"] == null) {
      print("⚠️ No images returned");
      return [];
    }

    if (data["result"] is! List) {
      print("⚠️ Unexpected format: ${data["result"]}");
      return [];
    }

    return data["result"];
  }



  Future<int?> uploadImage({
    required int worksheetId,
    required String base64,
  }) async {
    try {
      final cleaned = cleanBase64(base64);

      if (cleaned.isEmpty) {
        print("⚠️ Invalid image base64");
        return null;
      }

      print("📦 BASE64 LENGTH: ${cleaned.length}");

      final response = await http.post(
        Uri.parse("$baseUrl/web/dataset/call_kw"),
        headers: {
          "Content-Type": "application/json",
          "Cookie": sessionId!,
        },
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "model": "waste.worksheet",
            "method": "upload_image",
            "args": [worksheetId, cleaned, "photo.jpg"],
            "kwargs": {},
          }
        }),
      ).timeout(const Duration(seconds: 60));

      print("📡 STATUS: ${response.statusCode}");
      print("📡 BODY: ${response.body}");

      final data = jsonDecode(response.body);

      if (data["error"] != null) {
        print("❌ ODOO ERROR: ${data["error"]}");
        return null;
      }

      /// 🔥 THIS IS THE KEY FIX
      final result = data["result"];

      if (result is int) {
        return result; // ✅ server_id
      }

      print("⚠️ Unexpected result format: $result");
      return null;

    } catch (e) {
      print("❌ IMAGE UPLOAD ERROR: $e");
      return null;
    }
  }


  // Future<bool> deleteImageFromServer(int imageId) async {
  //   try {
  //     final response = await http.post(
  //       Uri.parse("$baseUrl/web/dataset/call_kw"),
  //       headers: {
  //         "Content-Type": "application/json",
  //         "Cookie": sessionId!,
  //       },
  //       body: jsonEncode({
  //         "jsonrpc": "2.0",
  //         "method": "call",
  //         "params": {
  //           "model": "waste.worksheet.image",
  //           "method": "unlink",
  //           "args": [
  //             [imageId]
  //           ],
  //           "kwargs": {},
  //         }
  //       }),
  //     );
  //
  //     final data = jsonDecode(response.body);
  //
  //     if (data["error"] != null) {
  //       print("❌ DELETE ERROR: ${data["error"]}");
  //       return false;
  //     }
  //
  //     return data["result"] == true;
  //
  //   } catch (e) {
  //     print("❌ DELETE REQUEST FAILED: $e");
  //     return false;
  //   }
  // }

  Future<bool> deleteImageFromServer(int imageId) async {
    try {
      print("🗑️ TRY DELETE IMAGE ID: $imageId");

      final response = await http.post(
        Uri.parse("$baseUrl/web/dataset/call_kw"),
        headers: {
          "Content-Type": "application/json",
          "Cookie": sessionId!,
        },
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "model": "waste.worksheet.image",
            "method": "unlink",
            "args": [
              [imageId]
            ],
            "kwargs": {},
          }
        }),
      );

      print("📡 DELETE STATUS: ${response.statusCode}");
      print("📡 DELETE BODY: ${response.body}");

      final data = jsonDecode(response.body);

      if (data["error"] != null) {
        print("❌ ODOO ERROR: ${data["error"]}");
        return false;
      }

      print("✅ DELETE RESULT: ${data["result"]}");

      return data["result"] == true;

    } catch (e) {
      print("❌ DELETE EXCEPTION: $e");
      return false;
    }
  }

  Future<List> getManagers() async {
    final response = await http.post(
      Uri.parse("$baseUrl/web/dataset/call_kw"),
      headers: {
        "Content-Type": "application/json",
        "Cookie": sessionId!,
      },
      body: jsonEncode({
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
          "model": "waste.worksheet",
          "method": "mobile_get_managers",
          "args": [],
          "kwargs": {},
        }
      }),
    );

    final data = jsonDecode(response.body);

    return data["result"] ?? [];
  }

  Future<bool> finishWorksheet({
    required int worksheetId,
    required int managerId,
  }) async {
    try {
      final response = await http.post(
        Uri.parse("$baseUrl/web/dataset/call_kw"),
        headers: {
          "Content-Type": "application/json",
          "Cookie": sessionId!,
        },
        body: jsonEncode({
          "jsonrpc": "2.0",
          "method": "call",
          "params": {
            "model": "waste.worksheet",
            "method": "mobile_finish_worksheet",
            "args": [worksheetId, managerId],
            "kwargs": {},
          }
        }),
      );

      final data = jsonDecode(response.body);

      if (data["error"] != null) {
        print("❌ FINISH ERROR: ${data["error"]}");
        return false;
      }

      return data["result"] == true;

    } catch (e) {
      print("❌ FINISH ERROR: $e");
      return false;
    }
  }



}


