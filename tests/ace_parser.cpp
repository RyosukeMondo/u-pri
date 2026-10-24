// Windows test executable: no database, no real passwords, no registry writes.
#include "../compat/ace_datainit.cpp"
#include <cstdio>
static int failures=0;
static void check(bool ok,const char *name) { if(!ok) { ++failures; std::printf("FAIL %s\n",name); } }
static void test(const wchar_t *input,bool expected,const wchar_t *value,const wchar_t *clean,const char *name) {
    std::wstring result; Secret secret; bool found=false;
    HRESULT hr=strip_password(input,result,secret,found);
    check(SUCCEEDED(hr) && found==expected && (!found || (secret.value==value && result==clean)),name);
}
int main() {
    test(L"Provider=Microsoft.ACE.OLEDB.12.0;Data Source=C:\\O'Brien\\a.accdb;Jet OLEDB:Database Password=test;Mode=Read",true,L"test",L"Provider=Microsoft.ACE.OLEDB.12.0;Data Source=C:\\O'Brien\\a.accdb;Mode=Read","apostrophe path preserved");
    test(L"Provider=Microsoft.ACE.OLEDB.12.0;Jet OLEDB:Database Password='a;b';Mode=Read",true,L"a;b",L"Provider=Microsoft.ACE.OLEDB.12.0;Mode=Read","quoted semicolon");
    test(L"Provider=Microsoft.ACE.OLEDB.16.0;Jet OLEDB:Database Password=\"a\"\"b\"",true,L"a\"b",L"Provider=Microsoft.ACE.OLEDB.16.0;","doubled quote");
    test(L"Provider=Fake;Jet OLEDB:Database Password=test",false,L"",L"","unrelated provider passthrough");
    test(L"Provider=Fake;Data Source=C:\\O'Brien\\a.accdb",false,L"",L"","unrelated apostrophe passthrough");
    test(L"Provider='Microsoft.ACE.OLEDB.12.0';Jet OLEDB:Database Password=",true,L"",L"Provider='Microsoft.ACE.OLEDB.12.0';","empty password");
    test(L"Provider=Microsoft.ACE.OLEDB.12.0;Data Source=a.accdb",false,L"",L"","no target property");
    std::wstring clean; Secret secret; bool found;
    check(FAILED(strip_password(L"Provider=Microsoft.ACE.OLEDB.12.0;Jet OLEDB:Database Password=a;Jet OLEDB:Database Password=b",clean,secret,found)),"duplicate rejected for original parser");
    clean.clear();
    check(FAILED(strip_password(L"Provider=Microsoft.ACE.OLEDB.12.0;Jet OLEDB:Database Password=\"a\"b\"",clean,secret,found)),"malformed quoted suffix rejected for original parser");
    std::printf("parser_failures=%d\n",failures); return failures?1:0;
}
