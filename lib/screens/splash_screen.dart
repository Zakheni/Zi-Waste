import 'dart:async';
import 'package:flutter/material.dart';
import '../services/odoo_service.dart';
import 'home_page.dart';
import 'login_page.dart';
import 'worksheet_list_page.dart';

class SplashScreen extends StatefulWidget {

  final OdooService service;

  const SplashScreen({super.key, required this.service});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {

  @override
  void initState() {
    super.initState();

    Timer(const Duration(seconds: 6), () {

      if (widget.service.sessionId != null) {

        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => const HomePage(),
          ),
        );

      } else {

        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => const LoginPage(),
          ),
        );

      }

    });
  }

  @override
  Widget build(BuildContext context) {

    return Scaffold(
      backgroundColor: const Color(0xFF1FAF5B),

      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,

          children: [

            Image.asset(
              "assets/images/icon.png",
              width: 200,
            ),

            const SizedBox(height: 30),

            const CircularProgressIndicator(
              color: Colors.white,
            ),
          ],
        ),
      ),
    );
  }
}