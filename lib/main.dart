  Future<void> _submitAgentTask() async {
    final goal = _agentTaskController.text.trim();
    if (goal.isEmpty || !_serverRunning || _agentToken.isEmpty) return;
    final client = HttpClient();
    final baseUri = Uri.parse('http://127.0.0.1:8080');
    setState(() => _agentTaskLog.insert(0, 'Planning: $goal'));

    Future<Map<String, dynamic>> requestJson(
      String method,
      String path, {
      Map<String, dynamic>? payload,
    }) async {
      final request = await client.openUrl(method, baseUri.resolve(path));
      request.headers.contentType = ContentType.json;
      request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $_agentToken');
      if (payload != null) {
        final encoded = jsonEncode(payload);
        request.contentLength = utf8.encode(encoded).length;
        request.write(encoded);
      }
      final response = await request.close().timeout(const Duration(minutes: 3));
      final body = await response.transform(utf8.decoder).join();
      dynamic decoded;
      try {
        decoded = body.isEmpty ? <String, dynamic>{} : jsonDecode(body);
      } catch (_) {
        decoded = <String, dynamic>{'raw': body};
      }
      return <String, dynamic>{'status': response.statusCode, 'body': decoded};
    }

    try {
      final planResponse = await requestJson(
        'POST',
        '/v1/agent/plan',
        payload: <String, dynamic>{'goal': goal},
      );
      final planStatus = planResponse['status'] as int;
      final planBody = planResponse['body'];
      if (planStatus != 200 || planBody is! Map) {
        throw StateError('Planner HTTP \${planStatus}: \${jsonEncode(planBody)}');
      }

      final plan = planBody['plan'];
      final steps = plan is Map ? plan['steps'] : null;
      if (steps is! List || steps.isEmpty) {
        throw StateError('Planner returned no executable steps');
      }

      final taskIds = <String>[];
      if (mounted) {
        setState(() {
          _agentCheck = 'Plan ready • \${steps.length} step(s)';
          _agentTaskLog.insert(0, 'Plan created: \${steps.length} step(s)');
        });
      }

      for (var index = 0; index < steps.length; index++) {
        final step = steps[index];
        if (step is! Map) throw StateError('Invalid plan step \${index + 1}');
        final action = step['action']?.toString() ?? '';
        final args = step['args'] is Map
            ? Map<String, dynamic>.from(step['args'] as Map)
            : <String, dynamic>{};
        if (action.isEmpty) {
          throw StateError('Plan step \${index + 1} has no action');
        }

        final taskId = 'task-\${DateTime.now().microsecondsSinceEpoch}-$index';
        final taskResponse = await requestJson(
          'POST',
          '/v1/agent/tasks',
          payload: <String, dynamic>{'id': taskId, 'action': action, 'args': args},
        );
        final taskStatus = taskResponse['status'] as int;
        if (taskStatus != 202) {
          throw StateError(
            'Queue HTTP \${taskStatus}: \${jsonEncode(taskResponse['body'])}',
          );
        }
        taskIds.add(taskId);
        if (mounted) {
          setState(() => _agentTaskLog.insert(
            0,
            'Queued \${index + 1}/\${steps.length}: $action',
          ));
        }
      }

      if (mounted) {
        setState(() => _agentCheck = 'Running • \${taskIds.length} task(s)');
      }

      final pending = taskIds.toSet();
      for (var attempt = 0; attempt < 40 && pending.isNotEmpty; attempt++) {
        await Future<void>.delayed(const Duration(milliseconds: 750));
        final resultsResponse = await requestJson('GET', '/v1/agent/tasks/results');
        if (resultsResponse['status'] != 200) continue;
        final body = resultsResponse['body'];
        final results = body is Map ? body['results'] : null;
        if (results is! List) continue;

        for (final item in results) {
          if (item is! Map) continue;
          final id = item['id']?.toString();
          if (id == null || !pending.remove(id)) continue;
          final ok = item['ok'] == true;
          final action = item['action']?.toString() ?? 'task';
          if (mounted) {
            setState(() => _agentTaskLog.insert(
              0,
              '\${ok ? 'Completed' : 'Failed'}: $action • '
              '\${jsonEncode(item['message'] ?? item['error'] ?? '')}',
            ));
          }
        }
      }

      if (mounted) {
        setState(() {
          _agentCheck = pending.isEmpty
              ? 'Completed • \${taskIds.length} task(s)'
              : 'Queued • waiting for Computer Agent';
          _agentTaskLog.insert(
            0,
            pending.isEmpty
                ? 'Goal completed: $goal'
                : 'Tasks remain queued on the phone.',
          );
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _agentCheck = 'Task failed: $error';
          _agentTaskLog.insert(0, 'Task failed: $error');
        });
      }
    } finally {
      client.close(force: true);
    }
  }