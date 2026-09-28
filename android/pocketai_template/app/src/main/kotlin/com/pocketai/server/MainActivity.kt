package com.pocketai.server

import android.app.ActivityManager
import android.content.Intent
import android.net.Uri
import android.os.Build
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketException
import java.net.BindException
import java.net.InetSocketAddress
import java.util.concurrent.Executors

class MainActivity : FlutterActivity() {
    private val channelName = "pocketai/native"
    private lateinit var nativeAi: NativeAi
    private var server: LocalAiServer? = null
    private var nativeInitError: String? = null
    private var serverInitError: String? = null
    private var pendingModelPicker: MethodChannel.Result? = null
    private val modelPickerRequestCode = 1001
    private val executorForModelImport = Executors.newSingleThreadExecutor()

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
            server = LocalAiServer(filesDir, nativeAi).also { it.start() }
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
            "serverHost" to "127.0.0.1",
            "serverPort" to 8080,
            "serverError" to (serverInitError ?: server?.error().orEmpty()),
        )
    }

    private fun serverStatus(): Map<String, Any> {
        val ai = if (nativeInitError == null) nativeAi else null
        return mapOf(
            "running" to (server?.isRunning() == true),
            "host" to "127.0.0.1",
            "port" to (server?.port ?: 8080),
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
) {
    val port = 8080
    private val executor = Executors.newCachedThreadPool()
    @Volatile private var running = false
    private var socket: ServerSocket? = null

    @Volatile private var starting = false
    @Volatile private var startupError: String? = null

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
                val address = InetSocketAddress(java.net.InetAddress.getByName("127.0.0.1"), port)
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
                startupError = "cannot bind local server to 127.0.0.1:$port: BindException: ${e.message ?: "bind rejected"}"
            } catch (e: SecurityException) {
                startupError = "cannot bind local server to 127.0.0.1:$port: SecurityException: ${e.message ?: "operation not permitted"}"
            } catch (e: SocketException) {
                startupError = "cannot bind local server to 127.0.0.1:$port: SocketException: ${e.message ?: "socket operation failed"}"
            } catch (e: Throwable) {
                startupError = "cannot start local server on 127.0.0.1:$port: ${e.javaClass.simpleName}: ${e.message ?: "server startup failed"}"
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
            val reader = BufferedReader(InputStreamReader(c.getInputStream(), Charsets.UTF_8))
            val requestLine = reader.readLine() ?: return
            val parts = requestLine.split(" ")
            if (parts.size < 2) return
            val method = parts[0]
            val path = parts[1]
            var contentLength = 0
            while (true) {
                val line = reader.readLine() ?: return
                if (line.isEmpty()) break
                if (line.startsWith("Content-Length:", true)) {
                    contentLength = line.substringAfter(":").trim().toIntOrNull() ?: 0
                }
            }
            val bodyChars = CharArray(contentLength)
            var read = 0
            while (read < contentLength) {
                val n = reader.read(bodyChars, read, contentLength - read)
                if (n <= 0) break
                read += n
            }
            val (status, payload) = route(method, path, String(bodyChars))
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
