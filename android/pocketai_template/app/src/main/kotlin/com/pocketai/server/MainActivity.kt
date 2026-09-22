package com.pocketai.server

import io.flutter.embedding.android.FlutterActivity

class MainActivity : FlutterActivity() {
    companion object {
        init {
            System.loadLibrary("pocket_ai")
        }
    }
}
