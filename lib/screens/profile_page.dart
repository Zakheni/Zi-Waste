import 'package:flutter/material.dart';
import '../services/odoo_service.dart';

class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key});

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  final service = OdooService();
  Map<String, dynamic>? profile;
  bool loading = true;

  String safeValue(dynamic value) {
    if (value == null || value == false) return "-";
    return value.toString();
  }

  @override
  void initState() {
    super.initState();
    loadProfile();
  }

  Future<void> loadProfile() async {
    final data = await service.getProfile();

    if (!mounted) return;

    setState(() {
      profile = data;
      loading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : profile == null
          ? const Center(child: Text("Failed to load profile"))
          : Column(
        children: [
          /// 🔥 HEADER
          Container(
            width: double.infinity,
            padding: const EdgeInsets.only(top: 60, bottom: 30),
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [Color(0xFF1FAF5B), Color(0xFF159A4F)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
              borderRadius: BorderRadius.vertical(
                bottom: Radius.circular(30),
              ),
            ),
            child: Column(
              children: [
                /// 👤 AVATAR
                CircleAvatar(
                  radius: 45,
                  backgroundColor: Colors.white,
                  child: const Icon(
                    Icons.person,
                    size: 50,
                    color: Colors.lightGreen,
                  ),
                ),

                const SizedBox(height: 12),

                /// 👤 NAME
                Text(
                  safeValue(profile!["name"]),
                  style: const TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                  ),
                ),

                const SizedBox(height: 4),

                Text(
                  safeValue(profile!["email"]),
                  style: const TextStyle(
                    color: Colors.white70,
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 20),

          /// 🔥 INFO CARD
          Expanded(
            child: ListView(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              children: [
                profileCard([
                  profileTile(Icons.phone, "Phone",
                      safeValue(profile!["phone"])),
                  profileTile(Icons.phone_android, "Mobile",
                      safeValue(profile!["mobile"])),
                ]),

                const SizedBox(height: 12),

                profileCard([
                  profileTile(Icons.location_on, "Street",
                      safeValue(profile!["street"])),
                  profileTile(Icons.location_city, "City",
                      safeValue(profile!["city"])),
                ]),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// 🔥 CARD WRAPPER
Widget profileCard(List<Widget> children) {
  return Card(
    elevation: 3,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(16),
    ),
    child: Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(children: children),
    ),
  );
}

/// 🔥 TILE
Widget profileTile(IconData icon, String label, String value) {
  return ListTile(
    leading: CircleAvatar(
      backgroundColor: Colors.green.withOpacity(0.1),
      child: Icon(icon, color: Colors.green),
    ),
    title: Text(label),
    subtitle: Text(
      value,
      style: const TextStyle(fontWeight: FontWeight.w500),
    ),
  );
}




