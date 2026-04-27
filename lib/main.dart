import 'package:driver_app/services/sync_service.dart';
import 'package:flutter/material.dart';
import 'package:driver_app/theme/app_theme.dart';
import 'screens/splash_screen.dart';
import 'services/odoo_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final service = OdooService();
  await service.loadSession();   // 🔑 Load saved login

  /// Load saved login
  await service.loadSession();

  await SyncService.syncAll();

  /// Sync offline updates if internet is available
  await SyncService.syncPending();

  runApp(MyApp(service));


}

class MyApp extends StatelessWidget {
  final OdooService service;



  const MyApp(this.service, {super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: "Waste Driver",
      theme: AppTheme.theme,

      // Splash screen decides where to go
      home: SplashScreen(service: service),


    );
  }
}
