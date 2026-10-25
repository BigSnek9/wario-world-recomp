// Read-only stack evidence from this project's diagnostic child. No memory dump.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <dbghelp.h>
#include <cstdio>
#include <cwchar>
#include <filesystem>
#include <string>

struct ResumeGuard {
    HANDLE thread;
    ~ResumeGuard() { ResumeThread(thread); }
};

static void window_text(HWND window) {
    wchar_t text[8192]{};
    DWORD_PTR result=0;
    SendMessageTimeoutW(window,WM_GETTEXT,8192,reinterpret_cast<LPARAM>(text),SMTO_ABORTIFHUNG,100,&result);
    char utf8[32768]{};
    WideCharToMultiByte(CP_UTF8,0,text,-1,utf8,sizeof utf8,nullptr,nullptr);
    if (*utf8) std::printf("Window text: %s\n",utf8);
}

static BOOL CALLBACK child_window(HWND window, LPARAM) { window_text(window); return TRUE; }
static BOOL CALLBACK owned_window(HWND window, LPARAM owner) {
    DWORD pid=0; GetWindowThreadProcessId(window,&pid);
    if(pid==static_cast<DWORD>(owner)) { window_text(window); EnumChildWindows(window,child_window,0); }
    return TRUE;
}

int wmain(int argc, wchar_t** argv) {
    if (argc != 3) return 2;
    DWORD pid = wcstoul(argv[1], nullptr, 10);
    HANDLE process = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, FALSE, pid);
    if (!process) return 3;
    wchar_t actual[32768]; DWORD length = 32768;
    if (!QueryFullProcessImageNameW(process, 0, actual, &length) || _wcsicmp(actual, argv[2]) != 0) {
        std::puts("Refusing: PID does not match the exact diagnostic runner path.");
        CloseHandle(process); return 4;
    }
    EnumWindows(owned_window,static_cast<LPARAM>(pid));
    auto symbols = std::filesystem::path(argv[2]).parent_path().wstring();
    SymSetOptions(SYMOPT_DEFERRED_LOADS | SYMOPT_LOAD_LINES | SYMOPT_UNDNAME | SYMOPT_FAIL_CRITICAL_ERRORS);
    if (!SymInitializeW(process, symbols.c_str(), TRUE)) { CloseHandle(process); return 5; }
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    THREADENTRY32 entry{}; entry.dwSize = sizeof entry;
    if (Thread32First(snapshot, &entry)) do {
        if (entry.th32OwnerProcessID != pid) continue;
        HANDLE thread = OpenThread(THREAD_GET_CONTEXT | THREAD_SUSPEND_RESUME | THREAD_QUERY_INFORMATION, FALSE, entry.th32ThreadID);
        if (!thread) continue;
        PWSTR description = nullptr;
        GetThreadDescription(thread, &description);
        std::wstring name = description ? description : L"";
        if (description) LocalFree(description);
        char utf8_name[1024]{};
        WideCharToMultiByte(CP_UTF8,0,name.c_str(),-1,utf8_name,sizeof utf8_name,nullptr,nullptr);
        std::printf("Thread %lu %s\n", entry.th32ThreadID, utf8_name);
        // CPU and graphics threads are sufficient for the current verifier stall.
        if (name.find(L"CPU") == std::wstring::npos && name.find(L"GPU") == std::wstring::npos &&
            name.find(L"Video") == std::wstring::npos) { CloseHandle(thread); continue; }
        if (SuspendThread(thread) != DWORD(-1)) {
            ResumeGuard resume{thread};
            CONTEXT context{}; context.ContextFlags = CONTEXT_FULL;
            if (GetThreadContext(thread, &context)) {
                STACKFRAME64 frame{};
                frame.AddrPC.Offset = context.Rip; frame.AddrPC.Mode = AddrModeFlat;
                frame.AddrStack.Offset = context.Rsp; frame.AddrStack.Mode = AddrModeFlat;
                frame.AddrFrame.Offset = context.Rbp; frame.AddrFrame.Mode = AddrModeFlat;
                for (int level = 0; level < 40 && frame.AddrPC.Offset; ++level) {
                    alignas(SYMBOL_INFO) char buffer[sizeof(SYMBOL_INFO) + 4096]{};
                    auto* symbol = reinterpret_cast<SYMBOL_INFO*>(buffer);
                    symbol->SizeOfStruct = sizeof(SYMBOL_INFO); symbol->MaxNameLen = 4095;
                    DWORD64 displacement = 0;
                    std::printf("  %02d %016llx", level, static_cast<unsigned long long>(frame.AddrPC.Offset));
                    if (SymFromAddr(process, frame.AddrPC.Offset, &displacement, symbol))
                        std::printf(" %s+0x%llx", symbol->Name, static_cast<unsigned long long>(displacement));
                    IMAGEHLP_LINE64 line{}; line.SizeOfStruct = sizeof line; DWORD delta = 0;
                    if (SymGetLineFromAddr64(process, frame.AddrPC.Offset, &delta, &line))
                        std::printf(" (%s:%lu)", line.FileName, line.LineNumber);
                    std::puts("");
                    if (!StackWalk64(IMAGE_FILE_MACHINE_AMD64, process, thread, &frame, &context,
                                     nullptr, SymFunctionTableAccess64, SymGetModuleBase64, nullptr)) break;
                }
            }
        }
        CloseHandle(thread);
    } while (Thread32Next(snapshot, &entry));
    CloseHandle(snapshot); SymCleanup(process); CloseHandle(process); return 0;
}
