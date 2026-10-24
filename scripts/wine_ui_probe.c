/* Read-only UI text probe for our isolated Wine display. No window mutations.
   x86_64-w64-mingw32-gcc scripts/wine_ui_probe.c -o research/wine_ui_probe.exe */
#include <windows.h>
#include <stdio.h>
#include <string.h>
static const char *wanted = NULL;
static void text(HWND h) {
    WCHAR wide[2048] = {0}; char utf8[8192]; DWORD_PTR ignored;
    SendMessageTimeoutW(h, WM_GETTEXT, 2047, (LPARAM)wide,
                        SMTO_ABORTIFHUNG, 500, &ignored);
    if (wide[0]) {
        WideCharToMultiByte(CP_UTF8, 0, wide, -1, utf8, sizeof(utf8), NULL, NULL);
        puts(utf8); fflush(stdout);
    }
}
static BOOL CALLBACK child(HWND h, LPARAM p) { text(h); return TRUE; }
static BOOL CALLBACK window(HWND h, LPARAM p) {
    if (IsWindowVisible(h)) {
        if (wanted) {
            DWORD pid; char path[4096]; DWORD size=sizeof(path);
            GetWindowThreadProcessId(h,&pid);
            HANDLE process=OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);
            if (!process) return TRUE;
            BOOL ok=QueryFullProcessImageNameA(process,0,path,&size); CloseHandle(process);
            if (!ok) return TRUE;
            const char *name=strrchr(path,'\\'); name=name?name+1:path;
            if (_stricmp(name,wanted)) return TRUE;
            printf("matched_executable=%s\n",name);
        }
        text(h); EnumChildWindows(h, child, 0);
    }
    return TRUE;
}
int main(int argc, char **argv) { if(argc>1)wanted=argv[1]; EnumWindows(window, 0); return 0; }
