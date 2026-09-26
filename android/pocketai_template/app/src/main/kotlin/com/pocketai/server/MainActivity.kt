package com.pocketai.server

import android.app.ActivityManager
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
import java.util.concurrent.Executors

class MainActivity : FlutterActivity() {
    private val channelName = "pocketai/native"
    private lateinit var nativeAi: NativeAi
    private var server: LocalAiServer? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        nativeAi = NativeAi()
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "status" -> result.success(statusMap())
                    "startServer" -> try {
                        if (server == null) server = LocalAiServer(filesDir, nativeAi).also { it.start() }
                        result.success(serverStatus())
                    } catch (e: Exception) {
                        result.error("SERVER_START_FAILED", e.message, null)
                    }
                    "stopServer" -> {
                        server?.stop()
                        server = null
                        result.success(serverStatus())
                    }
                    "serverStatus" -> result.success(serverStatus())
                    else -> result.notImplemented()
                }
            }

        // Start the local OpenAI-compatible API as soon as the Android activity
        // is initialized. The server must not depend on a Flutter UI action.
        if (server == null) {
            server = LocalAiServer(filesDir, nativeAi).also { it.start() }
        }
    }

    private fun statusMap(): Map<String, Any> = mapOf(
        "ready" to nativeAi.isReady(),
        "status" to nativeAi.status(),
        "version" to nativeAi.version(),
        "runtime" to nativeAi.runtimeCheck(),
        "modelLoaded" to nativeAi.isModelLoaded(),
        "model" to nativeAi.loadedModelName(),
        "device" to deviceCapabilities(),
    )

    private fun serverStatus(): Map<String, Any> = mapOf(
        "running" to (server?.isRunning() == true),
        "host" to "127.0.0.1",
        "port" to (server?.port ?: 8080),
        "modelLoaded" to nativeAi.isModelLoaded(),
        "model" to nativeAi.loadedModelName(),
    )

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

    override fun onDestroy() {
        server?.stop()
        server = null
        nativeAi.unloadModel()
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

    fun start() {
        if (running) return
        java.io.File(filesDir, "models").mkdirs()
        socket = ServerSocket(port, 32, java.net.InetAddress.getByName("127.0.0.1"))
        running = true
        executor.execute {
            while (running) {
                try {
                    val client = socket?.accept() ?: break
                    executor.execute { handle(client) }
                } catch (_: SocketException) {
                    if (running) break
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
