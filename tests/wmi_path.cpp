#include "../compat/wmi_path.cpp"
#include <cstdio>
int main() {
    int failures=0;
    if(normalized_path(L"Win32_LogicalDisk=\"C:\"")!=L"Win32_LogicalDisk.DeviceID=\"C:\"") ++failures;
    if(normalized_path(L"Win32_LogicalDisk=\"d:\"")!=L"Win32_LogicalDisk.DeviceID=\"d:\"") ++failures;
    const wchar_t *unchanged[]={L"",L"Win32_OperatingSystem",L"Win32_LogicalDisk.DeviceID=\"C:\"",L"Win32_LogicalDisk=\"bad\"",L"Win32_LogicalDisk=\"C:\"suffix",L"root\\cimv2:Win32_LogicalDisk=\"C:\""};
    for(auto value:unchanged) if(normalized_path(value)!=value) ++failures;
    std::printf("wmi_path_failures=%d\n",failures); return failures?1:0;
}
