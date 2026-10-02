#include <jni.h>
#include <algorithm>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include <chrono>
#include "llama.h"

static llama_model *g_model = nullptr;
static llama_context *g_ctx = nullptr;
static llama_sampler *g_sampler = nullptr;
static std::string g_model_path;
static std::mutex g_mutex;
static std::string g_last_inference_stats = "{}";
static int g_threads = 1;

static void free_model_locked() {
    if (g_sampler) { llama_sampler_free(g_sampler); g_sampler = nullptr; }
    if (g_ctx) { llama_free(g_ctx); g_ctx = nullptr; }
    if (g_model) { llama_model_free(g_model); g_model = nullptr; }
    g_model_path.clear();
}

static void warmup_locked() {
    if (!g_model || !g_ctx || !g_sampler) return;

    // Exercise the same prompt-decode and first-sample paths used by Qwen2
    // before the first real request. The result is discarded and all state is
    // reset so warm-up cannot affect the user's first generation.
    char architecture[64] = {0};
    const bool is_qwen2 = llama_model_meta_val_str(
        g_model, "general.architecture", architecture, sizeof(architecture)) > 0 &&
        std::string(architecture) == "qwen2";

    std::string input = "Hello";
    if (is_qwen2) {
        input = "<|im_start|>user\nHello\n<|im_end|>\n<|im_start|>assistant\n";
    }

    const llama_vocab *vocab = llama_model_get_vocab(g_model);
    const int n_prompt = -llama_tokenize(
        vocab, input.c_str(), input.size(), nullptr, 0, true, true);
    if (n_prompt <= 0 || n_prompt >= 128) return;

    std::vector<llama_token> tokens(n_prompt);
    if (llama_tokenize(
            vocab, input.c_str(), input.size(), tokens.data(), tokens.size(), true, true) < 0) {
        return;
    }

    llama_memory_clear(llama_get_memory(g_ctx), true);
    llama_sampler_reset(g_sampler);

    llama_batch batch = llama_batch_get_one(tokens.data(), (int32_t)tokens.size());
    if (llama_decode(g_ctx, batch) == 0) {
        const llama_token token = llama_sampler_sample(g_sampler, g_ctx, -1);
        (void) token;
    }

    // Never carry warm-up KV/sampler state into the first user request.
    llama_memory_clear(llama_get_memory(g_ctx), true);
    llama_sampler_reset(g_sampler);
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_pocketai_server_NativeAi_isReady(JNIEnv*, jobject) { return JNI_TRUE; }

extern "C" JNIEXPORT jstring JNICALL
Java_com_pocketai_server_NativeAi_status(JNIEnv* env, jobject) {
    return env->NewStringUTF("llama.cpp-linked");
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_pocketai_server_NativeAi_version(JNIEnv* env, jobject) {
    const char *version = llama_version();
    return env->NewStringUTF(version ? version : "unknown");
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_pocketai_server_NativeAi_runtimeCheck(JNIEnv* env, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    llama_backend_init();
    const char *version = llama_version();
    std::string result = std::string("OK;backend_initialized;version=") + (version ? version : "unknown");
    return env->NewStringUTF(result.c_str());
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_pocketai_server_NativeAi_loadModel(JNIEnv* env, jobject, jstring path) {
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
    g_threads = threads;
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

    // Pay one-time kernel/sampler initialization cost while loading the model,
    // rather than making the first real conversation pay it.
    warmup_locked();

    env->ReleaseStringUTFChars(path, chars);
    return JNI_TRUE;
}

extern "C" JNIEXPORT void JNICALL
Java_com_pocketai_server_NativeAi_unloadModel(JNIEnv*, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    free_model_locked();
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_pocketai_server_NativeAi_isModelLoaded(JNIEnv*, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return g_model != nullptr && g_ctx != nullptr;
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_pocketai_server_NativeAi_loadedModelName(JNIEnv* env, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (g_model_path.empty()) return env->NewStringUTF("");
    const auto pos = g_model_path.find_last_of("/\\");
    const std::string name = pos == std::string::npos ? g_model_path : g_model_path.substr(pos + 1);
    return env->NewStringUTF(name.c_str());
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_pocketai_server_NativeAi_lastInferenceStats(JNIEnv* env, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return env->NewStringUTF(g_last_inference_stats.c_str());
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_pocketai_server_NativeAi_generate(JNIEnv* env, jobject, jstring prompt, jint max_tokens, jfloat) {
    const char *chars = env->GetStringUTFChars(prompt, nullptr);
    if (!chars) return env->NewStringUTF("ERROR: invalid prompt");

    std::lock_guard<std::mutex> lock(g_mutex);
    if (!g_model || !g_ctx || !g_sampler) {
        env->ReleaseStringUTFChars(prompt, chars);
        return env->NewStringUTF("ERROR: no model loaded");
    }

    std::string input(chars);
    env->ReleaseStringUTFChars(prompt, chars);

    // Qwen2 instruct models expect ChatML framing. Keep other model families on
    // the existing raw-prompt path until their templates are explicitly added.
    char architecture[64] = {0};
    const bool is_qwen2 = llama_model_meta_val_str(
        g_model, "general.architecture", architecture, sizeof(architecture)) > 0 &&
        std::string(architecture) == "qwen2";
    if (is_qwen2) {
        input = "<|im_start|>user\n" + input +
                "<|im_end|>\n<|im_start|>assistant\n";
    }

    using Clock = std::chrono::steady_clock;
    const auto total_start = Clock::now();

    const llama_vocab *vocab = llama_model_get_vocab(g_model);
    const auto tokenize_start = Clock::now();
    const int n_prompt = -llama_tokenize(vocab, input.c_str(), input.size(), nullptr, 0, true, true);
    if (n_prompt <= 0 || n_prompt >= 4096) {
        return env->NewStringUTF("ERROR: prompt tokenization failed");
    }

    std::vector<llama_token> tokens(n_prompt);
    if (llama_tokenize(vocab, input.c_str(), input.size(), tokens.data(), tokens.size(), true, true) < 0) {
        return env->NewStringUTF("ERROR: prompt tokenization failed");
    }
    const auto tokenize_end = Clock::now();

    llama_memory_clear(llama_get_memory(g_ctx), true);
    llama_sampler_reset(g_sampler);

    llama_batch batch = llama_batch_get_one(tokens.data(), (int32_t)tokens.size());
    const auto prompt_decode_start = Clock::now();
    if (llama_decode(g_ctx, batch) != 0) return env->NewStringUTF("ERROR: prompt decode failed");
    const auto prompt_decode_end = Clock::now();

    std::string output;
    const int limit = std::max(1, std::min(512, (int)max_tokens));
    int generated_tokens = 0;
    const auto generation_start = Clock::now();
    for (int i = 0; i < limit; ++i) {
        const llama_token token = llama_sampler_sample(g_sampler, g_ctx, -1);
        if (llama_vocab_is_eog(vocab, token)) break;

        char buf[256];
        const int n = llama_token_to_piece(vocab, token, buf, sizeof(buf), 0, true);
        if (n < 0) break;
        output.append(buf, n);
        ++generated_tokens;

        batch = llama_batch_get_one(const_cast<llama_token*>(&token), 1);
        if (llama_decode(g_ctx, batch) != 0) break;
    }

    const auto generation_end = Clock::now();
    const auto total_end = Clock::now();
    const auto ms = [](auto start, auto end) {
        return std::chrono::duration<double, std::milli>(end - start).count();
    };
    const double generation_ms = ms(generation_start, generation_end);
    const double total_ms = ms(total_start, total_end);
    const double prompt_ms = ms(prompt_decode_start, prompt_decode_end);
    const double generation_tps = generation_ms > 0.0 ? generated_tokens * 1000.0 / generation_ms : 0.0;
    const double prompt_tps = prompt_ms > 0.0 ? n_prompt * 1000.0 / prompt_ms : 0.0;
    g_last_inference_stats = "{\"prompt_tokens\":" + std::to_string(n_prompt) +
        ",\"generated_tokens\":" + std::to_string(generated_tokens) +
        ",\"threads\":" + std::to_string(g_threads) +
        ",\"tokenize_ms\":" + std::to_string(ms(tokenize_start, tokenize_end)) +
        ",\"prompt_decode_ms\":" + std::to_string(prompt_ms) +
        ",\"generation_ms\":" + std::to_string(generation_ms) +
        ",\"total_native_ms\":" + std::to_string(total_ms) +
        ",\"prompt_tokens_per_sec\":" + std::to_string(prompt_tps) +
        ",\"generation_tokens_per_sec\":" + std::to_string(generation_tps) + "}";

    return env->NewStringUTF(output.c_str());
}
