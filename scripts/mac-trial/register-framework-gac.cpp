// Register managed framework files already installed from official Microsoft MSI.
#include <windows.h>
#include <fusion.h>
#include <stdio.h>
int wmain(int argc, wchar_t** argv){
 const wchar_t* root=L"C:\\windows\\Microsoft.NET\\Framework64\\v2.0.50727\\";
 wchar_t path[1024];swprintf(path,1024,L"%lsfusion.dll",root);
 HMODULE dll=LoadLibraryW(path);if(!dll){printf("fusion_load_error=%lu\n",GetLastError());return 1;}
 typedef HRESULT (WINAPI *CreateCache)(IAssemblyCache**,DWORD);
 auto create=(CreateCache)GetProcAddress(dll,"CreateAssemblyCache");IAssemblyCache* cache=nullptr;
 if(!create || FAILED(create(&cache,0))){puts("cache_creation_failed");return 1;}
 if(argc>1)root=argv[1];
 swprintf(path,1024,L"%ls*.dll",root);WIN32_FIND_DATAW data;HANDLE h=FindFirstFileW(path,&data);
 int ok=0,skip=0;if(h==INVALID_HANDLE_VALUE)return 1;
 do {if(data.dwFileAttributes&FILE_ATTRIBUTE_DIRECTORY)continue;
 swprintf(path,1024,L"%ls%ls",root,data.cFileName);HRESULT hr=cache->InstallAssembly(0,path,nullptr);
 if(SUCCEEDED(hr))ok++;else skip++;
 }while(FindNextFileW(h,&data));FindClose(h);cache->Release();
 printf("gac_registered=%d; nonregistered_dlls=%d\n",ok,skip);return ok?0:1;
}
