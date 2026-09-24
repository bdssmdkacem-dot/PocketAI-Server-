#include <jni.h>
#include <string>

#include "llama.h"

extern "C"
JNIEXPORT jboolean JNICALL
Java_com_pocketai_server_NativeAi_isReady(JNIEnv*, jobject) {
    return JNI_TRUE;
}

extern "C"
JNIEXPORT jstring JNICALL
Java_com_pocketai_server_NativeAi_status(JNIEnv* env, jobject) {
    const std::string status = "llama.cpp-linked";
    return env->NewStringUTF(status.c_str());
}

extern "C"
JNIEXPORT jstring JNICALL
Java_com_pocketai_server_NativeAi_version(JNIEnv* env, jobject) {
    const char* version = llama_version();
    return env->NewStringUTF(version != nullptr ? version : "unknown");
}

extern "C"
JNIEXPORT jstring JNICALL
Java_com_pocketai_server_NativeAi_runtimeCheck(JNIEnv* env, jobject) {
    try {
        llama_backend_init();
        const char* version = llama_version();
        const std::string result =
            std::string("OK;backend_initialized;version=") +
            (version != nullptr ? version : "unknown");
        llama_backend_free();
        return env->NewStringUTF(result.c_str());
    } catch (...) {
        return env->NewStringUTF("FAIL;native_exception");
    }
}
