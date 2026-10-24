// Open the installed app's database using its own configuration, read-only.
// Never output passwords, connection strings, or customer records.
using System;
using System.Data.OleDb;
using System.IO;
using System.Text;
using System.Xml;
class DbProbe {
    [System.Runtime.InteropServices.DllImport("upri_oledb_direct.dll", CharSet=System.Runtime.InteropServices.CharSet.Unicode, CallingConvention=System.Runtime.InteropServices.CallingConvention.Cdecl)]
    static extern int probe_open(string path, string password, out int stage);
    public static void Main(string[] args) {
        var output = new StringBuilder();
        string secret = "";
        try {
            output.AppendLine("process_bits=" + (IntPtr.Size * 8));
            string root = @"C:\ゆうプリR";
            var doc = new XmlDocument(); doc.Load(Path.Combine(root, @"Configuration\Settings.xml"));
            // Use the application's settings accessor: the XML value is not the effective value.
            var assembly = System.Reflection.Assembly.LoadFrom(Path.Combine(root, "420107Z01I01V01.DLL"));
            var settingsType = assembly.GetType("jp.jp_post.LabelPrintClient.Z01I01V01.Configuration.SysSettings", true);
            var settings = Activator.CreateInstance(settingsType);
            var passwordProperty = settingsType.GetProperty("AccessPassword");
            passwordProperty.SetValue(settings, doc.SelectSingleNode("//AccessPassword").InnerText, null);
            secret = (string)passwordProperty.GetValue(settings, null);
            var connection = new System.Data.Common.DbConnectionStringBuilder();
            connection["Provider"] = doc.SelectSingleNode("//AccessEngine").InnerText;
            string database = Path.Combine(root, doc.SelectSingleNode("//AccessFile").InnerText);
            connection["Data Source"] = database;
            connection["Jet OLEDB:Database Password"] = secret;
            connection["Mode"] = "Read";
            if(args.Length > 1) connection["OLE DB Services"] = -4;
            output.AppendLine("database_exists=" + File.Exists(database));
            if(args.Length > 1 && args[1] == "direct") {
                int stage;
                int result = probe_open(database, secret, out stage);
                output.AppendLine("direct_stage=" + stage);
                output.AppendLine("direct_hresult=" + result.ToString("X8"));
                File.WriteAllText(args[0], output.ToString(), Encoding.UTF8);
                return;
            }
            using(var db = new OleDbConnection(connection.ConnectionString)) {
                db.Open(); output.AppendLine("database_open=success");
            }
        } catch(Exception ex) {
            // Exception messages can contain connection strings. Emit types/codes only.
            output.AppendLine("exception_type=" + ex.GetType().FullName);
            var frames = new System.Diagnostics.StackTrace(ex).GetFrames();
            if(frames != null) foreach(var frame in frames) {
                var method = frame.GetMethod();
                output.AppendLine("frame=" + method.DeclaringType.FullName + "." + method.Name);
            }
            if(ex is OleDbException) {
                var error = (OleDbException)ex;
                output.AppendLine("HRESULT=" + error.ErrorCode.ToString("X8"));
                foreach(OleDbError item in error.Errors) {
                    int state;
                    output.AppendLine("native_error=" + item.NativeError);
                    if(Int32.TryParse(item.SQLState, out state)) output.AppendLine("sql_state=" + state);
                }
            }
        }
        File.WriteAllText(args[0], output.ToString(), Encoding.UTF8);
    }
}
