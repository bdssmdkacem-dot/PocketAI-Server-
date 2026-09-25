import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

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

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  static const _native = MethodChannel('pocketai/native');

  String _status = 'Checking native engine…';
  String _version = '—';
  String _runtime = '—';
  String _device = '—';
  bool _serverRunning = false;
  String _serverAddress = '127.0.0.1:8080';

  @override
  void initState() {
    super.initState();
    _checkNativeEngine();
  }

  Future<void> _checkNativeEngine() async {
    try {
      final result = await _native.invokeMethod<Map<dynamic, dynamic>>('status');
      if (!mounted) return;
      final device = result?['device'] as Map<dynamic, dynamic>?;
      final abis = (device?['supportedAbis'] as List<dynamic>?)?.join(', ') ?? 'Unknown';
      final ramBytes = device?['totalRamBytes'] as num?;
      final ramGb = ramBytes == null ? 'Unknown' : '${(ramBytes / 1073741824).toStringAsFixed(1)} GB';
      setState(() {
        _status = result?['status']?.toString() ?? 'Unknown';
        _version = result?['version']?.toString() ?? 'Unknown';
        _runtime = result?['runtime']?.toString() ?? 'Unknown';
        _device = '${device?['manufacturer'] ?? ''} ${device?['model'] ?? ''} • Android API ${device?['androidApi'] ?? '?'} • ABI $abis • RAM $ramGb';
        _serverRunning = result?['serverRunning'] == true;
        _serverAddress = '${result?['serverHost'] ?? '127.0.0.1'}:${result?['serverPort'] ?? 8080}';
      });
    } on PlatformException catch (error) {
      if (!mounted) return;
      setState(() {
        _status = 'Native error: ${error.message ?? error.code}';
        _version = 'Unavailable';
        _runtime = 'Unavailable';
        _device = 'Unavailable';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _status = 'Native error: $error';
        _version = 'Unavailable';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('PocketAI Server')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('LOCAL AI SERVER'),
                  const SizedBox(height: 12),
                  Text(_status == 'llama.cpp-linked' ? 'Native Ready' : _status, style: const TextStyle(fontSize: 30, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Text(_runtime),
                  const SizedBox(height: 8),
                  const Text('Flutter → MethodChannel → Kotlin → JNI → llama.cpp'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          InfoTile(title: 'Device', value: _device),
          InfoTile(title: 'llama.cpp', value: _status),
          InfoTile(title: 'Version', value: _version),
          const InfoTile(title: 'Model', value: 'No model loaded'),
          InfoTile(title: 'Server', value: _serverRunning ? 'Running • $_serverAddress' : 'Stopped'),
          InfoTile(title: 'API', value: 'http://$_serverAddress/v1'),
          const InfoTile(title: 'Native target', value: 'ABI selected by build configuration'),
          const SizedBox(height: 8),
          FilledButton.icon(onPressed: _checkNativeEngine, icon: const Icon(Icons.refresh), label: const Text('Refresh device & native status')),
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
  Widget build(BuildContext context) => Card(child: ListTile(title: Text(title), subtitle: Text(value)));
}