import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import '../services/odoo_service.dart';
import '../services/sync_service.dart';
import 'login_page.dart';
import 'worksheet_list_page.dart';
import 'profile_page.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int currentIndex = 0;
  String selectedFilter = "all";
  final service = OdooService();

  Map<String, int> statusCounts = {
    "all": 0,
    "draft": 0,
    "in_progress": 0,
    "done": 0,
  };

  @override
  void initState() {
    super.initState();
    loadCounts(); // 🔥 FIX: load counts when app starts
  }

  Future<void> loadCounts() async {
    final data = await service.getWorksheets();

    int draft = 0;
    int inProgress = 0;
    int done = 0;

    for (var ws in data) {
      final state = (ws["state"] ?? "")
          .toString()
          .toLowerCase()
          .trim()
          .replaceAll(" ", "_");

      if (state == "draft")
        draft++;
      else if (state == "in_progress")
        inProgress++;
      else if (state == "done") done++;
    }

    setState(() {
      statusCounts = {
        "all": data.length,
        "draft": draft,
        "in_progress": inProgress,
        "done": done,
      };
    });

    print("🔥 HOMEPAGE COUNTS: $statusCounts");
  }

  void logout() async {
    await service.clearSession();

    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const LoginPage()),
          (route) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      const HomeTab(),
      WorksheetListPage(
        filterState: selectedFilter,
        onCountsUpdated: (counts) {
          setState(() {
            statusCounts = counts;
          });
        },
      ),
      const ProfilePage(),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text(["Dashboard", "Worksheets", "Profile"][currentIndex]),
        backgroundColor: Colors.green,
        actions: [
          if (currentIndex == 1)
            IconButton(
              icon: const Icon(Icons.sync),
              onPressed: () async {
                final result = await Connectivity().checkConnectivity();
                final isOnline = !result.contains(ConnectivityResult.none);

                if (!isOnline) {
                  ScaffoldMessenger.of(context)
                      .showSnackBar(const SnackBar(content: Text("📡 Offline")));
                  return;
                }

                ScaffoldMessenger.of(context)
                    .showSnackBar(
                    const SnackBar(content: Text("🔄 Syncing...")));

                await SyncService.syncAll();
                await loadCounts(); // 🔥 refresh counts after sync

                ScaffoldMessenger.of(context)
                    .showSnackBar(const SnackBar(content: Text("✅ Synced")));
              },
            ),
        ],
      ),

      drawer: Drawer(
        child: Column(
          children: [
            const DrawerHeader(
              decoration: BoxDecoration(color: Color(0xFF1FAF5B)),
              child: Center(
                child: Text(
                  "Driver Menu",
                  style: TextStyle(color: Colors.white, fontSize: 22),
                ),
              ),
            ),

            ListTile(
              leading: const Icon(Icons.home, color: Colors.purple),
              title: const Text("Home"),
              onTap: () {
                Navigator.pop(context);
                Future.delayed(const Duration(milliseconds: 200), () {
                  if (!mounted) return;
                  setState(() {
                    currentIndex = 0;
                  });
                });
              },
            ),

            ListTile(
              leading: const Icon(Icons.list_alt, color: Colors.green),
              title: const Text("My Worksheets"),
              onTap: () {
                Navigator.pop(context);
                Future.delayed(const Duration(milliseconds: 200), () {
                  if (!mounted) return;
                  setState(() {
                    currentIndex = 1;
                  });
                });
              },
            ),
            ListTile(
              leading: const Icon(Icons.person, color: Colors.orangeAccent),
              title: const Text("Profile"),
              onTap: () {
                Navigator.pop(context);
                Future.delayed(const Duration(milliseconds: 200), () {
                  if (!mounted) return;
                  setState(() {
                    currentIndex = 2;
                  });
                });
              },
            ),
            const Spacer(),
            SafeArea(
              top: false,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Divider(),
                  ListTile(
                    leading: const Icon(Icons.logout, color: Colors.red),
                    title: const Text("Logout"),
                    onTap: logout,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),

      body: pages[currentIndex],

      bottomNavigationBar: BottomNavigationBar(
        currentIndex: currentIndex,
        selectedItemColor: Colors.green,
        type: BottomNavigationBarType.fixed,
        onTap: (index) {
          setState(() {
            currentIndex = index;
          });
        },
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.home), label: "Home"),
          BottomNavigationBarItem(icon: Icon(Icons.list), label: "Worksheets"),
          BottomNavigationBarItem(icon: Icon(Icons.person), label: "Profile"),
        ],
      ),
    );
  }
}

class HomeTab extends StatelessWidget {
  const HomeTab({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        SizedBox(
          height: 180,
          width: double.infinity,
          child: Image.asset("assets/images/waste.jpg", fit: BoxFit.cover),
        ),

        const SizedBox(height: 20),

        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                statusButton(context, "All", Colors.grey, "all"),
                statusButton(context, "Draft", Colors.orange, "draft"),
                statusButton(
                    context, "In Progress", Colors.blue, "in_progress"),
                statusButton(context, "Done", Colors.green, "done"),
              ],
            ),
          ),
        ),

        const SizedBox(height: 20),

        Expanded(
          child: GridView.count(
            crossAxisCount: 2,
            padding: const EdgeInsets.all(16),
            children: [
              homeCard(context, "Worksheets", Icons.list_alt, Colors.blue, () {
                final parent =
                context.findAncestorStateOfType<_HomePageState>();
                parent?.setState(() {
                  parent.currentIndex = 1;
                });
              }),
              homeCard(context, "Profile", Icons.person, Colors.orange, () {
                final parent =
                context.findAncestorStateOfType<_HomePageState>();
                parent?.setState(() {
                  parent.currentIndex = 2;
                });
              }),
            ],
          ),
        ),
      ],
    );
  }
}

Widget homeCard(BuildContext context,
    String title,
    IconData icon,
    Color color,
    VoidCallback onTap,) {
  return InkWell(
    onTap: onTap,
    child: Container(
      margin: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 40, color: color),
          const SizedBox(height: 10),
          Text(title, style: TextStyle(color: color)),
        ],
      ),
    ),
  );
}

Widget statusButton(BuildContext context,
    String title,
    Color color,
    String state,) {
  final parent = context.findAncestorStateOfType<_HomePageState>();
  final count = parent?.statusCounts[state] ?? 0;

  return GestureDetector(
    onTap: () {
      parent?.setState(() {
        parent.selectedFilter = state;
        parent.currentIndex = 1;
      });
    },
    child: Container(
      margin: const EdgeInsets.only(right: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: parent?.selectedFilter == state
            ? color.withOpacity(0.3)
            : color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(25),
      ),
      child: Row(
        children: [
          Text(
            title,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(width: 6),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              "$count",
              style: const TextStyle(
                color: Colors.white,
                fontSize: 11,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
    ),
  );
}


// import 'package:connectivity_plus/connectivity_plus.dart';
// import 'package:flutter/material.dart';
// import '../services/odoo_service.dart';
// import '../services/sync_service.dart';
// import 'login_page.dart';
// import 'worksheet_list_page.dart';
// import 'profile_page.dart';
//
// class HomePage extends StatefulWidget {
//   const HomePage({super.key});
//
//   @override
//   State<HomePage> createState() => _HomePageState();
// }
//
// class _HomePageState extends State<HomePage> {
//   int currentIndex = 0;
//   String selectedFilter = "all";
//   final service = OdooService();
//
//   Map<String, int> statusCounts = {
//     "all": 0,
//     "draft": 0,
//     "in_progress": 0,
//     "done": 0,
//   };
//
//   // // 👇👇👇 PUT IT HERE (inside the class)
//   // Widget statusButton(
//   //     String title,
//   //     Color color,
//   //     String state,
//   //     ) {
//   //   return GestureDetector(
//   //     onTap: () {
//   //       setState(() {
//   //         selectedFilter = state;
//   //         currentIndex = 1; // go to Worksheet list
//   //       });
//   //     },
//   //     child: Container(
//   //       margin: const EdgeInsets.only(right: 8),
//   //       padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
//   //       decoration: BoxDecoration(
//   //         color: selectedFilter == state
//   //             ? color.withOpacity(0.3)
//   //             : color.withOpacity(0.1),
//   //         borderRadius: BorderRadius.circular(25),
//   //       ),
//   //       child: Text(
//   //         title,
//   //         style: TextStyle(
//   //           color: color,
//   //           fontWeight: FontWeight.bold,
//   //         ),
//   //       ),
//   //     ),
//   //   );
//   // }
//
//
//   void updateCounts(List data) {
//     int draft = 0;
//     int inProgress = 0;
//     int done = 0;
//
//     for (var ws in data) {
//       // 🔥 normalize state (VERY IMPORTANT)
//       final state = (ws["state"] ?? "")
//           .toString()
//           .toLowerCase()
//           .trim()
//           .replaceAll(" ", "_");
//
//       if (state == "draft") {
//         draft++;
//       } else if (state == "in_progress") {
//         inProgress++;
//       } else if (state == "done") {
//         done++;
//       }
//     }
//
//     setState(() {
//       statusCounts["draft"] = draft;
//       statusCounts["in_progress"] = inProgress;
//       statusCounts["done"] = done;
//       statusCounts["all"] = data.length;
//     });
//
//     // 🧪 Debug (you can remove later)
//     print("COUNTS → All:${data.length}, Draft:$draft, InProgress:$inProgress, Done:$done");
//
//   }
//
//   void logout() async {
//     await service.clearSession();
//
//     Navigator.pushAndRemoveUntil(
//       context,
//       MaterialPageRoute(builder: (_) => const LoginPage()),
//       (route) => false,
//     );
//   }
//
//   @override
//   Widget build(BuildContext context) {
//     /// ✅ PAGES
//     // final pages = [
//     //   HomeTab(),
//     //   // const WorksheetListPage(),
//     //   // const Center(child: Text("Gallery")),
//     //   WorksheetListPage(filterState: selectedFilter),
//     //   const ProfilePage(),
//     // ];
//
//     final pages = [
//       const HomeTab(),
//
//       WorksheetListPage(
//         filterState: selectedFilter,
//         onCountsUpdated: (counts) {
//           setState(() {
//             statusCounts = counts;
//           });
//         },
//       ),
//
//       const ProfilePage(),
//     ];
//
//
//
//     return Scaffold(
//       /// ✅ APP BAR CHANGES WITH TAB
//       appBar: AppBar(
//         title: Text(["Dashboard", "Worksheets", "Profile"][currentIndex]),
//         backgroundColor: Colors.green,
//
//         actions: [
//           if (currentIndex == 1)
//             IconButton(
//               icon: const Icon(Icons.sync),
//               onPressed: () async {
//                 final result = await Connectivity().checkConnectivity();
//                 final isOnline = !result.contains(ConnectivityResult.none);
//
//                 if (!isOnline) {
//                   ScaffoldMessenger.of(
//                     context,
//                   ).showSnackBar(const SnackBar(content: Text("📡 Offline")));
//                   return;
//                 }
//
//                 ScaffoldMessenger.of(
//                   context,
//                 ).showSnackBar(const SnackBar(content: Text("🔄 Syncing...")));
//
//                 await SyncService.syncAll();
//
//                 ScaffoldMessenger.of(
//                   context,
//                 ).showSnackBar(const SnackBar(content: Text("✅ Synced")));
//               },
//             ),
//         ],
//       ),
//
//
//       /// ✅ DRAWER GLOBAL
//       drawer: Drawer(
//         child: Column(
//           children: [
//             const DrawerHeader(
//               decoration: BoxDecoration(color: Color(0xFF1FAF5B)),
//               child: Center(
//                 child: Text(
//                   "Driver Menu",
//                   style: TextStyle(color: Colors.white, fontSize: 22),
//                 ),
//               ),
//             ),
//
//
//             ListTile(
//               leading: const Icon(Icons.list_alt, color: Colors.green),
//               title: const Text("My Worksheets"),
//               onTap: () {
//                 Navigator.pop(context);
//
//                 Future.delayed(const Duration(milliseconds: 200), () {
//                   if (!mounted) return;
//                   setState(() {
//                     currentIndex = 1;
//                   });
//                 });
//               },
//             ),
//
//             ListTile(
//               leading: const Icon(Icons.person, color: Colors.orangeAccent),
//               title: const Text("Profile"),
//               onTap: () {
//                 Navigator.pop(context);
//
//                 Future.delayed(const Duration(milliseconds: 200), () {
//                   if (!mounted) return;
//                   setState(() {
//                     currentIndex = 2;
//                   });
//                 });
//               },
//             ),
//
//
//             const Spacer(),
//
//             SafeArea(
//               top: false, // 🔥 important (only protect bottom)
//               child: Column(
//                 mainAxisSize: MainAxisSize.min,
//                 children: [
//                   const Divider(),
//
//                   ListTile(
//                     leading: const Icon(Icons.logout, color: Colors.red),
//                     title: const Text("Logout"),
//                     onTap: logout,
//                   ),
//                 ],
//               ),
//             ),
//           ],
//         ),
//       ),
//
//       /// ✅ BODY SWITCHES
//       body: pages[currentIndex],
//
//       /// ✅ BOTTOM NAV FIXED
//       bottomNavigationBar: BottomNavigationBar(
//         currentIndex: currentIndex,
//         selectedItemColor: Colors.green,
//         type: BottomNavigationBarType.fixed,
//         // 🔥 IMPORTANT FIX
//         onTap: (index) {
//           setState(() {
//             currentIndex = index;
//           });
//         },
//         items: const [
//           BottomNavigationBarItem(icon: Icon(Icons.home), label: "Home"),
//           BottomNavigationBarItem(icon: Icon(Icons.list), label: "Worksheets"),
//           BottomNavigationBarItem(icon: Icon(Icons.person), label: "Profile"),
//         ],
//       ),
//     );
//   }
// }
//
// class HomeTab extends StatelessWidget {
//   const HomeTab({super.key});
//
//   @override
//   Widget build(BuildContext context) {
//     return Column(
//       children: [
//         /// IMAGE
//         SizedBox(
//           height: 180,
//           width: double.infinity,
//           child: Image.asset("assets/images/waste.jpg", fit: BoxFit.cover),
//         ),
//
//         const SizedBox(height: 20),
//
//
//         const SizedBox(height: 10),
//
//         Padding(
//           padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
//           child: SingleChildScrollView(
//             scrollDirection: Axis.horizontal,
//             child: Row(
//               children: [
//                 statusButton(context, "All", Colors.grey, "all"),
//                 statusButton(context, "Draft", Colors.orange, "draft"),
//                 statusButton(context, "In Progress", Colors.blue, "in_progress"),
//                 statusButton(context, "Done", Colors.green, "done"),
//               ],
//             ),
//           ),
//         ),
//
//         const SizedBox(height: 20),
//
//         /// CARDS
//         Expanded(
//           child: GridView.count(
//             crossAxisCount: 2,
//             padding: const EdgeInsets.all(16),
//             children: [
//               /// 📋 WORKSHEETS
//               homeCard(context, "Worksheets", Icons.list_alt, Colors.blue, () {
//                 final parent = context
//                     .findAncestorStateOfType<_HomePageState>();
//
//                 parent?.setState(() {
//                   parent.currentIndex = 1;
//                 });
//               }),
//
//               /// 👤 PROFILE
//               homeCard(context, "Profile", Icons.person, Colors.orange, () {
//                 final parent = context
//                     .findAncestorStateOfType<_HomePageState>();
//
//                 parent?.setState(() {
//                   parent.currentIndex = 2;
//                 });
//               }),
//             ],
//           ),
//         ),
//       ],
//     );
//   }
// }
//
// /// 🔥 CARD WIDGET
// Widget homeCard(
//   BuildContext context,
//   String title,
//   IconData icon,
//   Color color,
//   VoidCallback onTap,
// ) {
//   return InkWell(
//     onTap: onTap,
//     child: Container(
//       margin: const EdgeInsets.all(8),
//       decoration: BoxDecoration(
//         color: color.withOpacity(0.1),
//         borderRadius: BorderRadius.circular(16),
//       ),
//       child: Column(
//         mainAxisAlignment: MainAxisAlignment.center,
//         children: [
//           Icon(icon, size: 40, color: color),
//           const SizedBox(height: 10),
//           Text(title, style: TextStyle(color: color)),
//         ],
//       ),
//     ),
//   );
// }
//
//
// Widget statusButton(
//     BuildContext context,
//     String title,
//     Color color,
//     String state,
//     ) {
//   final parent = context.findAncestorStateOfType<_HomePageState>();
//   final count = parent?.statusCounts[state] ?? 0;
//
//   return GestureDetector(
//     onTap: () {
//       parent?.setState(() {
//         parent.selectedFilter = state;
//         parent.currentIndex = 1;
//       });
//     },
//     child: Container(
//       margin: const EdgeInsets.only(right: 8),
//       padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
//       decoration: BoxDecoration(
//         color: parent?.selectedFilter == state
//             ? color.withOpacity(0.3)
//             : color.withOpacity(0.1),
//         borderRadius: BorderRadius.circular(25),
//       ),
//       child: Row(
//         children: [
//           Text(
//             title,
//             style: TextStyle(
//               color: color,
//               fontWeight: FontWeight.bold,
//             ),
//           ),
//           const SizedBox(width: 6),
//
//           /// 🔥 BADGE
//           Container(
//             padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
//             decoration: BoxDecoration(
//               color: color,
//               borderRadius: BorderRadius.circular(12),
//             ),
//             child: Text(
//               "$count",
//               style: const TextStyle(
//                 color: Colors.white,
//                 fontSize: 11,
//                 fontWeight: FontWeight.bold,
//               ),
//             ),
//           ),
//         ],
//       ),
//     ),
//   );
// }