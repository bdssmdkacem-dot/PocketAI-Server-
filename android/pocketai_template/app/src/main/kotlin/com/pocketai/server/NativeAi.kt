package com.pocketai.pocket_ai_server

class NativeAi {
    external fun isReady(): Boolean
    external fun status(): String
    external fun version(): String
    external fun runtimeCheck(): String
    external fun loadModel(path: String): Boolean
    external fun unloadModel()
    external fun isModelLoaded(): Boolean
    external fun loadedModelName(): String
    external fun generate(prompt: String, maxTokens: Int, temperature: Float): String

    companion object {
        init { System.loadLibrary("pocket_ai") }
    }
}
