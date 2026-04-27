import 'dart:convert';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import '../services/local_db.dart';
import '../services/network_service.dart';
import '../services/odoo_service.dart';
import '../services/sync_service.dart';
import 'worksheet_detail_page.dart';
import 'login_page.dart';


class WorksheetListPage extends StatefulWidget {
  final String? filterState; // 👈 ADD THIS
  final Function(Map<String, int>)? onCountsUpdated; // 👈 ADD THIS

  const WorksheetListPage({super.key, this.filterState,  this.onCountsUpdated,});

  @override
  State<WorksheetListPage> createState() => _WorksheetListPageState();
}

class _WorksheetListPageState extends State<WorksheetListPage> {

  final service = OdooService();
  List worksheets = [];

  List filteredWorksheets = [];
  String searchQuery = "";

  List allWorksheets = [];   // 🔥 original data


  // void updateCounts(List data) {
  //   int draft = 0;
  //   int inProgress = 0;
  //   int done = 0;
  //
  //   for (var ws in data) {
  //     final state = (ws["state"] ?? "").toString().toLowerCase();
  //
  //     if (state == "draft") draft++;
  //     if (state == "in_progress") inProgress++;
  //     if (state == "done") done++;
  //   }
  //
  //   print("Counts → Draft:$draft InProgress:$inProgress Done:$done");
  // }
  void updateCounts(List data) {
    int draft = 0;
    int inProgress = 0;
    int done = 0;

    for (var ws in data) {
      final state = (ws["state"] ?? "")
          .toString()
          .toLowerCase()
          .trim()
          .replaceAll(" ", "_");

      if (state == "draft") draft++;
      else if (state == "in_progress") inProgress++;
      else if (state == "done") done++;
    }

    final counts = {
      "all": data.length,
      "draft": draft,
      "in_progress": inProgress,
      "done": done,
    };

    widget.onCountsUpdated?.call(counts); // 🔥 SEND TO HOMEPAGE
  }

  dynamic parseJsonField(dynamic field) {
    if (field == null) return null;

    dynamic value = field;

    // 🔥 KEEP DECODING UNTIL CLEAN
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

  String getName(dynamic field) {
    field = parseJsonField(field); // 🔥 CRITICAL

    if (field == null || field == false) return "";

    if (field is List && field.length > 1) {
      return field[1];
    }

    return field.toString();
  }

  /// Connectivity listener
  late Stream<List<ConnectivityResult>> connectivityStream;

  @override
  void initState() {
    super.initState();

    loadData();

    /// Listen for internet changes
    connectivityStream = Connectivity().onConnectivityChanged;




    connectivityStream.listen((results) async {
      if (!results.contains(ConnectivityResult.none)) {
        print("Internet restored → Auto Sync");

        await SyncService.syncPending();

        // final data = await service.getWorksheets();
        // final data = await service.getWorksheets(forceOnline: true);

        List data = [];

        try {
          data = await service.getWorksheets(forceOnline: true);
        } catch (e) {
          print("❌ SAFE FETCH FAILED: $e");

          // fallback safely
          data = await service.getWorksheets();
        }


        if (!mounted) return;

        allWorksheets = data;

        applyFilter(); // 🔥 KEEP FILTER
      }
    });

  }



  Future<void> loadData() async {
    final data = await service.getWorksheets();

    updateCounts(data);

    if (!mounted) return;

    allWorksheets = data;

    applyFilter(); // 🔥 ALWAYS filter after load
  }



  void applyFilter() {
    List filtered = allWorksheets;

    if (widget.filterState != null && widget.filterState != "all") {
      filtered = allWorksheets.where((ws) {
        final state = (ws["state"] ?? "")
            .toString()
            .toLowerCase()
            .trim();

        return state == widget.filterState;
      }).toList();
    }

    setState(() {
      worksheets = filtered;
      filteredWorksheets = filtered;
    });

    print("FILTER: ${widget.filterState} → ${filteredWorksheets.length}");
  }


  void logout() async {

    await service.clearSession();

    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const LoginPage()),
          (route) => false,
    );

  }

  void filterWorksheets(String query) {
    searchQuery = query;

    setState(() {
      filteredWorksheets = worksheets.where((ws) {
        final name = (ws["name"] ?? "").toString().toLowerCase();
        final service = getName(ws["service_requested_id"]).toLowerCase();

        return name.contains(query.toLowerCase()) ||
            service.contains(query.toLowerCase());
      }).toList();
    });
  }

  Color statusColor(String state) {

    switch (state) {
      case "draft":
        return Colors.orange;
      case "in_progress":
        return Colors.blue;
      case "done":
        return Colors.green;
      default:
        return Colors.grey;
    }

  }

  @override
  Widget build(BuildContext context) {

    return Scaffold(
      //
      // appBar: AppBar(
      //   title: const Text("Worksheets"),
      //
      //
      //   actions: [
      //
      //
      //     /// 🟢 SYNC TO ODOO (UPLOAD)
      //     IconButton(
      //       icon: const Icon(Icons.sync, color: Colors.white),
      //
      //
      //         onPressed: () async {
      //           final result = await Connectivity().checkConnectivity();
      //           final isOnline = !result.contains(ConnectivityResult.none);
      //
      //           if (!isOnline) {
      //             ScaffoldMessenger.of(context).showSnackBar(
      //               const SnackBar(
      //                 content: Text("📡 Offline - Waiting for internet..."),
      //                 backgroundColor: Colors.orange,
      //               ),
      //             );
      //             return;
      //           }
      //
      //           ScaffoldMessenger.of(context).showSnackBar(
      //             const SnackBar(content: Text("🔄 Syncing...")),
      //           );
      //
      //           try {
      //             await SyncService.syncAll();   // 🔥 ONE LINE DOES EVERYTHING
      //             await loadData();
      //
      //             ScaffoldMessenger.of(context).showSnackBar(
      //               const SnackBar(
      //                 content: Text("✅ Sync completed successfully"),
      //                 backgroundColor: Colors.green,
      //               ),
      //             );
      //           } catch (e) {
      //             ScaffoldMessenger.of(context).showSnackBar(
      //               SnackBar(
      //                 content: Text("⚠️ Sync failed: $e"),
      //                 backgroundColor: Colors.red,
      //               ),
      //             );
      //           }
      //         }
      //
      //
      //     ),
      //
      //   ],
      // ),


      body: Column(
        children: [

          /// 🔍 SEARCH BAR
          Padding(
            padding: const EdgeInsets.all(12),
            child: TextField(
              onChanged: filterWorksheets,
              decoration: InputDecoration(
                hintText: "Search worksheets...",
                prefixIcon: const Icon(Icons.search),
                filled: true,
                fillColor: Colors.grey.shade100,
                contentPadding: const EdgeInsets.symmetric(vertical: 0),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
          ),

          /// 📋 LIST
          Expanded(
            child: RefreshIndicator(
              onRefresh: loadData,

              child: filteredWorksheets.isEmpty
                  ? const Center(child: Text("No results found"))
                  : ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: filteredWorksheets.length,
                itemBuilder: (context, index) {
                  final ws = filteredWorksheets[index];
                  final state = ws["state"] ?? "draft";

                  return jobCard(ws, state);
                },
              ),
            ),
          ),
        ],
      ),

    );
  }

  Widget jobCard(Map ws, String state) {

    final color = statusColor(state);

    final serviceRequested = getName(ws["service_requested_id"]);
    final containerType = getName(ws["container_type_id"]);

    final binType = getName(ws["bin_type_id"]);
    final tankVolume = getName(ws["tank_volume_id"]);
    final truck = getName(ws["truck_tanker_id"]);


    String containerDisplay = "";
    String truckDisplay = "";

    /// 🗑️ BIN
    if (containerType.toLowerCase().contains("bin")) {
      if (binType.isNotEmpty) {
        containerDisplay = "🗑️🚮 Bin: $binType";
      }
    }

    /// 💧 TANK (optional if needed later)
    else if (containerType.toLowerCase().contains("tank")) {
      if (tankVolume.isNotEmpty) {
        containerDisplay = "🛢️ Tank: $tankVolume";
      }
    }

    /// 🚚 TRUCK
    if (truck.isNotEmpty) {
      truckDisplay = "🚚️🛢️💧️ Truck Tanker: $truck";
    }

    return InkWell(
      borderRadius: BorderRadius.circular(18),



      onTap: () async {
        final currentState = ws["state"] ?? "draft";

        /// 🔥 ONLY CHANGE IF DRAFT
        if (currentState == "draft") {

          print("🟡 Moving WS ${ws["id"]} → IN_PROGRESS");

          /// ✅ UPDATE UI IMMEDIATELY
          setState(() {
            ws["state"] = "in_progress";
          });

          /// ✅ SAVE TO LOCAL DB
          await LocalDB().updateWorksheetState(ws["id"], "in_progress");

          /// 🌐 TRY UPDATE ODOO
          final success = await service.updateWorksheetState(
            worksheetId: ws["id"],
            state: "in_progress",
          );

          if (!success) {
            print("⚠️ Offline → queued for sync");

            await LocalDB().addPendingAction({
              "type": "update_state",
              "worksheet_id": ws["id"],
              "state": "in_progress",
            });
          }
        }

        /// 👉 THEN OPEN DETAIL PAGE
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => WorksheetDetailPage(
              worksheet: ws,
              worksheetId: ws["id"],
            ),
          ),
        );
      },

      child: Card(
        elevation: 5,
        margin: const EdgeInsets.only(bottom: 14),

        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
        ),

        child: Padding(
          padding: const EdgeInsets.symmetric(
            horizontal: 16,
            vertical: 18,
          ),

          child: Row(
            children: [

              /// LEFT ICON
              Container(
                padding: const EdgeInsets.all(12),

                decoration: BoxDecoration(
                  color: const Color(0xFF1FAF5B).withOpacity(.15),
                  borderRadius: BorderRadius.circular(12),
                ),

                child: const Icon(
                  Icons.assignment_outlined,
                  color: Color(0xFF1FAF5B),
                  size: 28,
                ),
              ),

              const SizedBox(width: 14),

              /// JOB INFO
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [

                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [

                        /// 🔹 WORKSHEET NAME
                        // Text(
                        //   ws["name"] ?? "Worksheet",
                        //   style: const TextStyle(
                        //     fontSize: 17,
                        //     fontWeight: FontWeight.w600,
                        //   ),
                        // ),

                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [

                            /// 🔹 NAME (LEFT)
                            Expanded(
                              child: Text(
                                ws["name"] ?? "Worksheet",
                                style: const TextStyle(
                                  fontSize: 17,
                                  fontWeight: FontWeight.w600,
                                ),
                                overflow: TextOverflow.ellipsis, // 🔥 prevents overflow
                              ),
                            ),

                            const SizedBox(width: 8),

                            /// 🔹 STATUS (RIGHT)
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 10,
                                vertical: 4,
                              ),
                              decoration: BoxDecoration(
                                color: color.withOpacity(.15),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Text(
                                state.toUpperCase(),
                                style: TextStyle(
                                  color: color,
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                          ],
                        ),

                        const SizedBox(height: 4),

                        /// 🔹 SERVICE REQUEST
                        if (serviceRequested.isNotEmpty)
                          Text(
                            serviceRequested,
                            style: const TextStyle(
                              fontSize: 13,
                              color: Colors.black54,
                              fontWeight: FontWeight.w500,
                            ),
                          ),

                        const SizedBox(height: 2),

                        /// 🔹 CONTAINER TYPE

                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [

                            if (containerDisplay.isNotEmpty)
                              Text(
                                containerDisplay,
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: Colors.grey,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),

                            if (truckDisplay.isNotEmpty)
                              Text(
                                truckDisplay,
                                style: const TextStyle(
                                  fontSize: 12,
                                  color: Colors.grey,
                                ),
                              ),
                          ],
                        ),
                        const SizedBox(height: 6),

                        /// 🔹 STATUS BADGE

                      ],
                    ),





                    const SizedBox(height: 6),

                    // Container(
                    //   padding: const EdgeInsets.symmetric(
                    //     horizontal: 10,
                    //     vertical: 4,
                    //   ),
                    //
                    //   decoration: BoxDecoration(
                    //     color: color.withOpacity(.15),
                    //     borderRadius: BorderRadius.circular(10),
                    //   ),
                    //
                    //   child: Text(
                    //     state.toUpperCase(),
                    //     style: TextStyle(
                    //       color: color,
                    //       fontSize: 12,
                    //       fontWeight: FontWeight.bold,
                    //     ),
                    //   ),
                    // ),

                    /// Offline indicator
                    if (ws["offline"] == true)
                      const Padding(
                        padding: EdgeInsets.only(top: 6),
                        child: Text(
                          "Waiting for internet to sync",
                          style: TextStyle(
                            color: Colors.orange,
                            fontSize: 12,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),

                  ],
                ),
              ),

              const Icon(
                Icons.chevron_right,
                size: 28,
                color: Colors.grey,
              ),

            ],
          ),
        ),
      ),
    );
  }
}
