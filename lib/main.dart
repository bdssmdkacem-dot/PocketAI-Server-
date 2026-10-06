import 'package:flutter/material.dart';
import 'dart:convert';
import 'dart:io';

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
  String _lanAddress = 'Not available';
  String _agentToken = '';
  String _agentCheck = 'Not connected';
  String _serverError = '';
  bool _serverActionBusy = false;
  String _apiCheck = 'Not checked';
  String _modelsCheck = 'Not checked';
  String _modelName = 'No model loaded';
  bool _modelActionBusy = false;
  String _chatCheck = 'Not tested';
  bool _chatBusy = false;
  bool _benchmarkBusy = false;
  String _benchmarkCheck = 'Not run';
  int _desktopSection = 0;
  final TextEditingController _agentTaskController = TextEditingController();
  final FocusNode _agentTaskFocus = FocusNode();
  final List<String> _agentTaskLog = <String>[];
  String _warmupCheck = 'Not measured';

  Future<void> _submitAgentTask() async {
    final goal = _agentTaskController.text.trim();
    if (goal.isEmpty || !_serverRunning || _agentToken.isEmpty) return;
    setState(() => _agentTaskLog.insert(0, 'Planning: $goal'));
    final client = HttpClient();
    try {
      final request = await client.postUrl(Uri.parse('http://127.0.0.1:8080/v1/agent/plan'));
      final payload = jsonEncode({'goal': goal});
      request.headers.contentType = ContentType.json;
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $_agentToken');
      request.contentLength = utf8.encode(payload).length;
      request.write(payload);
      final response = await request.close().timeout(const Duration(minutes: 3));
      final body = await response.transform(utf8.decoder).join();
      if (!mounted) return;
      setState(() {
        _agentCheck = 'Task planned • HTTP ${response.statusCode}';
        _agentTaskLog.insert(0, 'Planner HTTP ${response.statusCode}: $body');
      });
    } catch (error) {
      if (mounted) {
        setState(() {
          _agentCheck = 'Task failed: $error';
          _agentTaskLog.insert(0, 'Task failed: $error);
        });
      }
    } finally {
      client.close(force: true);
    }
  }

  @override
  void dispose() {
    _agentTaskController.dispose();
    _agentTaskFocus.dispose();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    _checkNativeEngine();
  }

  Future<void> _startServer() async {
    if (_serverActionBusy) return;

    setState(() {
      _serverActionBusy = true;
      _serverError = '';
    });

    try {
      await _native.invokeMethod<Map<dynamic, dynamic>>('startServer');

      // Socket creation/bind now happens on Android's background thread.
      // Give it a short window to finish before reading the final server state.
      Map<dynamic, dynamic>? result;
      for (var attempt = 0; attempt < 50; attempt++) {
        await Future<void>.delayed(const Duration(milliseconds: 100));
        result = await _native.invokeMethod<Map<dynamic, dynamic>>('serverStatus');
        if (result?['running'] == true || (result?['error']?.toString() ?? '').isNotEmpty) {
          break;
        }
      }

      if (!mounted) return;
      setState(() {
        _serverRunning = result?['running'] == true;
        _lanAddress = '${result?['lanAddress'] ?? ''}:${result?['port'] ?? 8080}';
        _serverAddress = _lanAddress.startsWith(':') ? '127.0.0.1:${result?['port'] ?? 8080}' : _lanAddress;
        _agentToken = result?['agentToken']?.toString() ?? _agentToken;
        _agentCheck = result?['computerAgentConnected'] == true ? 'Computer Agent connected' : 'Waiting for Computer Agent';
        _serverError = result?['error']?.toString() ?? '';
      });

      await _checkNativeEngine();
      if (_serverRunning) {
        await _checkApi();
        await _checkModels();
      }
    } on PlatformException catch (error) {
      if (!mounted) return;
      setState(() {
        _serverError = error.message ?? error.code;
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _serverError = error.toString();
      });
    } finally {
      if (mounted) {
        setState(() {
          _serverActionBusy = false;
        });
      }
    }
  }

  Future<void> _checkApi() async {
    if (!_serverRunning) {
      setState(() => _apiCheck = 'Server is not running');
      return;
    }
    setState(() => _apiCheck = 'Checking /health…');
    final client = HttpClient();
    try {
      client.connectionTimeout = const Duration(seconds: 3);
      final request = await client.getUrl(Uri.parse('http://127.0.0.1:8080/health'));
      final response = await request.close().timeout(const Duration(seconds: 5));
      final body = await response.transform(utf8.decoder).join();
      if (!mounted) return;
      setState(() {
        _apiCheck = 'HTTP ${response.statusCode}: $body';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _apiCheck = 'API check failed: $error');
    } finally {
      client.close(force: true);
    }
  }

  Future<void> _checkModels() async {
    if (!_serverRunning) {
      setState(() => _modelsCheck = 'Server is not running');
      return;
    }
    setState(() => _modelsCheck = 'Checking /v1/models…');
    final client = HttpClient();
    try {
      client.connectionTimeout = const Duration(seconds: 3);
      final request = await client.getUrl(Uri.parse('http://127.0.0.1:8080/v1/models'));
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $_agentToken');
      final response = await request.close().timeout(const Duration(seconds: 5));
      final body = await response.transform(utf8.decoder).join();
      if (!mounted) return;
      setState(() {
        _modelsCheck = 'HTTP ${response.statusCode}: $body';
      });
    } catch (error) {
      if (!mounted) return;
      setState(() => _modelsCheck = 'API check failed: $error');
    } finally {
      client.close(force: true);
    }
  }

  Future<void> _importAndLoadModel() async {
    if (_modelActionBusy || !_serverRunning) return;
    setState(() { _modelActionBusy = true; _serverError = ''; });
    try {
      final picked = await _native.invokeMethod<Map<dynamic, dynamic>>('pickModel');
      if (!mounted) return;
      if (picked == null || picked['cancelled'] == true) return;
      final name = picked['name']?.toString() ?? '';
      if (name.isEmpty) throw StateError('No model was selected');
      final client = HttpClient();
      try {
        client.connectionTimeout = const Duration(seconds: 3);
        final request = await client.postUrl(Uri.parse('http://127.0.0.1:8080/v1/models/load'));
        final payload = jsonEncode({'model': name});
        request.headers.contentType = ContentType.json;
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $_agentToken');
        request.contentLength = utf8.encode(payload).length;
        request.write(payload);
        final response = await request.close().timeout(const Duration(minutes: 10));
        final body = await response.transform(utf8.decoder).join();
        if (response.statusCode < 200 || response.statusCode >= 300) throw StateError('HTTP ${response.statusCode}: $body');
      } finally { client.close(force: true); }
      final status = await _native.invokeMethod<Map<dynamic, dynamic>>('serverStatus');
      if (!mounted) return;
      setState(() { _modelName = status?['model']?.toString().isNotEmpty == true ? status!['model'].toString() : name; });
      await _checkModels();
    } catch (error) {
      if (!mounted) return;
      setState(() { _modelsCheck = 'Model load failed: $error'; });
    } finally {
      if (mounted) setState(() { _modelActionBusy = false; });
    }
  }
  Future<void> _testChat(String prompt) async {
    if (_chatBusy || !_serverRunning) return;
    setState(() => _chatBusy = true);
    final stopwatch = Stopwatch()..start();
    final client = HttpClient();
    try {
      client.connectionTimeout = const Duration(seconds: 3);
      final request = await client.postUrl(
        Uri.parse('http://127.0.0.1:8080/v1/chat/completions'),
      );
      final payload = jsonEncode({
        'messages': [
          {'role': 'user', 'content': prompt},
        ],
        'max_tokens': 64,
        'temperature': 0.7,
      });
      request.headers.contentType = ContentType.json;
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $_agentToken');
      request.contentLength = utf8.encode(payload).length;
      request.write(payload);
      final response = await request.close().timeout(const Duration(minutes: 5));
      final body = await response.transform(utf8.decoder).join();
      stopwatch.stop();
      if (!mounted) return;
      setState(() {
        _chatCheck =
            'HTTP ${response.statusCode} in ${stopwatch.elapsedMilliseconds} ms: $body';
      });
    } catch (error) {
      stopwatch.stop();
      if (!mounted) return;
      setState(() {
        _chatCheck =
            'Chat test failed after ${stopwatch.elapsedMilliseconds} ms: $error';
      });
    } finally {
      client.close(force: true);
      if (mounted) {
        setState(() => _chatBusy = false);
      }
    }
  }

  Future<void> _runInferenceBenchmark() async {
    if (_benchmarkBusy || !_serverRunning) return;
    setState(() {
      _benchmarkBusy = true;
      _benchmarkCheck = 'Running controlled English vs Arabic benchmark…';
    });

    final client = HttpClient();
    final results = <String>[];
    const englishPrompt = 'Answer with exactly six simple English words: what is AI?';
    const arabicPrompt = 'أجب بست كلمات عربية بسيطة بالضبط: ما هو الذكاء الاصطناعي؟';

    Future<void> runCase(String label, String prompt, int round) async {
      final stopwatch = Stopwatch()..start();
      final request = await client.postUrl(
        Uri.parse('http://127.0.0.1:8080/v1/chat/completions'),
      );
      final payload = jsonEncode({
        'messages': [
          {'role': 'user', 'content': prompt},
        ],
        'max_tokens': 16,
        'temperature': 0.0,
      });
      request.headers.contentType = ContentType.json;
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $_agentToken');
      request.contentLength = utf8.encode(payload).length;
      request.write(payload);
      final response = await request.close().timeout(const Duration(minutes: 3));
      final body = await response.transform(utf8.decoder).join();
      stopwatch.stop();

      try {
        final decoded = jsonDecode(body) as Map<String, dynamic>;
        final perf = decoded['pocketai_performance'] as Map<String, dynamic>?;
        if (perf != null) {
          results.add(
            '$label $round: HTTP ${response.statusCode} • '
            'prompt_tokens ${perf['prompt_tokens']} • '
            'generated ${perf['generated_tokens']} • '
            'prompt ${perf['prompt_decode_ms']} ms '
            '(${perf['prompt_tokens_per_sec']} tok/s) • '
            'generation ${perf['generation_ms']} ms '
            '(${perf['generation_tokens_per_sec']} tok/s) • '
            'native ${perf['total_native_ms']} ms',
          );
        } else {
          results.add('$label $round: HTTP ${response.statusCode} • no performance data');
        }
      } catch (_) {
        results.add('$label $round: HTTP ${response.statusCode} • ${stopwatch.elapsedMilliseconds} ms');
      }

      if (mounted) {
        setState(() {
          _benchmarkCheck = results.join('\\n');
          final last = results.isNotEmpty ? results.last : '';
          final match = RegExp(r'warmup ([^ ]+) ms').firstMatch(last);
          if (match != null) _warmupCheck = '${match.group(1)} ms';
        });
      }
    }

    try {
      client.connectionTimeout = const Duration(seconds: 3);
      for (var round = 1; round <= 3; round++) {
        await runCase('English', englishPrompt, round);
        await runCase('Arabic', arabicPrompt, round);
      }
    } catch (error) {
      if (mounted) {
        setState(() => _benchmarkCheck = 'Controlled benchmark failed: $error');
      }
    } finally {
      client.close(force: true);
      if (mounted) setState(() => _benchmarkBusy = false);
    }
  }

  Future<void> _queueComputerPing() async {
    if (!_serverRunning || _agentToken.isEmpty) return;
    final client = HttpClient();
    try {
      final request = await client.postUrl(Uri.parse('http://127.0.0.1:8080/v1/agent/tasks'));
      final payload = jsonEncode({'action': 'ping', 'args': {'message': 'Hello from PocketAI phone'}});
      request.headers.contentType = ContentType.json;
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $_agentToken');
      request.contentLength = utf8.encode(payload).length;
      request.write(payload);
      final response = await request.close().timeout(const Duration(seconds: 5));
      final body = await response.transform(utf8.decoder).join();
      if (!mounted) return;
      setState(() => _agentCheck = 'Ping task queued: HTTP ${response.statusCode} $body');
    } catch (error) {
      if (!mounted) return;
      setState(() => _agentCheck = 'Agent task failed: $error');
    } finally {
      client.close(force: true);
    }
  }

  Future<void> _planComputerTask() async {
    if (!_serverRunning || _agentToken.isEmpty) return;
    final goal = 'ابحث في الويب عن أحدث أخبار الذكاء الاصطناعي اليوم واقرأ أول نتيجة مفيدة.';
    final client = HttpClient();
    try {
      final request = await client.postUrl(Uri.parse('http://127.0.0.1:8080/v1/agent/plan'));
      final payload = jsonEncode({'goal': goal});
      request.headers.contentType = ContentType.json;
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $_agentToken');
      request.contentLength = utf8.encode(payload).length;
      request.write(payload);
      final response = await request.close().timeout(const Duration(minutes: 3));
      final body = await response.transform(utf8.decoder).join();
      if (!mounted) return;
      setState(() => _agentCheck = 'Planner HTTP ${response.statusCode}: $body');
    } catch (error) {
      if (!mounted) return;
      setState(() => _agentCheck = 'Planner failed: \$error');
    } finally {
      client.close(force: true);
    }
  }
  Future<void> _queueComputerBrowserTest() async {
    if (!_serverRunning || _agentToken.isEmpty) return;
    final client = HttpClient();
    try {
      final request = await client.postUrl(Uri.parse('http://127.0.0.1:8080/v1/agent/tasks'));
      final payload = jsonEncode({
        'action': 'browser.search',
        'args': {'query': 'PocketAI local computer agent'},
      });
      request.headers.contentType = ContentType.json;
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $_agentToken');
      request.contentLength = utf8.encode(payload).length;
      request.write(payload);
      final response = await request.close().timeout(const Duration(seconds: 5));
      final body = await response.transform(utf8.decoder).join();
      if (!mounted) return;
      setState(() => _agentCheck = 'Browser search queued: HTTP ${response.statusCode} $body');
    } catch (error) {
      if (!mounted) return;
      setState(() => _agentCheck = 'Browser task failed: $error');
    } finally {
      client.close(force: true);
    }
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
        _lanAddress = '${result?['lanAddress'] ?? ''}:${result?['serverPort'] ?? 8080}';
        _serverAddress = _lanAddress.startsWith(':') ? '127.0.0.1:${result?['serverPort'] ?? 8080}' : _lanAddress;
        _agentToken = result?['agentToken']?.toString() ?? _agentToken;
        _agentCheck = result?['computerAgentConnected'] == true ? 'Computer Agent connected' : 'Waiting for Computer Agent';
        _serverError = result?['serverError']?.toString() ?? '';
        _modelName = result?['model']?.toString().isNotEmpty == true ? result!['model'].toString() : 'No model loaded';
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
    final width = MediaQuery.sizeOf(context).width;
    final desktop = width >= 900;
    final maxWidth = desktop ? 1500.0 : double.infinity;

    final content = ListView(
      padding: EdgeInsets.all(desktop ? 28 : 20),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('LOCAL AI SERVER', style: TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              Text(_status == 'llama.cpp-linked' ? 'Native Ready' : _status,
                  style: const TextStyle(fontSize: 30, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              Text(_runtime),
              const SizedBox(height: 8),
              const Text('Flutter → MethodChannel → Kotlin → JNI → llama.cpp'),
              const SizedBox(height: 12),
              Wrap(spacing: 8, runSpacing: 8, children: [
                Chip(label: Text(_serverRunning ? 'Server running' : 'Server stopped')),
                Chip(label: Text(_agentCheck.contains('connected') ? 'Agent connected' : 'Agent waiting')),
              ]),
            ]),
          ),
        ),
        const SizedBox(height: 16),
        if (desktop)
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(child: _desktopServerColumn()),
            const SizedBox(width: 18),
            Expanded(child: _desktopAgentColumn()),
          ])
        else ...[
          InfoTile(title: 'Device', value: _device),
          InfoTile(title: 'llama.cpp', value: _status),
          InfoTile(title: 'Version', value: _version),
          InfoTile(title: 'Model', value: _modelName),
          _modelControls(),
          InfoTile(title: 'Server', value: _serverRunning ? 'Running • $_serverAddress' : 'Stopped'),
          _agentPanel(),
        ],
        if (desktop) ...[
          const SizedBox(height: 18),
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(child: _desktopAiColumn()),
            const SizedBox(width: 18),
            Expanded(child: _desktopDiagnosticsColumn()),
          ]),
        ] else ...[
          InfoTile(title: 'Health', value: _apiCheck),
          FilledButton.icon(onPressed: _serverRunning ? _checkApi : null,
              icon: const Icon(Icons.health_and_safety_outlined), label: const Text('Test /health')),
          InfoTile(title: 'Models API', value: _modelsCheck),
          FilledButton.icon(onPressed: _serverRunning ? _checkModels : null,
              icon: const Icon(Icons.view_list_outlined), label: const Text('Test /v1/models')),
          InfoTile(title: 'Chat completion', value: _chatCheck),
          FilledButton.icon(onPressed: _serverRunning && !_chatBusy ? () => _testChat('Hello, who are you?') : null,
              icon: const Icon(Icons.chat_outlined), label: const Text('Test English chat')),
          FilledButton.icon(onPressed: _serverRunning && !_chatBusy ? () => _testChat('من أنت؟ ما اسم النموذج الذي تعمل به؟ وهل تستطيع الإجابة باللغة العربية؟') : null,
              icon: const Icon(Icons.translate), label: const Text('Test Arabic chat')),
          InfoTile(title: 'Warm-up', value: _warmupCheck),
          InfoTile(title: 'Inference benchmark', value: _benchmarkCheck),
          FilledButton.icon(onPressed: _serverRunning && !_benchmarkBusy ? _runInferenceBenchmark : null,
              icon: _benchmarkBusy ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.speed),
              label: Text(_benchmarkBusy ? 'Benchmarking…' : 'Run English vs Arabic controlled benchmark')),
          const InfoTile(title: 'Native target', value: 'ABI selected by build configuration'),
          FilledButton.icon(onPressed: _checkNativeEngine,
              icon: const Icon(Icons.refresh), label: const Text('Refresh device & native status')),
        ],
      ],
    );

    final desktopWorkspace = CallbackShortcuts(
      bindings: <ShortcutActivator, VoidCallback>{
        const SingleActivator(LogicalKeyboardKey.digit1, control: true): () => setState(() => _desktopSection = 0),
        const SingleActivator(LogicalKeyboardKey.digit2, control: true): () => setState(() => _desktopSection = 1),
        const SingleActivator(LogicalKeyboardKey.digit3, control: true): () => setState(() => _desktopSection = 2),
        const SingleActivator(LogicalKeyboardKey.digit4, control: true): () => setState(() => _desktopSection = 3),
        const SingleActivator(LogicalKeyboardKey.keyL, control: true): () => _agentTaskFocus.requestFocus(),
      },
      child: Focus(
        autofocus: desktop,
        child: Row(children: [
          NavigationRail(
            selectedIndex: _desktopSection,
            labelType: NavigationRailLabelType.all,
            onDestinationSelected: (index) => setState(() => _desktopSection = index),
            destinations: const [
              NavigationRailDestination(icon: Icon(Icons.dashboard_outlined), label: Text('Dashboard')),
              NavigationRailDestination(icon: Icon(Icons.memory_outlined), label: Text('AI Engine')),
              NavigationRailDestination(icon: Icon(Icons.computer_outlined), label: Text('Computer Agent')),
              NavigationRailDestination(icon: Icon(Icons.monitor_heart_outlined), label: Text('Diagnostics')),
            ],
          ),
          const VerticalDivider(width: 1),
          Expanded(child: _desktopSectionContent()),
        ]),
      ),
    );

    return Scaffold(
      appBar: AppBar(
        title: Text(desktop ? 'PocketAI Command Center' : 'PocketAI Server'),
        actions: [
          if (desktop) ...[
            Chip(label: Text(_serverRunning ? 'Server ✓' : 'Server offline')),
            const SizedBox(width: 8),
            Chip(label: Text(_agentCheck.contains('connected') ? 'Agent ✓' : 'Agent waiting')),
            const SizedBox(width: 12),
          ],
          IconButton(tooltip: 'Refresh', onPressed: _checkNativeEngine, icon: const Icon(Icons.refresh)),
          const SizedBox(width: 8),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: desktop ? desktopWorkspace : content,
        ),
      ),
    );
  }

  Widget _desktopSectionContent() {
    switch (_desktopSection) {
      case 1:
        return ListView(padding: const EdgeInsets.all(28), children: [_desktopServerColumn(), const SizedBox(height: 18), _desktopAiColumn()]);
      case 2:
        return ListView(padding: const EdgeInsets.all(28), children: [_agentConsole(), const SizedBox(height: 18), _desktopAgentColumn()]);
      case 3:
        return ListView(padding: const EdgeInsets.all(28), children: [_desktopDiagnosticsColumn()]);
      default:
        return ListView(padding: const EdgeInsets.all(28), children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(child: _desktopServerColumn()),
            const SizedBox(width: 18),
            Expanded(child: _agentConsole()),
          ]),
          const SizedBox(height: 18),
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(child: _desktopAiColumn()),
            const SizedBox(width: 18),
            Expanded(child: _desktopDiagnosticsColumn()),
          ]),
        ]);
    }
  }

  Widget _agentConsole() => Card(
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.terminal),
          const SizedBox(width: 8),
          const Expanded(child: Text('AGENT TASK CONSOLE', style: TextStyle(fontWeight: FontWeight.bold))),
          Tooltip(message: 'Ctrl+L focuses the task field', child: IconButton(onPressed: () => _agentTaskFocus.requestFocus(), icon: const Icon(Icons.keyboard))),
        ]),
        const SizedBox(height: 6),
        const Text('Describe what you want the paired computer to do.'),
        const SizedBox(height: 12),
        TextField(
          controller: _agentTaskController,
          focusNode: _agentTaskFocus,
          minLines: 2,
          maxLines: 5,
          decoration: const InputDecoration(
            border: OutlineInputBorder(),
            hintText: 'Open the browser and search for the latest AI news…',
            prefixIcon: Icon(Icons.task_alt),
          ),
          onSubmitted: (_) => _submitAgentTask(),
        ),
        const SizedBox(height: 10),
        Wrap(spacing: 8, runSpacing: 8, children: [
          FilledButton.icon(
            onPressed: _serverRunning && _agentToken.isNotEmpty ? _submitAgentTask : null,
            icon: const Icon(Icons.play_arrow),
            label: const Text('Run task'),
          ),
          OutlinedButton.icon(
            onPressed: () {
              _agentTaskController.clear();
              _agentTaskFocus.requestFocus();
            },
            icon: const Icon(Icons.clear),
            label: const Text('Clear'),
          ),
          Chip(label: Text(_agentCheck)),
        ]),
        const SizedBox(height: 14),
        const Divider(),
        const Text('TASK LOG', style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 6),
        if (_agentTaskLog.isEmpty)
          const Text('No tasks yet. Connect the Computer Agent to begin.')
        else
          ..._agentTaskLog.map((entry) => MouseRegion(
            cursor: SystemMouseCursors.click,
            child: GestureDetector(
              onSecondaryTap: () => showMenu<String>(
                context: context,
                position: const RelativeRect.fromLTRB(120, 120, 120, 120),
                items: const [PopupMenuItem(value: 'dismiss', child: Text('Task log entry'))],
              ),
              child: ListTile(
                dense: true,
                leading: const Icon(Icons.chevron_right),
                title: Text(entry),
              ),
            ),
          )),
        const SizedBox(height: 8),
        const Text('Ctrl+1 Dashboard • Ctrl+2 AI • Ctrl+3 Agent • Ctrl+4 Diagnostics • Ctrl+L task field • Ctrl+Enter submit'),
      ]),
    ),
  );


  Widget _modelControls() => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    FilledButton.icon(
      onPressed: _serverRunning && !_modelActionBusy ? _importAndLoadModel : null,
      icon: _modelActionBusy ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.folder_open),
      label: Text(_modelActionBusy ? 'Importing / loading model…' : 'Select & load GGUF model'),
    ),
    FilledButton.icon(
      onPressed: _serverActionBusy ? null : _startServer,
      icon: _serverActionBusy ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.play_arrow),
      label: Text(_serverRunning ? 'Restart / verify server' : 'Start / retry server'),
    ),
  ]);

  Widget _desktopServerColumn() => Card(
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('AI ENGINE', style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        InfoTile(title: 'Device', value: _device),
        InfoTile(title: 'llama.cpp', value: _status),
        InfoTile(title: 'Version', value: _version),
        InfoTile(title: 'Model', value: _modelName),
        _modelControls(),
        InfoTile(title: 'Server', value: _serverRunning ? 'Running • $_serverAddress' : 'Stopped'),
        InfoTile(title: 'API', value: 'http://$_serverAddress/v1'),
      ]),
    ),
  );

  Widget _desktopAgentColumn() => _agentPanel();

  Widget _agentPanel() => Card(
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('COMPUTER AGENT', style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        InfoTile(title: 'LAN address', value: _lanAddress),
        InfoTile(title: 'Agent connection', value: _agentCheck),
        InfoTile(title: 'Pairing token', value: _agentToken.isEmpty ? 'Not available' : _agentToken),
        const Text('The phone is the local AI brain; the paired computer executes approved tasks over LAN.'),
        const SizedBox(height: 10),
        Wrap(spacing: 8, runSpacing: 8, children: [
          FilledButton.icon(onPressed: _serverRunning && _agentToken.isNotEmpty ? _queueComputerPing : null,
              icon: const Icon(Icons.computer), label: const Text('Ping')),
          FilledButton.icon(onPressed: _serverRunning && _agentToken.isNotEmpty ? _queueComputerBrowserTest : null,
              icon: const Icon(Icons.language), label: const Text('Browser search')),
          FilledButton.icon(onPressed: _serverRunning && _agentToken.isNotEmpty ? _planComputerTask : null,
              icon: const Icon(Icons.auto_awesome), label: const Text('Plan task')),
          OutlinedButton.icon(onPressed: _checkNativeEngine,
              icon: const Icon(Icons.sync), label: const Text('Refresh')),
        ]),
      ]),
    ),
  );

  Widget _desktopAiColumn() => Card(
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('AI PLAYGROUND', style: TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        InfoTile(title: 'Chat completion', value: _chatCheck),
        Wrap(spacing: 8, runSpacing: 8, children: [
          FilledButton.icon(onPressed: _serverRunning && !_chatBusy ? () => _testChat('Hello, who are you?') : null,
              icon: const Icon(Icons.chat_outlined), label: const Text('English')),
          FilledButton.icon(onPressed: _serverRunning && !_chatBusy ? () => _testChat('من أنت؟ ما اسم النموذج الذي تعمل به؟ وهل تستطيع الإجابة باللغة العربية؟') : null,
              icon: const Icon(Icons.translate), label: const Text('Arabic')),
        ]),
        const SizedBox(height: 18),
        const Divider(),
        const SizedBox(height: 8),
        const Text('BENCHMARK', style: TextStyle(fontWeight: FontWeight.bold)),
        InfoTile(title: 'Warm-up', value: _warmupCheck),
        InfoTile(title: 'Inference', value: _benchmarkCheck),
        FilledButton.icon(onPressed: _serverRunning && !_benchmarkBusy ? _runInferenceBenchmark : null,
            icon: _benchmarkBusy ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.speed),
            label: Text(_benchmarkBusy ? 'Benchmarking…' : 'Run benchmark')),
      ]),
    ),
  );

  Widget _desktopDiagnosticsColumn() => Card(
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('DIAGNOSTICS', style: TextStyle(fontWeight: FontWeight.bold)),
        InfoTile(title: 'Health', value: _apiCheck),
        InfoTile(title: 'Models API', value: _modelsCheck),
        if (_serverError.isNotEmpty) InfoTile(title: 'Server error', value: _serverError),
        FilledButton.icon(onPressed: _serverRunning ? _checkApi : null,
            icon: const Icon(Icons.health_and_safety_outlined), label: const Text('Test health')),
        FilledButton.icon(onPressed: _serverRunning ? _checkModels : null,
            icon: const Icon(Icons.view_list_outlined), label: const Text('Test models')),
        const InfoTile(title: 'Native target', value: 'ABI selected by build configuration'),
      ]),
    ),
  );

}

class InfoTile extends StatelessWidget {
  const InfoTile({super.key, required this.title, required this.value});
  final String title;
  final String value;

  @override
  Widget build(BuildContext context) => Card(
        child: ListTile(title: Text(title), subtitle: Text(value)),
      );
}