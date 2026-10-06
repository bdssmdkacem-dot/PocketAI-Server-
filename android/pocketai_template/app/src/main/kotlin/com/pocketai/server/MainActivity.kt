package com.pocketai.server

import android.app.ActivityManager
import android.content.Intent
import android.net.Uri
import android.content.Context
import android.content.SharedPreferences
import android.os.Build
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.ByteArrayOutputStream
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketException
import java.net.BindException
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.security.SecureRandom
import android.util.Base64
import java.util.concurrent.Executors
import java.util.concurrent.ConcurrentLinkedQueue

class MainActivity : FlutterActivity() {
    private val channelName = "pocketai/native"
    private lateinit var nativeAi: NativeAi
    private var server: LocalAiServer? = null
    private var nativeInitError: String? = null
    private var serverInitError: String? = null
    private var pendingModelPicker: MethodChannel.Result? = null
    private val modelPickerRequestCode = 1001
    private val executorForModelImport = Executors.newSingleThreadExecutor()
    private val prefs: SharedPreferences by lazy { getSharedPreferences("pocketai_agent", Context.MODE_PRIVATE) }
    private var agentToken: String = ""

    private fun getAgentToken(): String {
        if (agentToken.isNotBlank()) return agentToken
        agentToken = prefs.getString("token", "") ?: ""
        if (agentToken.isBlank()) {
            val bytes = ByteArray(32)
            SecureRandom().nextBytes(bytes)
            agentToken = Base64.encodeToString(bytes, Base64.NO_WRAP or Base64.NO_PADDING or Base64.URL_SAFE)
            prefs.edit().putString("token", agentToken).apply()
        }
        return agentToken
    }

    private fun lanIpv4Address(): String {
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val networkInterface = interfaces.nextElement()
                if (!networkInterface.isUp || networkInterface.isLoopback) continue
                val addresses = networkInterface.inetAddresses
                while (addresses.hasMoreElements()) {
                    val address = addresses.nextElement()
                    val host = address.hostAddress ?: continue
                    if (!address.isLoopbackAddress && !host.contains(":")) return host
                }
            }
        } catch (_: Throwable) {}
        return ""
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        try {
            nativeAi = NativeAi()
        } catch (t: Throwable) {
            nativeInitError = "${t.javaClass.simpleName}: ${t.message ?: "native library initialization failed"}"
        }
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "status" -> result.success(statusMap())
                    "startServer" -> {
                        ensureServer()
                        result.success(serverStatus())
                    }
                    "stopServer" -> {
                        server?.stop()
                        server = null
                        result.success(serverStatus())
                    }
                    "serverStatus" -> result.success(serverStatus())
                    "pickModel" -> pickModel(result)
                    else -> result.notImplemented()
                }
            }

        // Start the local OpenAI-compatible API as soon as the Android activity
        // is initialized. The server must not depend on a Flutter UI action.
        ensureServer()
    }

    private fun ensureServer() {
        if (nativeInitError != null || server?.isRunning() == true || server?.isStarting() == true) return
        try {
            server?.stop()
        } catch (_: Throwable) {}
        server = null
        try {
            server = LocalAiServer(filesDir, nativeAi, getAgentToken()).also { it.start() }
            serverInitError = null
        } catch (t: Throwable) {
            serverInitError = "${t.javaClass.simpleName}: ${t.message ?: "server initialization failed"}"
        }
    }

    private fun statusMap(): Map<String, Any> {
        ensureServer()
        val ai = if (nativeInitError == null) nativeAi else null
        return mapOf(
            "ready" to (ai?.isReady() ?: false),
            "status" to (nativeInitError ?: ai?.status().orEmpty()),
            "version" to (if (ai == null) "Unavailable" else ai.version()),
            "runtime" to (nativeInitError ?: ai?.runtimeCheck().orEmpty()),
            "modelLoaded" to (ai?.isModelLoaded() ?: false),
            "model" to (ai?.loadedModelName().orEmpty()),
            "device" to deviceCapabilities(),
            "serverRunning" to (server?.isRunning() == true),
            "serverHost" to (server?.host ?: "127.0.0.1"),
            "serverPort" to 8080,
            "lanAddress" to lanIpv4Address(),
            "agentToken" to getAgentToken(),
            "computerAgentConnected" to (server?.computerAgentConnected() == true),
            "serverError" to (serverInitError ?: server?.error().orEmpty()),
        )
    }

    private fun serverStatus(): Map<String, Any> {
        val ai = if (nativeInitError == null) nativeAi else null
        return mapOf(
            "running" to (server?.isRunning() == true),
            "host" to (server?.host ?: "127.0.0.1"),
            "port" to (server?.port ?: 8080),
            "lanAddress" to lanIpv4Address(),
            "agentToken" to getAgentToken(),
            "computerAgentConnected" to (server?.computerAgentConnected() == true),
            "modelLoaded" to (ai?.isModelLoaded() ?: false),
            "model" to (ai?.loadedModelName().orEmpty()),
            "error" to (nativeInitError ?: serverInitError ?: server?.error().orEmpty()),
        )
    }

    private fun deviceCapabilities(): Map<String, Any> {
        val memoryInfo = ActivityManager.MemoryInfo()
        val activityManager = getSystemService(ACTIVITY_SERVICE) as ActivityManager
        activityManager.getMemoryInfo(memoryInfo)
        return mapOf(
            "manufacturer" to Build.MANUFACTURER,
            "model" to Build.MODEL,
            "androidApi" to Build.VERSION.SDK_INT,
            "supportedAbis" to Build.SUPPORTED_ABIS.toList(),
            "cpuCores" to Runtime.getRuntime().availableProcessors(),
            "totalRamBytes" to memoryInfo.totalMem,
            "availableRamBytes" to memoryInfo.availMem,
            "lowMemory" to memoryInfo.lowMemory,
        )
    }

    private fun pickModel(result: MethodChannel.Result) {
        if (pendingModelPicker != null) {
            result.error("PICKER_BUSY", "A model picker is already open", null)
            return
        }
        pendingModelPicker = result
        try {
            val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = "*/*"
                putExtra(Intent.EXTRA_MIME_TYPES, arrayOf("application/octet-stream", "application/x-gguf", "*/*"))
            }
            startActivityForResult(intent, modelPickerRequestCode)
        } catch (t: Throwable) {
            pendingModelPicker = null
            result.error("PICKER_FAILED", t.message ?: "Unable to open model picker", null)
        }
    }

    @Suppress("DEPRECATION")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != modelPickerRequestCode) return
        val result = pendingModelPicker
        pendingModelPicker = null
        if (result == null) return

        if (resultCode != RESULT_OK || data?.data == null) {
            result.success(mapOf("cancelled" to true))
            return
        }

        val uri: Uri = data.data!!
        executorForModelImport.execute {
            try {
                val name = queryDisplayName(uri)
                if (name.isBlank() || !name.endsWith(".gguf", true) ||
                    name.contains("/") || name.contains("\\") || name.contains("..")) {
                    runOnUiThread { result.error("INVALID_MODEL", "Please select a .gguf model file", null) }
                    return@execute
                }

                val modelsDir = java.io.File(filesDir, "models").apply { mkdirs() }
                val target = java.io.File(modelsDir, name)
                contentResolver.openInputStream(uri).use { input ->
                    if (input == null) throw IllegalStateException("Cannot open selected model")
                    target.outputStream().use { output -> input.copyTo(output) }
                }
                runOnUiThread {
                    result.success(mapOf(
                        "cancelled" to false,
                        "name" to name,
                        "path" to target.absolutePath,
                        "sizeBytes" to target.length()
                    ))
                }
            } catch (t: Throwable) {
                runOnUiThread { result.error("MODEL_IMPORT_FAILED", t.message ?: "Failed to import model", null) }
            }
        }
    }

    private fun queryDisplayName(uri: Uri): String {
        val projection = arrayOf("_display_name")
        contentResolver.query(uri, projection, null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) {
                val index = cursor.getColumnIndex("_display_name")
                if (index >= 0) return cursor.getString(index) ?: ""
            }
        }
        return uri.lastPathSegment?.substringAfterLast('/') ?: ""
    }

    override fun onDestroy() {
        server?.stop()
        server = null
        executorForModelImport.shutdownNow()
        if (nativeInitError == null) {
            try { nativeAi.unloadModel() } catch (_: Throwable) {}
        }
        super.onDestroy()
    }
}

private class LocalAiServer(
    private val filesDir: java.io.File,
    private val nativeAi: NativeAi,
    private val authToken: String,
) {
    val port = 8080
    val host = "0.0.0.0"
    private val executor = Executors.newCachedThreadPool()
    @Volatile private var running = false
    private var socket: ServerSocket? = null

    @Volatile private var starting = false
    @Volatile private var startupError: String? = null
    @Volatile private var lastAgentHeartbeatMs: Long = 0L
    private val taskQueue = ConcurrentLinkedQueue<JSONObject>()
    private val completedTasks = ConcurrentLinkedQueue<JSONObject>()

    fun start() {
        if (running || starting) return
        java.io.File(filesDir, "models").mkdirs()
        startupError = null
        starting = true

        // All socket creation/bind/accept work runs off Android's main thread.
        // This is required on Android because network operations on the UI thread
        // can raise NetworkOnMainThreadException.
        executor.execute {
            try {
                val address = InetSocketAddress(java.net.InetAddress.getByName("0.0.0.0"), port)
                val boundSocket = ServerSocket()
                boundSocket.reuseAddress = true
                boundSocket.bind(address, 32)
                socket = boundSocket
                running = true

                while (running) {
                    try {
                        val client = socket?.accept() ?: break
                        executor.execute { handle(client) }
                    } catch (_: SocketException) {
                        if (running) break
                    }
                }
            } catch (e: BindException) {
                startupError = "cannot bind LAN server to 0.0.0.0:$port: BindException: ${e.message ?: "bind rejected"}"
            } catch (e: SecurityException) {
                startupError = "cannot bind LAN server to 0.0.0.0:$port: SecurityException: ${e.message ?: "operation not permitted"}"
            } catch (e: SocketException) {
                startupError = "cannot bind LAN server to 0.0.0.0:$port: SocketException: ${e.message ?: "socket operation failed"}"
            } catch (e: Throwable) {
                startupError = "cannot start LAN server on 0.0.0.0:$port: ${e.javaClass.simpleName}: ${e.message ?: "server startup failed"}"
            } finally {
                starting = false
                if (!running) {
                    try { socket?.close() } catch (_: Exception) {}
                    socket = null
                }
            }
        }
    }

    fun stop() {
        running = false
        try { socket?.close() } catch (_: Exception) {}
        socket = null
        executor.shutdownNow()
    }

    fun isRunning() = running
    fun isStarting() = starting
    fun error() = startupError ?: ""

    private fun handle(client: Socket) {
        client.use { c ->
            c.soTimeout = 120_000
            val input = BufferedInputStream(c.getInputStream())
            val requestLine = readHttpLine(input) ?: return
            val parts = requestLine.split(" ")
            if (parts.size < 2) return
            val method = parts[0]
            val path = parts[1]
            var contentLength = 0
            var authorization: String? = null
            while (true) {
                val line = readHttpLine(input) ?: return
                if (line.isEmpty()) break
                if (line.startsWith("Content-Length:", true)) {
                    contentLength = line.substringAfter(":").trim().toIntOrNull() ?: 0
                }
                if (line.startsWith("Authorization:", true)) {
                    authorization = line.substringAfter(":").trim()
                }
            }
            if (contentLength < 0 || contentLength > 10 * 1024 * 1024) return
            if (!isAuthorized(path, authorization)) {
                val payload = JSONObject().put("error", "unauthorized").toString()
                val bytes = payload.toByteArray(Charsets.UTF_8)
                val response = "HTTP/1.1 401 Unauthorized\\r\\n" +
                    "Content-Type: application/json; charset=utf-8\\r\\n" +
                    "Content-Length: " + bytes.size + "\\r\\n" +
                    "Connection: close\\r\\n\\r\\n"
                val out = c.getOutputStream()
                out.write(response.toByteArray(Charsets.US_ASCII))
                out.write(bytes)
                out.flush()
                return
            }
            val bodyBytes = ByteArray(contentLength)
            var read = 0
            while (read < contentLength) {
                val n = input.read(bodyBytes, read, contentLength - read)
                if (n <= 0) return
                read += n
            }
            val (status, payload) = route(method, path, bodyBytes.toString(Charsets.UTF_8))
            val bytes = payload.toByteArray(Charsets.UTF_8)
            val response = "HTTP/1.1 " + status + "\r\n" +
                "Content-Type: application/json; charset=utf-8\r\n" +
                "Content-Length: " + bytes.size + "\r\n" +
                "Connection: close\r\n\r\n"
            val out = c.getOutputStream()
            out.write(response.toByteArray(Charsets.US_ASCII))
            out.write(bytes)
            out.flush()
        }
    }

    private fun readHttpLine(input: BufferedInputStream): String? {
        val bytes = ByteArrayOutputStream()
        while (true) {
            val b = input.read()
            if (b < 0) return if (bytes.size() == 0) null else bytes.toString(Charsets.US_ASCII.name())
            if (b == '\n'.code) {
                val data = bytes.toByteArray()
                val length = if (data.isNotEmpty() && data.last() == '\r'.code.toByte()) data.size - 1 else data.size
                return String(data, 0, length, Charsets.US_ASCII)
            }
            bytes.write(b)
            if (bytes.size() > 16 * 1024) return null
        }
    }

    fun computerAgentConnected(): Boolean =
        lastAgentHeartbeatMs > 0L && System.currentTimeMillis() - lastAgentHeartbeatMs < 10_000L

    private fun isAuthorized(path: String, authHeader: String?): Boolean {
        if (path == "/health") return true
        return authHeader == "Bearer " + authToken
    }

    private fun jsonError(status: String, message: String): Pair<String, String> =
        status to JSONObject().put("error", message).toString()

    private fun route(method: String, path: String, body: String): Pair<String, String> {
        if (method == "GET" && path == "/health") {
            return "200 OK" to JSONObject()
                .put("status", "ok")
                .put("native_ready", nativeAi.isReady())
                .put("model_loaded", nativeAi.isModelLoaded())
                .toString()
        }

        if (method == "GET" && path == "/v1/models") {
            val data = JSONArray()
            if (nativeAi.isModelLoaded()) {
                data.put(JSONObject()
                    .put("id", nativeAi.loadedModelName())
                    .put("object", "model")
                    .put("owned_by", "pocketai"))
            }
            return "200 OK" to JSONObject().put("object", "list").put("data", data).toString()
        }

        if (method == "POST" && path == "/v1/models/load") {
            return try {
                val name = JSONObject(body).optString("model").trim()
                val valid = name.isNotBlank() && name.endsWith(".gguf", true) &&
                    !name.contains("/") && !name.contains("\\") && !name.contains("..")
                if (!valid) {
                    "400 Bad Request" to JSONObject().put("error", "model must be a GGUF filename").toString()
                } else {
                    val file = java.io.File(java.io.File(filesDir, "models"), name)
                    when {
                        !file.isFile -> "404 Not Found" to JSONObject().put("error", "model file not found in files/models").toString()
                        nativeAi.loadModel(file.absolutePath) -> "200 OK" to JSONObject().put("model", name).put("loaded", true).toString()
                        else -> "500 Internal Server Error" to JSONObject().put("error", "failed to load model").toString()
                    }
                }
            } catch (e: Exception) {
                "400 Bad Request" to JSONObject().put("error", e.message ?: "invalid request").toString()
            }
        }

        if (path == "/v1/agent/hello" && method == "GET") {
            lastAgentHeartbeatMs = System.currentTimeMillis()
            return "200 OK" to JSONObject()
                .put("name", "PocketAI Computer Agent")
                .put("protocol", "pocketai-agent-v1")
                .put("phone_llm", "llama.cpp")
                .put("capabilities", JSONArray()
                    .put("task.poll")
                    .put("task.result")
                    .put("ping")
                    .put("browser.open")
                    .put("browser.search")
                    .put("browser.read")
                    .put("browser.click")
                    .put("browser.type")
                    .put("browser.scroll")
                    .put("browser.back")
                    .put("browser.forward")
                    .put("browser.screenshot")
                    .put("browser.close"))
                .toString()
        }

        if (path == "/v1/agent/tasks" && method == "POST") {
            return try {
                val request = JSONObject(body)
                val id = request.optString("id").ifBlank { "task-" + System.currentTimeMillis() }
                val action = request.optString("action").ifBlank { "ping" }
                val args = request.optJSONObject("args") ?: JSONObject()
                taskQueue.add(JSONObject()
                    .put("id", id)
                    .put("action", action)
                    .put("args", args)
                    .put("created_at", System.currentTimeMillis()))
                "202 Accepted" to JSONObject().put("id", id).put("queued", true).toString()
            } catch (e: Exception) {
                jsonError("400 Bad Request", e.message ?: "invalid task")
            }
        }

        if (path == "/v1/agent/tasks/next" && method == "GET") {
            lastAgentHeartbeatMs = System.currentTimeMillis()
            val task = taskQueue.poll()
            return if (task == null) {
                "204 No Content" to ""
            } else {
                "200 OK" to task.toString()
            }
        }

        if (path == "/v1/agent/tasks/result" && method == "POST") {
            return try {
                val result = JSONObject(body)
                result.put("received_at", System.currentTimeMillis())
                completedTasks.add(result)
                lastAgentHeartbeatMs = System.currentTimeMillis()
                "200 OK" to JSONObject().put("accepted", true).put("task_id", result.optString("id")).toString()
            } catch (e: Exception) {
                jsonError("400 Bad Request", e.message ?: "invalid result")
            }
        }

        if (path == "/v1/agent/tasks/results" && method == "GET") {
            val results = JSONArray()
            while (true) {
                val result = completedTasks.poll() ?: break
                results.put(result)
            }
            return "200 OK" to JSONObject().put("results", results).toString()
        }


        if (method == "POST" && path == "/v1/agent/plan") {
            return try {
                if (!nativeAi.isModelLoaded()) {
                    "409 Conflict" to JSONObject().put("error", "no model loaded").toString()
                } else {
                    val goal = JSONObject(body).optString("goal").trim()
                    if (goal.isBlank()) {
                        "400 Bad Request" to JSONObject().put("error", "goal is required").toString()
                    } else {
                        val plannerPrompt = "You are PocketAI browser task planner. Convert the user goal into a short JSON plan. Allowed actions only: browser.search, browser.open, browser.read, browser.click, browser.type, browser.scroll, browser.back, browser.forward, browser.screenshot. Return ONLY valid JSON: {\"steps\":[{\"action\":\"browser.search\",\"args\":{\"query\":\"...\"}}]}. Maximum 8 steps. Do not invent selectors unless explicitly provided. User goal: " + goal
                        val response = nativeAi.generate(plannerPrompt, 256, 0.0f)
                        if (response.startsWith("ERROR:")) {
                            "500 Internal Server Error" to JSONObject().put("error", response).toString()
                        } else {
                            val jsonText = response.replace("```json", "").replace("```", "").trim()
                            val parsed = JSONObject(jsonText)
                            val steps = parsed.optJSONArray("steps") ?: JSONArray()
                            if (steps.length() > 8) {
                                "400 Bad Request" to JSONObject().put("error", "plan exceeds maximum of 8 steps").toString()
                            } else {
                                var valid = true
                                val allowed = setOf("browser.search","browser.open","browser.read","browser.click","browser.type","browser.scroll","browser.back","browser.forward","browser.screenshot")
                                for (i in 0 until steps.length()) {
                                    val action = steps.optJSONObject(i)?.optString("action").orEmpty()
                                    if (!allowed.contains(action)) { valid = false; break }
                                }
                                if (!valid) "400 Bad Request" to JSONObject().put("error", "plan contains an unsupported browser action").toString()
                                else "200 OK" to JSONObject().put("goal", goal).put("plan", parsed).toString()
                            }
                        }
                    }
                }
            } catch (e: Exception) {
                "400 Bad Request" to JSONObject().put("error", "invalid planner output: ${e.message ?: "unknown"}").toString()
            }
        }
        if (method == "POST" && path == "/v1/chat/completions") {
            return try {
                if (!nativeAi.isModelLoaded()) {
                    "409 Conflict" to JSONObject().put("error", "no model loaded").toString()
                } else {
                    val json = JSONObject(body)
                    var prompt = json.optString("prompt")
                    if (prompt.isBlank()) {
                        val messages = json.optJSONArray("messages")
                        if (messages != null && messages.length() > 0) {
                            prompt = messages.getJSONObject(messages.length() - 1).optString("content")
                        }
                    }
                    if (prompt.isBlank()) {
                        "400 Bad Request" to JSONObject().put("error", "prompt or messages is required").toString()
                    } else {
                        val maxTokens = json.optInt("max_tokens", 128).coerceIn(1, 512)
                        val temperature = json.optDouble("temperature", 0.7).toFloat().coerceIn(0.0f, 2.0f)
                        val response = nativeAi.generate(prompt, maxTokens, temperature)
                        val performance = try { JSONObject(nativeAi.lastInferenceStats()) } catch (_: Throwable) { JSONObject() }
                        if (response.startsWith("ERROR:")) {
                            "500 Internal Server Error" to JSONObject().put("error", response).toString()
                        } else {
                            val choice = JSONObject()
                                .put("index", 0)
                                .put("message", JSONObject().put("role", "assistant").put("content", response))
                                .put("finish_reason", "stop")
                            "200 OK" to JSONObject()
                                .put("id", "chatcmpl-pocketai-" + System.currentTimeMillis())
                                .put("object", "chat.completion")
                                .put("model", nativeAi.loadedModelName())
                                .put("pocketai_performance", performance)
                                .put("choices", JSONArray().put(choice))
                                .toString()
                        }
                    }
                }
            } catch (e: Exception) {
                "500 Internal Server Error" to JSONObject().put("error", e.message ?: "generation failed").toString()
            }
        }

        return "404 Not Found" to JSONObject().put("error", "not found").toString()
    }
}
