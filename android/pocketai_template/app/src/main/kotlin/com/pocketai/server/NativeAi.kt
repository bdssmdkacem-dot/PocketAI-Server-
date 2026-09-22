package com.pocketai.server

class NativeAi {
    external fun isReady(): Boolean
    external fun status(): String
    external fun version(): String

    companion object {
        init {
            System.loadLibrary("pocket_ai")
        }
    }
}
