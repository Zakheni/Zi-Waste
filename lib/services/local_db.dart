import 'dart:convert';

import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';

import 'network_service.dart';
import 'odoo_service.dart';

import 'dart:io';
import 'package:path_provider/path_provider.dart';

String? safeString(dynamic v) {
  if (v == null || v == false || v == 0) return null;
  return v.toString();
}

class LocalDB {
  static Database? _db;

  Future<Database> get database async {
    if (_db != null) return _db!;

    final path = join(await getDatabasesPath(), "driver_local.db");

    _db = await openDatabase(
      path,
      version: 7,
      onCreate: (db, version) async {
        await db.execute('''
   CREATE TABLE pending_updates(
      worksheet_id INTEGER PRIMARY KEY,
      arrival_time TEXT,
      return_date TEXT,
      kilometers INTEGER,
      unit_of_measure INTEGER,
      notes_html TEXT,
      product_uom_qty REAL,
      manager_id INTEGER 
    )
    ''');

        await db.execute('''
    CREATE TABLE worksheets(
      id INTEGER PRIMARY KEY,
      name TEXT,
    
      arrival_time TEXT,
      return_date TEXT,
      kilometers INTEGER,
      state TEXT,
    
      service_request_id TEXT,
      partner_id TEXT,
      pickup_point_id TEXT,
      service_requested_id TEXT,
    
      truck_tanker_id TEXT,
      waste_type_id TEXT,
      waste_details_id TEXT,
      bin_type_id TEXT,
      tank_volume_id TEXT,
      container_type_id TEXT,
    
      liters_collected REAL,
      sale_order_id TEXT,
    
      notes_html TEXT,
      product_uom_qty REAL,
    
      pickup_point_bins_summary TEXT,
      planned_date TEXT,
    
      pickup_point_ids TEXT,
      dropoff_point_ids TEXT,
      bin_lifted_ids TEXT,
      bin_dropped_ids TEXT,
    
      billing_amount REAL,
      
      driver_signature TEXT,
      service_provider_signature TEXT,
      
      manifest_document TEXT,
      weighbridge_slip TEXT,
      safety_certificate TEXT
    )
    ''');

        await db.execute('''
    CREATE TABLE units(
      id INTEGER PRIMARY KEY,
      name TEXT
    )
    ''');

        await db.execute('''
   CREATE TABLE pickup_points(
      id INTEGER PRIMARY KEY,
      name TEXT,
      partner_id INTEGER
    )
    ''');

        await db.execute('''
    CREATE TABLE bins(
      id INTEGER PRIMARY KEY,
      name TEXT,
    
      pickup_point_id INTEGER,
      partner_id INTEGER,
    
      container_type_id TEXT,
      bin_type_id TEXT,
      tank_volume_id TEXT,
    
      status TEXT,
      display_info TEXT
    )
    ''');

        await db.execute('''
    CREATE TABLE bin_transactions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      worksheet_id INTEGER,
      pickup_point_id INTEGER,
      dropoff_point_id INTEGER,
      lifted_bins TEXT,
      dropped_bins TEXT,
      synced INTEGER DEFAULT 0
    )
''');
        await db.execute('''
CREATE TABLE images(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  worksheet_id INTEGER,
  file_path TEXT,
  created_at TEXT,
  server_id INTEGER UNIQUE,
  synced INTEGER DEFAULT 0
)
''');

        await db.execute('''
CREATE TABLE IF NOT EXISTS managers (
  id INTEGER PRIMARY KEY,
  name TEXT
)
''');

        await db.execute('''
    CREATE TABLE IF NOT EXISTS settings (
      key TEXT PRIMARY KEY,
      value TEXT
    )
  ''');

      },

      onUpgrade: (db, oldVersion, newVersion) async {
        if (oldVersion < 7) {
          await db.execute(
            "ALTER TABLE pending_updates ADD COLUMN notes_html TEXT",
          );
          await db.execute(
            "ALTER TABLE pending_updates ADD COLUMN product_uom_qty REAL",
          );

          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN driver_id INTEGER",
          );
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN service_request_id TEXT",
          );
          await db.execute("ALTER TABLE worksheets ADD COLUMN partner_id TEXT");
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN pickup_point_id TEXT",
          );
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN service_requested_id TEXT",
          );

          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN truck_tanker_id TEXT",
          );
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN waste_type_id TEXT",
          );
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN waste_details_id TEXT",
          );
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN bin_type_id TEXT",
          );
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN tank_volume_id TEXT",
          );
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN container_type_id TEXT",
          );

          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN liters_collected REAL",
          );
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN sale_order_id TEXT",
          );

          await db.execute("ALTER TABLE worksheets ADD COLUMN notes_html TEXT");
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN product_uom_qty REAL",
          );

          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN pickup_point_bins_summary TEXT",
          );
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN planned_date TEXT",
          );

          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN pickup_point_ids TEXT",
          );
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN dropoff_point_ids TEXT",
          );
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN bin_lifted_ids TEXT",
          );
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN bin_dropped_ids TEXT",
          );

          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN billing_amount REAL",
          );

          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN manifest_document TEXT",
          );
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN weighbridge_slip TEXT",
          );
          await db.execute(
            "ALTER TABLE worksheets ADD COLUMN safety_certificate TEXT",
          );
          await db.execute(
            "ALTER TABLE images ADD COLUMN synced INTEGER DEFAULT 0",
          );

          await db.execute(
            "ALTER TABLE images ADD COLUMN image_base64 TEXT",
          );

          await db.execute('''
              CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
              )
            ''');



          if (oldVersion < 7) {
            await db.execute(
                "ALTER TABLE pending_updates ADD COLUMN manager_id INTEGER"
            );
          }

          /// 🆕 VERSION 5 → IMAGE GALLERY
          if (oldVersion < 7) {
            await db.execute('''
              CREATE TABLE IF NOT EXISTS images(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worksheet_id INTEGER,
                file_path TEXT,
                created_at TEXT,
                server_id INTEGER UNIQUE,
                synced INTEGER DEFAULT 0
              )
            ''');

            print("📸 Images table created");
          }

          if (oldVersion < 7) {
            await db.execute('''
              CREATE TABLE IF NOT EXISTS managers (
                id INTEGER PRIMARY KEY,
                name TEXT
              )
            ''');


          }



        }
      },
    );

    return _db!;
  }

  Future insertPending(Map<String, Object?> data) async {
    final db = await database;

    print("INSERTING INTO SQLITE: $data");

    // await db.insert("pending_updates", data);

    await db.insert(
      "pending_updates",
      data,
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future<List<Map>> getPending() async {
    final db = await database;

    return await db.query("pending_updates");
  }

  Future deletePending(int worksheetId) async {
    final db = await database;

    await db.delete(
      "pending_updates",
      where: "worksheet_id=?",
      whereArgs: [worksheetId],
    );
  }

  Future saveWorksheets(List worksheets) async {
    final db = await database;

    for (var ws in worksheets) {
      await db.insert("worksheets", {
        "id": ws["id"],
        "name": ws["name"],

        "arrival_time": ws["arrival_time"] == false ? null : ws["arrival_time"],
        "return_date": ws["return_date"] == false ? null : ws["return_date"],
        "kilometers": ws["kilometers"],
        "state": ws["state"],

        "service_request_id": jsonEncode(ws["service_request_id"]),
        "partner_id": jsonEncode(ws["partner_id"]),
        "pickup_point_id": jsonEncode(ws["pickup_point_id"]),
        "service_requested_id": jsonEncode(ws["service_requested_id"]),

        "truck_tanker_id": jsonEncode(ws["truck_tanker_id"]),
        "waste_type_id": jsonEncode(ws["waste_type_id"]),
        "waste_details_id": jsonEncode(ws["waste_details_id"]),
        "bin_type_id": jsonEncode(ws["bin_type_id"]),
        "tank_volume_id": jsonEncode(ws["tank_volume_id"]),
        "container_type_id": jsonEncode(ws["container_type_id"]),

        "liters_collected": ws["liters_collected"],
        "sale_order_id": jsonEncode(ws["sale_order_id"]),

        "notes_html": ws["notes_html"] == false ? null : ws["notes_html"],
        "product_uom_qty": ws["product_uom_qty"] == false
            ? null
            : ws["product_uom_qty"],

        "pickup_point_bins_summary": ws["pickup_point_bins_summary"],

        "planned_date": ws["planned_date"],

        "pickup_point_ids": jsonEncode(ws["pickup_point_ids"]),
        "dropoff_point_ids": jsonEncode(ws["dropoff_point_ids"]),
        "bin_lifted_ids": jsonEncode(ws["bin_lifted_ids"]),
        "bin_dropped_ids": jsonEncode(ws["bin_dropped_ids"]),

        "billing_amount": ws["billing_amount"],

        "driver_signature": safeString(ws["driver_signature"]),
        "service_provider_signature": safeString(
          ws["service_provider_signature"],
        ),

        "manifest_document": safeString(ws["manifest_document"]),
        "weighbridge_slip": safeString(ws["weighbridge_slip"]),
        "safety_certificate": safeString(ws["safety_certificate"]),
      }, conflictAlgorithm: ConflictAlgorithm.replace);

      print("SAVED SIGNATURE DRIVER: ${ws["driver_signature"]}");
      print("SAVED SIGNATURE PROVIDER: ${ws["service_provider_signature"]}");
    }
  }

  Future<List<Map>> getWorksheets() async {
    final db = await database;

    return await db.query("worksheets");
  }

  Future saveUnits(List units) async {
    final db = await database;

    await db.delete("units");

    for (var u in units) {
      await db.insert("units", {
        "id": u["id"],
        "name": u["name"],
      }, conflictAlgorithm: ConflictAlgorithm.replace);
    }
  }

  Future savePickupPoints(List data) async {
    final db = await database;

    for (var p in data) {
      print("SAVING PICKUP POINT: $p");

      await db.insert("pickup_points", {
        "id": p["id"],
        "name": p["name"],
        "partner_id": p["partner_id"]?[0],
      }, conflictAlgorithm: ConflictAlgorithm.replace);
    }
  }

  Future saveBins(List data) async {
    final db = await database;

    for (var b in data) {
      await db.insert("bins", {
        "id": b["id"],
        "name": b["name"],

        "pickup_point_id": (b["pickup_point_id"] is List)
            ? b["pickup_point_id"][0]
            : null,

        "partner_id": (b["partner_id"] is List) ? b["partner_id"][0] : null,

        "container_type_id": (b["container_type_id"] is List)
            ? b["container_type_id"][0]
            : null,

        "bin_type_id": (b["bin_type_id"] is List) ? b["bin_type_id"][0] : null,

        "tank_volume_id": (b["tank_volume_id"] is List)
            ? b["tank_volume_id"][0]
            : null,

        "status": b["status"],
        "display_info": b["display_info"],
      }, conflictAlgorithm: ConflictAlgorithm.replace);

      print("SAVING BIN: $b");
    }
  }

  Future debugBins() async {
    final db = await database;
    final data = await db.query("bins");

    print("ALL BINS IN SQLITE: $data");
  }

  Future<List<Map<String, Object?>>> getUnits() async {
    final db = await database;

    return await db.query("units");
  }

  Future<List<Map>> getPickupPoints(int partnerId) async {
    final db = await database;

    return await db.query(
      "pickup_points",
      where: "partner_id=?",
      whereArgs: [partnerId],
    );
  }

  Future<List<Map>> getLiftedBinsLocal(
    int partnerId,
    int pickupPointId,
    int binTypeId,
  ) async {
    final db = await database;

    return await db.query(
      "bins",
      where: """
      pickup_point_id = ?
      AND partner_id = ?
      AND status = ?
      AND bin_type_id = ?
    """,
      whereArgs: [pickupPointId, partnerId, "in_use", binTypeId],
    );
  }

  Future<List<Map>> getDroppedBinsLocal(int binTypeId) async {
    final db = await database;

    return await db.query(
      "bins",

      where: """
      pickup_point_id IS NULL
      AND partner_id IS NULL
      AND status = ?
      AND bin_type_id = ?
    """,
      whereArgs: ["intact", binTypeId],
    );
  }

  Future saveBinTransaction(Map<String, Object?> data) async {
    final db = await database;

    await db.insert(
      "bin_transactions",
      data,
      conflictAlgorithm: ConflictAlgorithm.replace,
    );
  }

  Future syncBinTransactions() async {
    final db = await database;

    final records = await db.query("bin_transactions", where: "synced=0");

    for (var r in records) {
      final success = await OdooService().assignBins(r["worksheet_id"] as int, [
        {
          "pickup_point_id": r["pickup_point_id"],
          "dropoff_point_id": r["dropoff_point_id"],
          "bin_lifted_ids": jsonDecode(r["lifted_bins"] as String),
          "bin_dropped_ids": jsonDecode(r["dropped_bins"] as String),
        },
      ]);

      if (success) {
        await db.update(
          "bin_transactions",
          {"synced": 1},
          where: "id=?",
          whereArgs: [r["id"]],
        );
      }
    }
  }

  Future<void> updateSignatureLocal(
    int worksheetId, {
    String? driverSignature,
    String? providerSignature,
  }) async {
    final db = await database;

    Map<String, dynamic> values = {};

    if (driverSignature != null) {
      // values["driver_signature"] = driverSignature;
      values["driver_signature"] = safeString(driverSignature);
    }

    if (providerSignature != null) {
      // values["service_provider_signature"] = providerSignature;
      values["service_provider_signature"] = safeString(providerSignature);
    }

    await db.update(
      "worksheets",
      values,
      where: "id = ?",
      whereArgs: [worksheetId],
    );

    print("💾 LOCAL SIGNATURE SAVED");
  }

  // =========================
  // 📄 DOCUMENT HELPERS
  // =========================

  Future<void> saveDocumentLocal({
    required int worksheetId,
    String? manifest,
    String? weighbridge,
    String? safety,
  }) async {
    final db = await database;

    String? clean(dynamic v) {
      if (v == null) return null;
      final s = v.toString().trim();
      if (s.isEmpty || s == "false" || s == "0") return null;
      return s;
    }

    final values = <String, dynamic>{};

    final m = clean(manifest);
    final w = clean(weighbridge);
    final s = clean(safety);

    if (m != null) values["manifest_document"] = m;
    if (w != null) values["weighbridge_slip"] = w;
    if (s != null) values["safety_certificate"] = s;

    if (values.isEmpty) return;

    await db.update(
      "worksheets",
      values,
      where: "id = ?",
      whereArgs: [worksheetId],
    );

    print("💾 DOCUMENT SAVED LOCALLY → WS $worksheetId");
  }

  // 🔥 LOAD DOCUMENT FROM SQLITE
  Future<Map<String, dynamic>?> getDocumentLocal(int worksheetId) async {
    final db = await database;

    final result = await db.query(
      "worksheets",
      columns: ["manifest_document", "weighbridge_slip", "safety_certificate"],
      where: "id = ?",
      whereArgs: [worksheetId],
      limit: 1,
    );

    if (result.isNotEmpty) {
      // return result.first;
      final row = result.first;

      return {
        "manifest_document": safeString(row["manifest_document"]),
        "weighbridge_slip": safeString(row["weighbridge_slip"]),
        "safety_certificate": safeString(row["safety_certificate"]),
      };
    }

    return null;
  }

  // =========================
  // 📸 IMAGE STORAGE
  // =========================
  // Future<void> saveImage({
  //   required int worksheetId,
  //   required String base64Image,
  // }) async {
  //   final db = await database;
  //
  //   await db.insert("images", {
  //     "worksheet_id": worksheetId,
  //     "image_base64": base64Image,
  //     "created_at": DateTime.now().toIso8601String(),
  //     "synced": 0, // 🔥 NOT SYNCED YET
  //   });
  //
  //   print("📸 Image saved locally (pending sync)");
  // }

  Future<void> saveImage({
    required int worksheetId,
    required String filePath,
  }) async {
    final db = await database;

    await db.insert("images", {
      "worksheet_id": worksheetId,
      "file_path": filePath,
      "created_at": DateTime.now().toIso8601String(),
      "synced": 0,
    });
    print("📸 Image saved locally (pending sync)");
  }

  // Future<void> saveImagesFromServer(int worksheetId, List images) async {
  //   final db = await database;
  //
  //   for (var img in images) {
  //     final base64 = img["image"];
  //
  //     if (base64 == null || base64 == false) continue;
  //
  //     await db.insert("images", {
  //       "worksheet_id": worksheetId,
  //       "image_base64": base64,
  //       "created_at": DateTime.now().toIso8601String(),
  //       "synced": 1, // ✅ already synced
  //     }, conflictAlgorithm: ConflictAlgorithm.replace);
  //   }
  //
  //   print("📥 Images saved from server");
  // }
  // Future<void> saveImagesFromServer(int worksheetId, List images) async {
  //   final db = await database;
  //
  //   for (var img in images) {
  //     final base64 = img["image"];
  //     final serverId = img["id"]; // 👈 IMPORTANT
  //
  //     if (base64 == null || base64 == false || serverId == null) continue;
  //
  //     // ✅ CHECK IF EXISTS FIRST
  //     final existing = await db.query(
  //       "images",
  //       where: "server_id = ?",
  //       whereArgs: [serverId],
  //     );
  //
  //     if (existing.isNotEmpty) {
  //       print("⚠️ Image already exists → skipping ID $serverId");
  //       continue;
  //     }
  //
  //     await db.insert(
  //       "images",
  //       {
  //         "worksheet_id": worksheetId,
  //         "image_base64": base64,
  //         "server_id": serverId,
  //         "created_at": DateTime.now().toIso8601String(),
  //         "synced": 1,
  //       },
  //     );
  //   }
  //
  //   print("📥 Images saved from server (NO DUPLICATES)");
  // }

  Future<String> base64ToFile(String base64) async {
    final bytes = base64Decode(base64);
    final dir = await getApplicationDocumentsDirectory();

    final file = File('${dir.path}/${DateTime.now().millisecondsSinceEpoch}.jpg');

    await file.writeAsBytes(bytes);

    return file.path;
  }

  // Future<void> saveImagesFromServer(int worksheetId, List images) async {
  //   final db = await database;
  //
  //   for (var img in images) {
  //     final base64 = img["image"];
  //     final serverId = img["id"];
  //
  //     if (base64 == null || base64 == false || serverId == null) continue;
  //
  //     final existing = await db.query(
  //       "images",
  //       where: "server_id = ?",
  //       whereArgs: [serverId],
  //     );
  //
  //     if (existing.isNotEmpty) continue;
  //
  //     final filePath = await base64ToFile(base64); // ✅ convert
  //
  //     await db.insert("images", {
  //       "worksheet_id": worksheetId,
  //       "file_path": filePath, // ✅ CORRECT
  //       "server_id": serverId,
  //       "created_at": DateTime.now().toIso8601String(),
  //       "synced": 1,
  //     });
  //   }
  // }

  Future<void> saveImagesFromServer(int worksheetId, List images) async {
    final db = await database;

    for (var img in images) {
      final base64 = img["image"];
      final serverId = img["id"];

      if (base64 == null || serverId == null) continue;

      /// ✅ HARD CHECK (IMPORTANT)
      final existing = await db.query(
        "images",
        where: "server_id = ?",
        whereArgs: [serverId],
      );

      if (existing.isNotEmpty) {
        print("⚠️ Duplicate prevented → $serverId");
        continue;
      }

      /// 🔥 convert to file
      final filePath = await base64ToFile(base64);

      await db.insert("images", {
        "worksheet_id": worksheetId,
        "file_path": filePath,
        "server_id": serverId,
        "created_at": DateTime.now().toIso8601String(),
        "synced": 1,
      });
    }
  }

  Future<List<Map<String, dynamic>>> getImages(int worksheetId) async {
    final db = await database;
    //
    // return await db.query(
    //   "images",
    //   where: "worksheet_id = ?",
    //   whereArgs: [worksheetId],
    //   orderBy: "id DESC",
    // );
    return await db.query(
      "images",
      where: "worksheet_id = ?",
      whereArgs: [worksheetId],
      orderBy: "id DESC",
      limit: 10, // 🔥 VERY IMPORTANT
    );

  }

  Future<void> updateWorksheetState(int id, String state) async {
    final db = await database;

    await db.update(
      "worksheets",
      {"state": state},
      where: "id = ?",
      whereArgs: [id],
    );

    print("💾 LOCAL STATE UPDATED → WS $id = $state");
  }

  Future<void> addPendingAction(Map<String, dynamic> action) async {
    final db = await database;

    await db.insert("pending_actions", {
      "type": action["type"],
      "data": jsonEncode(action),
      "created_at": DateTime.now().toIso8601String(),
    });

    print("📝 QUEUED ACTION → ${action["type"]}");
  }

  Future<void> deleteImageLocal(int id) async {
    final db = await database;

    await db.delete(
      "images",
      where: "id = ?",
      whereArgs: [id],
    );

    print("🗑️ LOCAL IMAGE DELETED → $id");
  }

  Future<void> saveManagers(List managers) async {
    final db = await database;

    for (var m in managers) {
      await db.insert(
        "managers",
        {
          "id": m["id"],
          "name": m["name"],
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
  }

  Future<List<Map<String, dynamic>>> getManagers() async {
    final db = await database;
    return await db.query("managers");
  }

  Future<void> saveLastManager(int managerId) async {
    final db = await database;

    await db.insert(
      "settings",
      {
        "key": "last_manager",
        "value": managerId.toString(),
      },
      conflictAlgorithm: ConflictAlgorithm.replace,
    );

    print("💾 Saved last manager → $managerId");
  }


}
