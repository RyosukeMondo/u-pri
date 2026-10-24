// File-based GUI-subsystem probe: no console-host dependency, no database opened.
using System;
using System.IO;
using System.Data.OleDb;
class RuntimeProbe {
 [STAThread] static void Main(string[] args) {
  File.WriteAllText(args[0],"started=true\nCLR="+Environment.Version+"\nbits="+(IntPtr.Size*8)+"\n");
  try {using(var connection=new OleDbConnection()) {File.AppendAllText(args[0],"oledb_constructor=success\n");}}
  catch(Exception e){File.AppendAllText(args[0],"oledb_exception="+e.GetType().FullName+"\n");}
 }
}
