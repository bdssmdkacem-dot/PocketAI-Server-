#include <jni.h>
#include <string>

extern "C"
JNIEXPORT jboolean JNICALL
Java_com_pocketai_server_NativeAi_isReady(JNIEnv*, jobject) {
    return JNI_TRUE;
}

extern "C"
JNIEXPORT jstring JNICALL
Java_com_pocketai_server_NativeAi_status(JNIEnv* env, jobject) {
    const std::string status = "native-bridge-ready";
    return env->NewStringUTF(status.c_str());
}
