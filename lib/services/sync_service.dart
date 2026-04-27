import 'dart:convert';
import 'dart:io';

import 'local_db.dart';
import 'odoo_service.dart';
import 'network_service.dart';


class SyncService {

  static Future<void> syncAll() async {


    bool online = await NetworkService.isOnline();

    if (!online) {
      print("SYNC STOPPED → No internet");
      // bool online = true; // 🔥 FORCE ONLINE FOR TEST
      return;
    }

    print("🌐 INTERNET BACK → FULL SYNC START");

    final db = LocalDB();

    /// 🔥1️⃣ Sync worksheet updates
    await syncPending();// 🔥 ADD THIS
    /// 🔥2️⃣ Sync bin transactions
    await db.syncBinTransactions();// 🔥 ADD THIS
    /// 🔥3️⃣ Sync signatures (ADD THIS)
    await syncSignatures(); // 🔥 ADD THIS
    /// 🔥4️⃣ Sync Documents (ADD THIS)
    await syncDocuments(); // 🔥 ADD THIS
    /// 🔥5️⃣ Sync signatures (ADD THIS)
    await syncImages(); // 🔥 ADD THIS

    print("✅ FULL SYNC COMPLETE");



  }


  static Future<void> syncPending() async {

    final db = LocalDB();
    final service = OdooService();

    final rows = await db.getPending();

    // for (var r in rows) {
    //
    //   final success = await service.updateWorksheet(
    //     r["worksheet_id"],
    //     r["arrival_time"] ?? "",
    //     r["return_date"] ?? "",
    //     r["kilometers"] ?? 0,
    //     r["unit_of_measure"],
    //     r["notes_html"] ?? "",
    //     (r["product_uom_qty"] ?? 0).toDouble(),
    //   );
    //
    //   if (success) {
    //     await db.deletePending(r["worksheet_id"]);
    //     print("SYNC SUCCESS → Worksheet ${r["worksheet_id"]}");
    //   }
    // }

    for (var r in rows) {

      final worksheetId = r["worksheet_id"];
      final managerId = r["manager_id"]; // 🔥 ADD THIS

      final success = await service.updateWorksheet(
        worksheetId,
        r["arrival_time"] ?? "",
        r["return_date"] ?? "",
        r["kilometers"] ?? 0,
        r["unit_of_measure"],
        r["notes_html"] ?? "",
        (r["product_uom_qty"] ?? 0).toDouble(),
      );

      if (success) {

        print("✅ SYNCED WS → $worksheetId");

        /// 🔥 SEND EMAIL AFTER SYNC (CRITICAL)
        if (managerId != null) {
          final emailSent = await service.finishWorksheet(
            worksheetId: worksheetId,
            managerId: managerId,
          );

          print(emailSent
              ? "📧 EMAIL SENT → WS $worksheetId"
              : "❌ EMAIL FAILED → WS $worksheetId");
        }

        await db.deletePending(worksheetId);
      }
    }

  }

  static Future<void> syncSignatures() async {
    final db = LocalDB();
    final service = OdooService();

    final worksheets = await db.getWorksheets();

    for (var ws in worksheets) {
      final driverSig = ws["driver_signature"];
      final providerSig = ws["service_provider_signature"];

      /// 🚫 skip if no signature
      if ((driverSig == null || driverSig == "") &&
          (providerSig == null || providerSig == "")) {
        continue;
      }

      print("🔄 SYNC SIGNATURE → WS ${ws["id"]}");

      final success = await service.updateSignature(
        worksheetId: ws["id"],
        driverSignature: driverSig,
        providerSignature: providerSig,
      );

      if (success) {
        print("✅ SIGNATURE SYNCED → WS ${ws["id"]}");
      } else {
        print("❌ SIGNATURE FAILED → WS ${ws["id"]}");
      }
    }
  }

  static Future<void> syncDocuments() async {
    final db = LocalDB();
    final service = OdooService();

    final worksheets = await db.getWorksheets();

    for (var ws in worksheets) {
      final manifest = ws["manifest_document"];
      final weighbridge = ws["weighbridge_slip"];
      final safety = ws["safety_certificate"];

      /// 🚫 skip if nothing to upload
      if ((manifest == null || manifest == "") &&
          (weighbridge == null || weighbridge == "") &&
          (safety == null || safety == "")) {
        continue;
      }

      print("📄 SYNC DOCUMENTS → WS ${ws["id"]}");

      final success = await service.uploadDocument(
        worksheetId: ws["id"],
        manifest: manifest,
        weighbridge: weighbridge,
        safety: safety,
        filename: "auto_upload.pdf",
      );

      if (success) {
        print("✅ DOCUMENT SYNCED → WS ${ws["id"]}");
      } else {
        print("❌ DOCUMENT SYNC FAILED → WS ${ws["id"]}");
      }
    }
  }

  // static Future<void> syncImages() async {
  //   final db = LocalDB();
  //   final service = OdooService();
  //
  //   final database = await db.database;
  //
  //
  //   final unsynced = await database.rawQuery(
  //       "SELECT id, worksheet_id FROM images WHERE synced = 0"
  //   );
  //
  //   for (var img in unsynced) {
  //
  //
  //
  //     final full = await database.rawQuery(
  //       "SELECT id, worksheet_id, substr(image_base64, 1, 1000000) as file_path FROM images WHERE id = ?",
  //       [img["id"]],
  //     );
  //
  //     final row = full.first;
  //
  //     print("📸 SYNC IMAGE → WS ${row["worksheet_id"]}");
  //
  //     final success = await service.uploadImage(
  //       worksheetId: row["worksheet_id"] as int,
  //       base64: row["image_base64"] as String,
  //     );
  //
  //     if (success) {
  //       await database.update(
  //         "images",
  //         {"synced": 1},
  //         where: "id = ?",
  //         whereArgs: [row["id"]],
  //       );
  //
  //       print("✅ IMAGE SYNCED");
  //     } else {
  //       print("❌ IMAGE FAILED");
  //     }
  //   }
  //
  // }

  // static Future<void> syncImages() async {
  //   final db = LocalDB();
  //   final service = OdooService();
  //
  //   final database = await db.database;
  //
  //   /// 🔥 GET UNSYNCED IMAGES
  //   final unsynced = await database.query(
  //     "images",
  //     where: "synced = 0",
  //   );
  //
  //   for (var row in unsynced) {
  //     try {
  //       final int id = row["id"] as int;
  //       final int worksheetId = row["worksheet_id"] as int;
  //       final String? filePath = row["file_path"] as String?;
  //
  //       if (filePath == null || filePath.isEmpty) {
  //         print("❌ Missing file path → skipping image $id");
  //         continue;
  //       }
  //
  //       final file = File(filePath);
  //
  //       /// 🚫 FILE DOES NOT EXIST
  //       if (!await file.exists()) {
  //         print("❌ File not found → $filePath");
  //         continue;
  //       }
  //
  //       /// 📦 READ FILE
  //       final bytes = await file.readAsBytes();
  //
  //       if (bytes.isEmpty) {
  //         print("⚠️ Empty image file → $filePath");
  //         continue;
  //       }
  //
  //       /// 🔥 CONVERT TO BASE64 FOR ODOO
  //       final base64Image = base64Encode(bytes);
  //
  //       print("📸 SYNC IMAGE → WS $worksheetId (size: ${bytes.length})");
  //
  //       final success = await service.uploadImage(
  //         worksheetId: worksheetId,
  //         base64: base64Image,
  //       );
  //
  //       if (success) {
  //         await database.update(
  //           "images",
  //           {"synced": 1},
  //           where: "id = ?",
  //           whereArgs: [id],
  //         );
  //
  //         print("✅ IMAGE SYNCED → ID $id");
  //       } else {
  //         print("❌ IMAGE FAILED → ID $id");
  //       }
  //     } catch (e) {
  //       print("❌ SYNC IMAGE ERROR: $e");
  //     }
  //   }
  // }

  static Future<void> syncImages() async {
    final db = LocalDB();
    final service = OdooService();

    final database = await db.database;

    /// 🔥 GET UNSYNCED IMAGES
    final unsynced = await database.query(
      "images",
      where: "synced = 0",
    );

    for (var row in unsynced) {
      try {
        final int id = row["id"] as int;
        final int worksheetId = row["worksheet_id"] as int;
        final String? filePath = row["file_path"] as String?;

        if (filePath == null || filePath.isEmpty) {
          print("❌ Missing file path → skipping image $id");
          continue;
        }

        final file = File(filePath);

        /// 🚫 FILE DOES NOT EXIST
        if (!await file.exists()) {
          print("❌ File not found → $filePath");
          continue;
        }

        /// 📦 READ FILE
        final bytes = await file.readAsBytes();

        if (bytes.isEmpty) {
          print("⚠️ Empty image file → $filePath");
          continue;
        }

        /// 🔥 CONVERT TO BASE64 FOR ODOO
        final base64Image = base64Encode(bytes);

        print("📸 SYNC IMAGE → WS $worksheetId (size: ${bytes.length})");

        /// 🔥 NOW RETURNS server_id (NOT bool)
        final int? serverId = await service.uploadImage(
          worksheetId: worksheetId,
          base64: base64Image,
        );

        /// ✅ SUCCESS CASE
        if (serverId != null) {
          await database.update(
            "images",
            {
              "synced": 1,
              "server_id": serverId, // 🔥 CRITICAL FIX
            },
            where: "id = ?",
            whereArgs: [id],
          );

          print("✅ IMAGE SYNCED → ID $id → server_id $serverId");
        } else {
          print("❌ IMAGE FAILED → ID $id");
        }
      } catch (e) {
        print("❌ SYNC IMAGE ERROR: $e");
      }
    }
  }

}

