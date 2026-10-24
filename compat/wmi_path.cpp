// Experimental Wine 9 path-syntax adapter. Reads the real WMI volume identifier.
// No identifier is generated, substituted, logged, or registered with a carrier.
#include <windows.h>
#include <wmiutils.h>
#include <string>
#include <new>
// Standard interface identifiers from wmiutils.idl; absent from MinGW's UUID library.
const IID IID_IWbemPath={0x3bc15af2,0x736c,0x477e,{0x9e,0x51,0x23,0x8a,0xf8,0x66,0x7d,0xcc}};
const CLSID CLSID_WbemDefPath={0xcf4cc405,0xe2c5,0x4ddd,{0xb3,0xce,0x5e,0x75,0x82,0xd8,0xc9,0xfa}};

static std::wstring normalized_path(const wchar_t *path) {
    std::wstring result(path);
    const wchar_t *prefix=L"Win32_LogicalDisk=";
    size_t n=wcslen(prefix);
    // Only the exact shorthand used by the app; preserve all other WMI paths.
    if(!_wcsnicmp(path,prefix,n) && result.size()==n+4 && path[n]==L'"' &&
       ((path[n+1]>=L'A' && path[n+1]<=L'Z') || (path[n+1]>=L'a' && path[n+1]<=L'z')) &&
       path[n+2]==L':' && path[n+3]==L'"')
        result=std::wstring(L"Win32_LogicalDisk.DeviceID=")+(path+n);
    return result;
}
class Path : public IWbemPath {
    LONG refs=1; IWbemPath *inner;
public:
    explicit Path(IWbemPath *p):inner(p) {}
    ~Path() { inner->Release(); }
    HRESULT WINAPI QueryInterface(REFIID id,void **out) override {
        if(!out) return E_POINTER; *out=nullptr;
        if(id==IID_IUnknown || id==IID_IWbemPath) { *out=static_cast<IWbemPath*>(this); AddRef(); return S_OK; }
        return E_NOINTERFACE;
    }
    ULONG WINAPI AddRef() override { return InterlockedIncrement(&refs); }
    ULONG WINAPI Release() override { ULONG n=InterlockedDecrement(&refs); if(!n) delete this; return n; }
    HRESULT WINAPI SetText(ULONG mode,LPCWSTR text) override {
        if(!text) return inner->SetText(mode,text);
        try { return inner->SetText(mode,normalized_path(text).c_str()); }
        catch(const std::bad_alloc&) { return E_OUTOFMEMORY; }
        catch(...) { return E_UNEXPECTED; }
    }
    HRESULT WINAPI GetText(LONG a,ULONG *b,LPWSTR c) override { return inner->GetText(a,b,c); }
    HRESULT WINAPI GetInfo(ULONG a,ULONGLONG *b) override { return inner->GetInfo(a,b); }
    HRESULT WINAPI SetServer(LPCWSTR a) override { return inner->SetServer(a); }
    HRESULT WINAPI GetServer(ULONG *a,LPWSTR b) override { return inner->GetServer(a,b); }
    HRESULT WINAPI GetNamespaceCount(ULONG *a) override { return inner->GetNamespaceCount(a); }
    HRESULT WINAPI SetNamespaceAt(ULONG a,LPCWSTR b) override { return inner->SetNamespaceAt(a,b); }
    HRESULT WINAPI GetNamespaceAt(ULONG a,ULONG *b,LPWSTR c) override { return inner->GetNamespaceAt(a,b,c); }
    HRESULT WINAPI RemoveNamespaceAt(ULONG a) override { return inner->RemoveNamespaceAt(a); }
    HRESULT WINAPI RemoveAllNamespaces() override { return inner->RemoveAllNamespaces(); }
    HRESULT WINAPI GetScopeCount(ULONG *a) override { return inner->GetScopeCount(a); }
    HRESULT WINAPI SetScope(ULONG a,LPWSTR b) override { return inner->SetScope(a,b); }
    HRESULT WINAPI SetScopeFromText(ULONG a,LPWSTR b) override { return inner->SetScopeFromText(a,b); }
    HRESULT WINAPI GetScope(ULONG a,ULONG *b,LPWSTR c,IWbemPathKeyList **d) override { return inner->GetScope(a,b,c,d); }
    HRESULT WINAPI GetScopeAsText(ULONG a,ULONG *b,LPWSTR c) override { return inner->GetScopeAsText(a,b,c); }
    HRESULT WINAPI RemoveScope(ULONG a) override { return inner->RemoveScope(a); }
    HRESULT WINAPI RemoveAllScopes() override { return inner->RemoveAllScopes(); }
    HRESULT WINAPI SetClassName(LPCWSTR a) override { return inner->SetClassName(a); }
    HRESULT WINAPI GetClassName(ULONG *a,LPWSTR b) override { return inner->GetClassName(a,b); }
    HRESULT WINAPI GetKeyList(IWbemPathKeyList **a) override { return inner->GetKeyList(a); }
    HRESULT WINAPI CreateClassPart(LONG a,LPCWSTR b) override { return inner->CreateClassPart(a,b); }
    HRESULT WINAPI DeleteClassPart(LONG a) override { return inner->DeleteClassPart(a); }
    BOOL WINAPI IsRelative(LPWSTR a,LPWSTR b) override { return inner->IsRelative(a,b); }
    BOOL WINAPI IsRelativeOrChild(LPWSTR a,LPWSTR b,LONG c) override { return inner->IsRelativeOrChild(a,b,c); }
    BOOL WINAPI IsLocal(LPCWSTR a) override { return inner->IsLocal(a); }
    BOOL WINAPI IsSameClassName(LPCWSTR a) override { return inner->IsSameClassName(a); }
};
class Factory : public IClassFactory {
public:
    HRESULT WINAPI QueryInterface(REFIID id,void **out) override {
        if(!out) return E_POINTER; *out=nullptr;
        if(id==IID_IUnknown || id==IID_IClassFactory) { *out=this; return S_OK; } return E_NOINTERFACE;
    }
    ULONG WINAPI AddRef() override { return 2; }
    ULONG WINAPI Release() override { return 1; }
    HRESULT WINAPI CreateInstance(IUnknown *outer,REFIID id,void **out) override {
        if(!out) return E_POINTER; *out=nullptr;
        if(outer) return CLASS_E_NOAGGREGATION;
        static HMODULE module=LoadLibraryW(L"C:\\windows\\system32\\wbem\\wmiutils.dll");
        typedef HRESULT (WINAPI *GetFactory)(REFCLSID,REFIID,void**);
        auto fn=module?reinterpret_cast<GetFactory>(GetProcAddress(module,"DllGetClassObject")):nullptr;
        if(!fn) return E_FAIL;
        IClassFactory *factory=nullptr; IWbemPath *inner=nullptr;
        HRESULT hr=fn(CLSID_WbemDefPath,IID_IClassFactory,reinterpret_cast<void**>(&factory));
        if(FAILED(hr)) return hr;
        if(id!=IID_IUnknown && id!=IID_IWbemPath) { hr=factory->CreateInstance(nullptr,id,out); factory->Release(); return hr; }
        hr=factory->CreateInstance(nullptr,IID_IWbemPath,reinterpret_cast<void**>(&inner)); factory->Release();
        if(FAILED(hr)) return hr;
        auto wrapper=new(std::nothrow) Path(inner);
        if(!wrapper) { inner->Release(); return E_OUTOFMEMORY; }
        hr=wrapper->QueryInterface(id,out); wrapper->Release(); return hr;
    }
    HRESULT WINAPI LockServer(BOOL) override { return S_OK; }
};
extern "C" __declspec(dllexport) HRESULT WINAPI DllGetClassObject(REFCLSID cls,REFIID id,void **out) {
    static Factory factory;
    if(cls!=CLSID_WbemDefPath) return CLASS_E_CLASSNOTAVAILABLE;
    return factory.QueryInterface(id,out);
}
extern "C" __declspec(dllexport) HRESULT WINAPI DllCanUnloadNow() { return S_FALSE; }
