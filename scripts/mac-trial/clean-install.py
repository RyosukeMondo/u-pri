"""Fresh Mac-only portable setup experiment. Not a standard Windows MSI installation.
Requires the separately supplied own probes/adapters and Wine in --base.
"""
import pathlib,os,subprocess,time,json,atexit,zipfile,argparse,sys,shutil
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base',type=pathlib.Path,default=pathlib.Path('/Volumes/UpriTrial'))
parser.add_argument('--name',default='clean-install-20261025-verified')
parser.add_argument('--wine-bin',type=pathlib.Path)
parser.add_argument('--helpers',type=pathlib.Path)
parser.add_argument('--assets',type=pathlib.Path)
args=parser.parse_args()
if pathlib.Path(args.name).name!=args.name or args.name in ('.','..'):raise ValueError('Invalid trial name')
b=args.base.resolve();work=b/args.name
if work.exists():raise RuntimeError('Fresh setup refuses an existing work directory')
work.mkdir()
prefix=work/'prefix';logs=work/'logs';logs.mkdir(exist_ok=True)
r=args.wine_bin or b/'Wine Staging.app/Contents/Resources/wine/bin'
helpers=args.helpers or b/'downloads'
assets=args.assets or b/'official-fetch-test'
root=pathlib.Path(__file__).resolve().parents[2]
e=os.environ.copy();e.update(WINEPREFIX=str(prefix),WINEDEBUG='-all',LC_ALL='ja_JP.UTF-8',WINEDLLOVERRIDES='winemenubuilder.exe=d;mscoree,mscorwks=n;ngen.exe=n',MVK_CONFIG_LOG_LEVEL='0')
def stop():
 subprocess.run([str(r/'wineserver'),'-k'],env=e,timeout=20,check=True)
 subprocess.run([str(r/'wineserver'),'-w'],env=e,timeout=20,check=True)
def best_effort_stop():
 try:stop()
 except Exception as exc:print('cleanup_fallback_failed='+str(type(exc).__name__),flush=True)
atexit.register(best_effort_stop)
def run(args,name,timeout=120):
 t=time.monotonic()
 with (logs/(name+'.log')).open('wb') as f:
  try: code=subprocess.run([str(r/'wine')]+args,env=e,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired:stop();code=124
 print(json.dumps({'step':name,'exit':code,'seconds':round(time.monotonic()-t,1)}),flush=True)
 if code!=0:raise RuntimeError('Stage failed: '+name+' code='+str(code))
 return code
def win(p):return 'Z:'+str(p).replace('/','\\')
subprocess.run([sys.executable,str(root/'setup/fetch_official.py'),'fetch','--dir',str(assets)],check=True)
extract=work/'dotnet';extract.mkdir(exist_ok=True)
def unpack(source,target):
 if sys.platform=='darwin': subprocess.run(['/usr/bin/tar','-xf',str(source),'-C',str(target)],check=True)
 else: subprocess.run(['7z','x','-y','-o'+str(target),str(source)],check=True,stdout=subprocess.DEVNULL)
unpack(assets/'dotnetfx35.exe',extract)
appfiles=work/'app';appfiles.mkdir(exist_ok=True)
with zipfile.ZipFile(assets/'yuprir-x64.zip') as z:
 for item in z.infolist():
  if item.filename.lower().endswith('.msi'):
   (appfiles/'YprMDB_Setup_x64.msi').write_bytes(z.read(item))
run(['wineboot','-u'],'boot')
# Remove Wine Mono using its registered uninstall entry.
res=subprocess.run([str(r/'wine'),'uninstaller','--list'],env=e,capture_output=True,timeout=30)
for line in res.stdout.decode(errors='replace').splitlines():
 if 'Wine Mono' in line:run(['uninstaller','--remove',line.split('|')[0]],'remove-mono')
run(['winecfg','-v','winxp64'],'winxp64')
f=extract/'wcu/dotNetFramework/dotNetFX20'
patches=['ASPNET_64.msp','clr_64.msp','crt_64.msp','dw_64.msp','NetFX_Core_64.msp','NetFX_Other_64.msp','winforms_64.msp']
run(['msiexec','/i',win(f/'Netfx20a_x64.msi'),'ADDEPLOY=1','PATCH='+';'.join(win(f/p) for p in patches),'/qn','/norestart','/L*v',win(logs/'netfx-msi-detail.log')],'netfx20',240)
run(['winecfg','-v','win10'],'win10-before-gac')
run([win(helpers/'register-framework-gac.exe')],'framework-gac')
run([win(helpers/'mac-runtime-probe.exe'),win(logs/'runtime.txt')],'runtime-probe',30)
p=logs/'runtime.txt'
print('runtime_evidence='+ (p.read_text(encoding='utf-8-sig') if p.exists() else 'missing'),flush=True)
if not p.exists() or 'oledb_constructor=success' not in p.read_text(encoding='utf-8-sig'):
 print('installation_verified=false; blocked_stage=native_dotnet',flush=True);raise SystemExit(1)
run(['winecfg','-v','win10'],'win10')
net35=work/'net35';net35.mkdir()
unpack(extract/'wcu/dotNetFramework/dotNetFX35/x64/netfx35_x64.exe',net35)
run(['msiexec','/a',win(net35/'vs_setup.msi'),r'TARGETDIR=C:\upri-net35','/qn','/L*v',win(logs/'net35-admin-detail.log')],'net35-admin',120)
cores=list((prefix/'drive_c/upri-net35').rglob('System.Core.dll'))
if not cores:raise RuntimeError('No System.Core in official .NET3.5 administrative image')
for index,core in enumerate(cores):
 directory='C:\\'+str(core.parent.relative_to(prefix/'drive_c')).replace('/','\\')+'\\'
 run([win(helpers/'register-framework-gac.exe'),directory],'gac35-'+str(index))

run([win(assets/'accessdatabaseengine_X64.exe'),'/quiet','/norestart'],'access2016',180)
run(['msiexec','/a',win(appfiles/'YprMDB_Setup_x64.msi'),r'TARGETDIR=C:\ゆうプリR','/qn','/L*v',win(logs/'app-msi-detail.log')],'yuprir-admin-extract',180)
import shutil
for cls,dll in [('{2206CDB0-19C1-11D1-89E0-00C04FD7A829}','upri_ace_datainit.dll'),('{2206CDB2-19C1-11D1-89E0-00C04FD7A829}','upri_ace_datainit.dll'),('{CF4CC405-E2C5-4DDD-B3CE-5E7582D8C9FA}','upri_wmi_path.dll')]:
 shutil.copyfile(helpers/dll,prefix/'drive_c/windows/system32'/dll)
 key='HKLM\\Software\\Classes\\CLSID\\'+cls+'\\InprocServer32'
 run(['reg','add',key,'/ve','/d','C:\\windows\\system32\\'+dll,'/f','/reg:64'],'register-'+cls)
 run(['reg','add',key,'/v','ThreadingModel','/d','Both','/f','/reg:64'],'threading-'+cls)
run([win(helpers/'mac-db64.exe'),win(logs/'db.txt')],'database-probe')
run([win(helpers/'mac-identity.exe'),win(logs/'identity.txt')],'identity-probe')
for name in ['db.txt','identity.txt']:
 p=logs/name
 print(name+'='+(p.read_text(encoding='utf-8-sig') if p.exists() else 'missing'),flush=True)
with (logs/'registration.log').open('wb') as f:
 p=subprocess.Popen([str(r/'wine'),r'C:\ゆうプリR\420107Z02P04V02.exe'],cwd=prefix/'drive_c/ゆうプリR',env=e,stdout=f,stderr=subprocess.STDOUT)
 time.sleep(12)
run([win(helpers/'wine_ui_probe.exe'),'420107Z02P04V02.exe'],'registration-ui',20)
ui=(logs/'registration-ui.log').read_text(errors='replace')
db=(logs/'db.txt').read_text(encoding='utf-8-sig')
identity=(logs/'identity.txt').read_text(encoding='utf-8-sig')
result={'mode':'experimental_portable','standard_msi_install':False,'shipping_verified':False,
 'database_open':'database_open=success' in db,
 'identity_verified':all(x in identity for x in ['wmi_serial_present=True','serial_matches_query=True','mac_tripledes=True']),
 'authentication_screen':all(x in ui for x in ['matched_executable=420107Z02P04V02.exe','会員番号','パソコンID','認証']) and 'Application Error' not in ui}
result['portable_setup_verified']=all(result[k] for k in ['database_open','identity_verified','authentication_screen'])
stop()
atexit.unregister(best_effort_stop)
result['trial_processes_stopped']=True
(work/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False),flush=True)
if not result['portable_setup_verified']:raise SystemExit(1)
