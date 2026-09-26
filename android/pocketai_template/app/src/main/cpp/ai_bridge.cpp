#include <jni.h>
#include <algorithm>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include "llama.h"

static llama_model *g_model = nullptr;
static llama_context *g_ctx = nullptr;
static llama_sampler *g_sampler = nullptr;
static std::string g_model_path;
static std::mutex g_mutex;

static void free_model_locked() {
    if (g_sampler) { llama_sampler_free(g_sampler); g_sampler = nullptr; }
    if (g_ctx) { llama_free(g_ctx); g_ctx = nullptr; }
    if (g_model) { llama_model_free(g_model); g_model = nullptr; }
    g_model_path.clear();
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_pocketai_pocket_1ai_1server_NativeAi_isReady(JNIEnv*, jobject) { return JNI_TRUE; }

extern "C" JNIEXPORT jstring JNICALL
Java_com_pocketai_pocket_1ai_1server_NativeAi_status(JNIEnv* env, jobject) {
    return env->NewStringUTF("llama.cpp-linked");
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_pocketai_pocket_1ai_1server_NativeAi_version(JNIEnv* env, jobject) {
    const char *version = llama_version();
    return env->NewStringUTF(version ? version : "unknown");
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_pocketai_pocket_1ai_1server_NativeAi_runtimeCheck(JNIEnv* env, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    llama_backend_init();
    const char *version = llama_version();
    std::string result = std::string("OK;backend_initialized;version=") + (version ? version : "unknown");
    return env->NewStringUTF(result.c_str());
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_pocketai_pocket_1ai_1server_NativeAi_loadModel(JNIEnv* env, jobject, jstring path) {
    const char *chars = env->GetStringUTFChars(path, nullptr);
    if (!chars) return JNI_FALSE;

    std::lock_guard<std::mutex> lock(g_mutex);
    llama_backend_init();
    free_model_locked();

    llama_model_params mp = llama_model_default_params();
    mp.n_gpu_layers = 0;
    g_model = llama_model_load_from_file(chars, mp);
    if (!g_model) {
        env->ReleaseStringUTFChars(path, chars);
        return JNI_FALSE;
    }

    llama_context_params cp = llama_context_default_params();
    cp.n_ctx = 2048;
    cp.n_batch = 512;
    const int threads = std::max(1, std::min(8, (int) std::thread::hardware_concurrency()));
    cp.n_threads = threads;
    cp.n_threads_batch = threads;

    g_ctx = llama_init_from_model(g_model, cp);
    if (!g_ctx) {
        free_model_locked();
        env->ReleaseStringUTFChars(path, chars);
        return JNI_FALSE;
    }

    g_sampler = llama_sampler_chain_init(llama_sampler_chain_default_params());
    if (!g_sampler) {
        free_model_locked();
        env->ReleaseStringUTFChars(path, chars);
        return JNI_FALSE;
    }
    llama_sampler_chain_add(g_sampler, llama_sampler_init_greedy());
    g_model_path = chars;
    env->ReleaseStringUTFChars(path, chars);
    return JNI_TRUE;
}

extern "C" JNIEXPORT void JNICALL
Java_com_pocketai_pocket_1ai_1server_NativeAi_unloadModel(JNIEnv*, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    free_model_locked();
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_pocketai_pocket_1ai_1server_NativeAi_isModelLoaded(JNIEnv*, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_model != nullptr && g_ctx != nullptr;
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_pocketai_pocket_1ai_1server_NativeAi_loadedModelName(JNIEnv* env, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_model_path.empty()) return env->NewStringUTF("");
    const auto pos = g_model_path.find_last_of("/\\");
    const std::string name = pos == std::string::npos ? g_model_path : g_model_path.substr(pos + 1);
    return env->NewStringUTF(name.c_str());
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_pocketai_pocket_1ai_1server_NativeAi_generate(JNIEnv* env, jobject, jstring prompt, jint max_tokens, jfloat) {
    const char *chars = env->GetStringUTFChars(prompt, nullptr);
    if (!chars) return env->NewStringUTF("ERROR: invalid prompt");

    std::lock_guard<std::mutex> lock(g_mutex);
    if (!g_model || !g_ctx || !g_sampler) {
        env->ReleaseStringUTFChars(prompt, chars);
        return env->NewStringUTF("ERROR: no model loaded");
    }

    const llama_vocab *vocab = llama_model_get_vocab(g_model);
    const int n_prompt = -llama_tokenize(vocab, chars, std::strlen(chars), nullptr, 0, true, true);
    if (n_prompt <= 0 || n_prompt >= 4096) {
        env->ReleaseStringUTFChars(prompt, chars);
        return env->NewStringUTF("ERROR: prompt tokenization failed");
    }

    std::vector<llama_token> tokens(n_prompt);
    if (llama_tokenize(vocab, chars, std::strlen(chars), tokens.data(), tokens.size(), true, true) < 0) {
        env->ReleaseStringUTFChars(prompt, chars);
        return env->NewStringUTF("ERROR: prompt tokenization failed");
    }
    env->ReleaseStringUTFChars(prompt, chars);

    llama_memory_clear(llama_get_memory(g_ctx), true);
    llama_sampler_reset(g_sampler);

    llama_batch batch = llama_batch_get_one(tokens.data(), (int32_t)tokens.size());
    if (llama_decode(g_ctx, batch) != 0) return env->NewStringUTF("ERROR: prompt decode failed");

    std::string output;
    const int limit = std::max(1, std::min(512, (int)max_tokens));
    for (int i = 0; i < limit; ++i) {
        const llama_token token = llama_sampler_sample(g_sampler, g_ctx, -1);
        if (llama_vocab_is_eog(vocab, token)) break;

        char buf[256];
        const int n = llama_token_to_piece(vocab, token, buf, sizeof(buf), 0, true);
        if (n < 0) break;
        output.append(buf, n);

        batch = llama_batch_get_one(const_cast<llama_token*>(&token), 1);
        if (llama_decode(g_ctx, batch) != 0) break;
    }

    return env->NewStringUTF(output.c_str());
}
