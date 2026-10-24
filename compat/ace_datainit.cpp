// Experimental Wine 9 compatibility shim. No application binaries are modified.
// Wine's IDataInitialize treats Jet OLEDB:Database Password as a provider string.
// Forward all other work, and set that property using ACE's own property metadata.
// Never log connection strings, passwords, or database records.
#define DBINITCONSTANTS
#include <windows.h>
#include <oledb.h>
#include <oledberr.h>
#include <msdasc.h>
#include <string>
#include <new>
#include <cwctype>

typedef HRESULT (WINAPI *GetFactory)(REFCLSID, REFIID, void **);
static GetFactory original_factory() {
    // Deliberately load the existing 64-bit Wine implementation, not our COM registration.
    static HMODULE module = LoadLibraryW(L"C:\\Program Files\\Common Files\\System\\OLE DB\\oledb32.dll");
    return module ? reinterpret_cast<GetFactory>(GetProcAddress(module, "DllGetClassObject")) : nullptr;
}
static std::wstring trim(const std::wstring &s) {
    size_t a=0,b=s.size();
    while(a<b && iswspace(s[a])) ++a;
    while(b>a && iswspace(s[b-1])) --b;
    return s.substr(a,b-a);
}
struct Secret {
    std::wstring value;
    ~Secret() { if(!value.empty()) SecureZeroMemory(&value[0],value.size()*sizeof(wchar_t)); }
};
// Preserve original syntax for every other property, including quoted semicolons.
static HRESULT strip_password(const wchar_t *text, std::wstring &clean, Secret &secret, bool &found) {
    found=false;
    const wchar_t *start=text, *p=text;
    wchar_t quote=0; bool valueStart=false, hasEquals=false, ace=false, quoteClosed=false;
    for(;;++p) {
        if(quote) {
            if(*p==quote) { if(p[1]==quote) { ++p; continue; } quote=0; quoteClosed=true; }
            else if(!*p) return E_INVALIDARG;
        } else if(quoteClosed && *p && *p!=L';' && !iswspace(*p)) return E_INVALIDARG;
        else if(!hasEquals && *p==L'=') { hasEquals=true; valueStart=true; }
        else if(valueStart && !iswspace(*p)) {
            if(*p==L'\'' || *p==L'"') quote=*p;
            valueStart=false;
        }
        if(!quote && (*p==L';' || !*p)) {
            std::wstring segment(start,p-start);
            size_t eq=segment.find(L'=');
            if(eq!=std::wstring::npos && !_wcsicmp(trim(segment.substr(0,eq)).c_str(),L"Provider")) {
                std::wstring provider=trim(segment.substr(eq+1));
                if(provider.size()>=2 && (provider.front()==L'\'' || provider.front()==L'"') && provider.back()==provider.front()) provider=provider.substr(1,provider.size()-2);
                ace=!_wcsicmp(provider.c_str(),L"Microsoft.ACE.OLEDB.12.0") || !_wcsicmp(provider.c_str(),L"Microsoft.ACE.OLEDB.16.0");
            }
            if(eq!=std::wstring::npos && !_wcsicmp(trim(segment.substr(0,eq)).c_str(),L"Jet OLEDB:Database Password")) {
                if(found) return E_INVALIDARG;
                found=true; secret.value=trim(segment.substr(eq+1));
                if(secret.value.size()>=2 && (secret.value[0]==L'\'' || secret.value[0]==L'"')) {
                    wchar_t q=secret.value[0];
                    if(secret.value.back()!=q) return E_INVALIDARG;
                    std::wstring decoded;
                    for(size_t i=1;i+1<secret.value.size();++i) {
                        decoded+=secret.value[i];
                        if(secret.value[i]==q && i+2<secret.value.size() && secret.value[i+1]==q) ++i;
                    }
                    SecureZeroMemory(&secret.value[0],secret.value.size()*sizeof(wchar_t));
                    secret.value.swap(decoded);
                }
            } else { clean+=segment; if(*p) clean+=L';'; }
            if(!*p) break;
            start=p+1;
            hasEquals=false; valueStart=false; quoteClosed=false;
        }
    }
    if(!ace) found=false;
    return S_OK;
}
static HRESULT set_password(IUnknown *source, const std::wstring &password) {
    IDBProperties *props=nullptr;
    HRESULT hr=source->QueryInterface(IID_IDBProperties,reinterpret_cast<void**>(&props));
    if(FAILED(hr)) return hr;
    ULONG count=0; DBPROPINFOSET *infos=nullptr; OLECHAR *descriptions=nullptr;
    hr=props->GetPropertyInfo(0,nullptr,&count,&infos,&descriptions);
    if(SUCCEEDED(hr)) {
        hr=DB_E_ERRORSOCCURRED;
        for(ULONG i=0;i<count;++i) for(ULONG j=0;j<infos[i].cPropertyInfos;++j) {
            const DBPROPINFO &info=infos[i].rgPropertyInfos[j];
            if(info.pwszDescription && !_wcsicmp(info.pwszDescription,L"Jet OLEDB:Database Password")) {
                DBPROP value={}; DBPROPSET set={};
                value.dwPropertyID=info.dwPropertyID; value.dwOptions=DBPROPOPTIONS_REQUIRED;
                V_VT(&value.vValue)=VT_BSTR; V_BSTR(&value.vValue)=SysAllocString(password.c_str());
                if(!V_BSTR(&value.vValue)) { hr=E_OUTOFMEMORY; continue; }
                set.guidPropertySet=infos[i].guidPropertySet; set.cProperties=1; set.rgProperties=&value;
                hr=props->SetProperties(1,&set);
                if(SUCCEEDED(hr) && value.dwStatus!=DBPROPSTATUS_OK) hr=DB_E_ERRORSOCCURRED;
                SecureZeroMemory(V_BSTR(&value.vValue),SysStringByteLen(V_BSTR(&value.vValue)));
                VariantClear(&value.vValue);
            }
        }
    }
    if(infos) {
        for(ULONG i=0;i<count;++i) {
            for(ULONG j=0;j<infos[i].cPropertyInfos;++j) VariantClear(&infos[i].rgPropertyInfos[j].vValues);
            CoTaskMemFree(infos[i].rgPropertyInfos);
        }
        CoTaskMemFree(infos);
    }
    CoTaskMemFree(descriptions); props->Release(); return hr;
}
class Initialize : public IDataInitialize {
    LONG refs=1;
    IDataInitialize *inner;
public:
    explicit Initialize(IDataInitialize *p):inner(p) {}
    ~Initialize() { inner->Release(); }
    HRESULT WINAPI QueryInterface(REFIID id,void **out) override {
        if(!out) return E_POINTER; *out=nullptr;
        if(id==IID_IUnknown || id==IID_IDataInitialize) { *out=static_cast<IDataInitialize*>(this); AddRef(); return S_OK; }
        return E_NOINTERFACE;
    }
    ULONG WINAPI AddRef() override { return InterlockedIncrement(&refs); }
    ULONG WINAPI Release() override { ULONG n=InterlockedDecrement(&refs); if(!n) delete this; return n; }
    HRESULT WINAPI GetDataSource(IUnknown *outer,DWORD ctx,LPCOLESTR text,REFIID id,IUnknown **out) override {
        if(!text || !out || *out) return inner->GetDataSource(outer,ctx,text,id,out);
        try {
            std::wstring clean; Secret password; bool found;
            HRESULT hr=strip_password(text,clean,password,found);
            if(FAILED(hr)) return inner->GetDataSource(outer,ctx,text,id,out);
            hr=inner->GetDataSource(outer,ctx,found?clean.c_str():text,id,out);
            if(SUCCEEDED(hr) && found && *out) {
                hr=set_password(*out,password.value);
                if(FAILED(hr)) { (*out)->Release(); *out=nullptr; }
            }
            return hr;
        } catch(const std::bad_alloc&) { return E_OUTOFMEMORY; }
          catch(...) { return E_UNEXPECTED; }
    }
    HRESULT WINAPI GetInitializationString(IUnknown *s,boolean p,LPOLESTR *out) override { return inner->GetInitializationString(s,p,out); }
    HRESULT WINAPI CreateDBInstance(REFCLSID c,IUnknown *o,DWORD x,LPOLESTR r,REFIID i,IUnknown **out) override { return inner->CreateDBInstance(c,o,x,r,i,out); }
    HRESULT WINAPI CreateDBInstanceEx(REFCLSID c,IUnknown *o,DWORD x,LPOLESTR r,COSERVERINFO *s,ULONG n,MULTI_QI *q) override { return inner->CreateDBInstanceEx(c,o,x,r,s,n,q); }
    HRESULT WINAPI LoadStringFromStorage(LPCOLESTR f,LPOLESTR *s) override { return inner->LoadStringFromStorage(f,s); }
    HRESULT WINAPI WriteStringToStorage(LPCOLESTR f,LPCOLESTR s,DWORD d) override { return inner->WriteStringToStorage(f,s,d); }
};
class Factory : public IClassFactory {
    CLSID cls;
public:
    explicit Factory(REFCLSID id):cls(id) {}
    HRESULT WINAPI QueryInterface(REFIID id,void **out) override {
        if(!out) return E_POINTER; *out=nullptr;
        if(id==IID_IUnknown || id==IID_IClassFactory) { *out=this; return S_OK; } return E_NOINTERFACE;
    }
    ULONG WINAPI AddRef() override { return 2; }
    ULONG WINAPI Release() override { return 1; }
    HRESULT WINAPI CreateInstance(IUnknown *outer,REFIID id,void **out) override {
        if(!out) return E_POINTER; *out=nullptr;
        if(outer) return CLASS_E_NOAGGREGATION;
        auto fn=original_factory(); if(!fn) return E_FAIL;
        IClassFactory *factory=nullptr; IDataInitialize *inner=nullptr;
        HRESULT hr=fn(cls,IID_IClassFactory,reinterpret_cast<void**>(&factory));
        if(FAILED(hr)) return hr;
        if(id!=IID_IUnknown && id!=IID_IDataInitialize) {
            hr=factory->CreateInstance(nullptr,id,out); factory->Release(); return hr;
        }
        hr=factory->CreateInstance(nullptr,IID_IDataInitialize,reinterpret_cast<void**>(&inner)); factory->Release();
        if(FAILED(hr)) return hr;
        auto wrapper=new(std::nothrow) Initialize(inner);
        if(!wrapper) { inner->Release(); return E_OUTOFMEMORY; }
        hr=wrapper->QueryInterface(id,out); wrapper->Release(); return hr;
    }
    HRESULT WINAPI LockServer(BOOL) override { return S_OK; }
};
extern "C" __declspec(dllexport) HRESULT WINAPI DllGetClassObject(REFCLSID cls,REFIID id,void **out) {
    static Factory initialize(CLSID_MSDAINITIALIZE), links(CLSID_DataLinks);
    if(cls==CLSID_MSDAINITIALIZE) return initialize.QueryInterface(id,out);
    if(cls==CLSID_DataLinks) return links.QueryInterface(id,out);
    return CLASS_E_CLASSNOTAVAILABLE;
}
// Keep the shim loaded for the lifetime of the process, including delegated objects.
extern "C" __declspec(dllexport) HRESULT WINAPI DllCanUnloadNow() { return S_FALSE; }
