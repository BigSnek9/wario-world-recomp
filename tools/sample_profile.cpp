// Read-only sampling profiler for this project's diagnostic child. No memory dump.
// Usage: sample_profile <pid> <exact-runner-path> <duration-ms> <out.csv> [interval-ms]
// Every interval it briefly suspends each recently busy thread, records RIP, and
// resumes it. Output CSV rows: t_ms,tid,thread,module,symbol. A summary of the
// hottest symbols per thread is printed to stdout.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <timeapi.h>
#include <tlhelp32.h>
#include <dbghelp.h>
#include <algorithm>
#include <cstdio>
#include <cwchar>
#include <filesystem>
#include <map>
#include <string>
#include <unordered_map>
#include <vector>

struct ThreadInfo {
    HANDLE handle = nullptr;
    std::string name;
    ULONGLONG last_cpu = 0;
    bool busy = true;
};

struct Sample {
    DWORD t_ms;
    DWORD tid;
    DWORD64 rip;
};

static ULONGLONG cpu_time(HANDLE thread) {
    FILETIME c, e, k, u;
    if (!GetThreadTimes(thread, &c, &e, &k, &u)) return 0;
    return (ULONGLONG(k.dwHighDateTime) << 32 | k.dwLowDateTime) + (ULONGLONG(u.dwHighDateTime) << 32 | u.dwLowDateTime);
}

static std::string thread_name(HANDLE thread) {
    PWSTR description = nullptr;
    GetThreadDescription(thread, &description);
    std::wstring name = description ? description : L"";
    if (description) LocalFree(description);
    char utf8[512]{};
    WideCharToMultiByte(CP_UTF8, 0, name.c_str(), -1, utf8, sizeof utf8, nullptr, nullptr);
    std::string result = utf8;
    std::replace(result.begin(), result.end(), ',', ';');
    return result;
}

static void refresh_threads(DWORD pid, std::map<DWORD, ThreadInfo>& threads) {
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    THREADENTRY32 entry{};
    entry.dwSize = sizeof entry;
    if (Thread32First(snapshot, &entry)) do {
        if (entry.th32OwnerProcessID != pid || threads.count(entry.th32ThreadID)) continue;
        HANDLE thread = OpenThread(THREAD_GET_CONTEXT | THREAD_SUSPEND_RESUME | THREAD_QUERY_INFORMATION, FALSE, entry.th32ThreadID);
        if (!thread) continue;
        ThreadInfo info;
        info.handle = thread;
        info.name = thread_name(thread);
        info.last_cpu = cpu_time(thread);
        threads[entry.th32ThreadID] = info;
    } while (Thread32Next(snapshot, &entry));
    CloseHandle(snapshot);
    for (auto& [tid, info] : threads) {
        ULONGLONG now = cpu_time(info.handle);
        info.busy = now != info.last_cpu;
        info.last_cpu = now;
        if (info.name.empty()) info.name = thread_name(info.handle);
    }
}

int wmain(int argc, wchar_t** argv) {
    if (argc < 5) return 2;
    DWORD pid = wcstoul(argv[1], nullptr, 10);
    DWORD duration = wcstoul(argv[3], nullptr, 10);
    DWORD interval = argc > 5 ? wcstoul(argv[5], nullptr, 10) : 1;
    HANDLE process = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pid);
    if (!process) return 3;
    wchar_t actual[32768];
    DWORD length = 32768;
    if (!QueryFullProcessImageNameW(process, 0, actual, &length) || _wcsicmp(actual, argv[2]) != 0) {
        std::puts("Refusing: PID does not match the exact diagnostic runner path.");
        CloseHandle(process);
        return 4;
    }
    timeBeginPeriod(1);
    std::map<DWORD, ThreadInfo> threads;
    std::vector<Sample> samples;
    samples.reserve(1 << 20);
    DWORD start = GetTickCount(), last_refresh = 0;
    refresh_threads(pid, threads);
    for (;;) {
        DWORD now = GetTickCount() - start;
        if (now >= duration) break;
        if (now - last_refresh >= 250) {
            refresh_threads(pid, threads);
            last_refresh = now;
        }
        for (auto& [tid, info] : threads) {
            if (!info.busy) continue;
            if (SuspendThread(info.handle) == DWORD(-1)) continue;
            CONTEXT context{};
            context.ContextFlags = CONTEXT_CONTROL;
            if (GetThreadContext(info.handle, &context)) samples.push_back({now, tid, context.Rip});
            ResumeThread(info.handle);
        }
        Sleep(interval);
    }
    timeEndPeriod(1);

    auto symbols = std::filesystem::path(argv[2]).parent_path().wstring();
    SymSetOptions(SYMOPT_DEFERRED_LOADS | SYMOPT_UNDNAME | SYMOPT_FAIL_CRITICAL_ERRORS);
    if (!SymInitializeW(process, symbols.c_str(), TRUE)) return 5;
    std::unordered_map<DWORD64, std::pair<std::string, std::string>> cache;
    auto resolve = [&](DWORD64 rip) -> const std::pair<std::string, std::string>& {
        auto found = cache.find(rip);
        if (found != cache.end()) return found->second;
        std::string module = "?", symbol;
        IMAGEHLP_MODULE64 mod{};
        mod.SizeOfStruct = sizeof mod;
        if (SymGetModuleInfo64(process, rip, &mod)) module = mod.ModuleName;
        alignas(SYMBOL_INFO) char buffer[sizeof(SYMBOL_INFO) + 1024]{};
        auto* info = reinterpret_cast<SYMBOL_INFO*>(buffer);
        info->SizeOfStruct = sizeof(SYMBOL_INFO);
        info->MaxNameLen = 1023;
        DWORD64 displacement = 0;
        if (SymFromAddr(process, rip, &displacement, info)) {
            symbol = info->Name;
            // Without a containing private symbol DbgHelp returns the nearest
            // preceding public one; mark those so they are not misread.
            if (info->Size != 0 && displacement >= info->Size) symbol = "~" + symbol;
        }
        else {
            char hex[32];
            std::snprintf(hex, sizeof hex, "0x%llx", static_cast<unsigned long long>(rip - mod.BaseOfImage));
            symbol = hex;
        }
        std::replace(symbol.begin(), symbol.end(), ',', ';');
        return cache[rip] = {module, symbol};
    };

    FILE* out = _wfopen(argv[4], L"w");
    if (!out) return 6;
    std::fputs("t_ms,tid,thread,module,symbol\n", out);
    std::map<DWORD, std::map<std::string, int>> per_thread;
    std::map<DWORD, int> totals;
    for (const auto& sample : samples) {
        const auto& [module, symbol] = resolve(sample.rip);
        std::fprintf(out, "%lu,%lu,%s,%s,%s\n", sample.t_ms, sample.tid, threads[sample.tid].name.c_str(), module.c_str(), symbol.c_str());
        per_thread[sample.tid][module + "!" + symbol]++;
        totals[sample.tid]++;
    }
    std::fclose(out);
    std::vector<std::pair<int, DWORD>> order;
    for (auto& [tid, count] : totals) order.push_back({count, tid});
    std::sort(order.rbegin(), order.rend());
    for (auto& [count, tid] : order) {
        if (count < 20) continue;
        std::printf("Thread %lu '%s': %d samples\n", tid, threads[tid].name.c_str(), count);
        std::vector<std::pair<int, std::string>> hot;
        for (auto& [name, n] : per_thread[tid]) hot.push_back({n, name});
        std::sort(hot.rbegin(), hot.rend());
        for (size_t i = 0; i < hot.size() && i < 15; ++i)
            std::printf("  %6.2f%% %s\n", 100.0 * hot[i].first / count, hot[i].second.c_str());
    }
    for (auto& [tid, info] : threads) CloseHandle(info.handle);
    SymCleanup(process);
    CloseHandle(process);
    return 0;
}
