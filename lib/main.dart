import 'package:flutter/material.dart';

void main() => runApp(const PocketAiApp());

class PocketAiApp extends StatelessWidget {
  const PocketAiApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PocketAI Server',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        colorSchemeSeed: Colors.amber,
        useMaterial3: true,
      ),
      home: const DashboardPage(),
    );
  }
}

class DashboardPage extends StatelessWidget {
  const DashboardPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('PocketAI Server')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: const [
          Card(
            child: Padding(
              padding: EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('LOCAL AI SERVER'),
                  SizedBox(height: 12),
                  Text('Ready', style: TextStyle(fontSize: 30, fontWeight: FontWeight.bold)),
                  SizedBox(height: 8),
                  Text('Native inference and LAN API initialization boundary.'),
                ],
              ),
            ),
          ),
          SizedBox(height: 16),
          InfoTile(title: 'Model', value: 'No model loaded'),
          InfoTile(title: 'Server', value: 'Stopped'),
          InfoTile(title: 'API', value: 'http://0.0.0.0:8080/v1'),
          InfoTile(title: 'Target', value: 'Android arm64-v8a'),
        ],
      ),
    );
  }
}

class InfoTile extends StatelessWidget {
  const InfoTile({super.key, required this.title, required this.value});
  final String title;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Card(child: ListTile(title: Text(title), subtitle: Text(value)));
  }
}
