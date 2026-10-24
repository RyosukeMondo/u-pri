// Read-only compatibility check. Never output the machine identifier itself.
using System;
using System.IO;
using System.Text;
using System.Management;
using System.Security.Cryptography;
class IdentityProbe {
    static StringBuilder output=new StringBuilder();
    static void Error(string phase,Exception ex) {
        output.AppendLine(phase+"="+ex.GetType().FullName);
        if(ex.InnerException!=null) Error(phase+".inner",ex.InnerException);
        if(ex is System.Runtime.InteropServices.COMException) output.AppendLine("com_hresult="+((System.Runtime.InteropServices.COMException)ex).ErrorCode.ToString("X8"));
        if(ex is ManagementException) output.AppendLine("wmi_code="+((int)((ManagementException)ex).ErrorCode).ToString("X8"));
        var frames=new System.Diagnostics.StackTrace(ex).GetFrames();
        if(frames!=null) foreach(var frame in frames) {
            var method=frame.GetMethod(); output.AppendLine("frame="+method.DeclaringType.FullName+"."+method.Name);
        }
    }
    public static void Main(string[] args) {
        string directSerial=null;
        try {
            using(var disk=new ManagementObject("Win32_LogicalDisk=\"C:\"")) {
                object serial=disk.Properties["VolumeSerialNumber"].Value;
                directSerial=serial==null?null:serial.ToString();
                output.AppendLine("wmi_serial_present="+(serial!=null && serial.ToString().Length>0));
            }
        } catch(Exception ex) { Error("wmi_path",ex); }
        try {
            using(var query=new ManagementObjectSearcher("SELECT VolumeSerialNumber FROM Win32_LogicalDisk WHERE DeviceID='C:'"))
            using(var results=query.Get()) {
                output.AppendLine("wmi_query_count="+results.Count);
                foreach(ManagementObject disk in results) using(disk) {
                    object value=disk["VolumeSerialNumber"];
                    output.AppendLine("serial_matches_query="+(directSerial!=null && value!=null && directSerial==value.ToString()));
                }
            }
        } catch(Exception ex) { Error("wmi_query",ex); }
        try {
            using(var mac=new MACTripleDES()) output.AppendLine("mac_tripledes="+(mac.ComputeHash(new byte[]{1,2,3}).Length>0));
        } catch(Exception ex) { Error("mac_tripledes",ex); }
        File.WriteAllText(args[0],output.ToString(),Encoding.UTF8);
    }
}
