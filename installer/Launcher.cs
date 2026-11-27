// Stereo3DStudio.exe - native launcher for the Stereo3D Studio GPU runtime.
// Starts the bundled Python runtime hidden, captures everything it prints to
// %LOCALAPPDATA%\Stereo3DStudio\logs\boot.log, and shows a message if it fails.
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("Stereo3DStudio")]
[assembly: System.Reflection.AssemblyProduct("Stereo3DStudio")]
[assembly: System.Reflection.AssemblyCompany("Drew Medina - drewmedina.com")]
[assembly: System.Reflection.AssemblyDescription("2D to 3D image and video converter")]
[assembly: System.Reflection.AssemblyVersion("1.4.0.0")]
[assembly: System.Reflection.AssemblyFileVersion("1.4.0.0")]

static class Launcher
{
    static StreamWriter boot;
    static readonly object bootLock = new object();

    static void Log(string s)
    {
        lock (bootLock)
        {
            try { if (boot != null) { boot.WriteLine(s); boot.Flush(); } } catch { }
        }
    }

    static string Tail(string file, int chars)
    {
        try
        {
            string t;
            using (var fs = new FileStream(file, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
            using (var sr = new StreamReader(fs)) t = sr.ReadToEnd();
            return t.Length > chars ? "..." + t.Substring(t.Length - chars) : t;
        }
        catch { return "(log unavailable)"; }
    }

    [STAThread]
    static int Main(string[] args)
    {
        string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        string logDir = Path.Combine(local, @"Stereo3DStudio\logs");
        string bootPath = Path.Combine(logDir, "boot.log");
        try
        {
            Directory.CreateDirectory(logDir);
            boot = new StreamWriter(new FileStream(bootPath, FileMode.Create, FileAccess.Write, FileShare.ReadWrite), new UTF8Encoding(false));
        }
        catch { }

        string py = Path.Combine(root, @"runtime\Scripts\python.exe");
        Log("Stereo3D Studio launcher " + DateTime.Now.ToString("s"));
        Log("root: " + root);
        Log("python: " + py);

        if (!File.Exists(py))
        {
            Log("python.exe missing");
            MessageBox.Show(
                "Stereo3D Studio's GPU runtime isn't installed in this folder.\n\n" +
                "Run \"Install Stereo3D Studio.bat\" first (or re-run it if this folder was moved).",
                "Stereo3D Studio", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return 1;
        }

        var sb = new StringBuilder("-X utf8 -m stereo3dstudio");
        foreach (string a in args)
            sb.Append(" \"").Append(a.Replace("\"", "\\\"")).Append('"');

        var psi = new ProcessStartInfo(py, sb.ToString());
        psi.UseShellExecute = false;
        psi.CreateNoWindow = true;
        psi.WorkingDirectory = root;
        psi.RedirectStandardOutput = true;
        psi.RedirectStandardError = true;
        psi.StandardOutputEncoding = Encoding.UTF8;
        psi.StandardErrorEncoding = Encoding.UTF8;
        psi.EnvironmentVariables["PYTHONPATH"] = Path.Combine(root, "app") + ";" + Path.Combine(root, "engine");
        psi.EnvironmentVariables["PYTHONNOUSERSITE"] = "1";
        psi.EnvironmentVariables["PYTHONUTF8"] = "1";
        psi.EnvironmentVariables["PYTHONFAULTHANDLER"] = "1";
        psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";
        psi.EnvironmentVariables["STEREOSTUDIO_LAUNCHER"] = "1";
        psi.EnvironmentVariables.Remove("PYTHONHOME");
        Log("args: " + sb);

        Process p;
        try
        {
            p = new Process();
            p.StartInfo = psi;
            p.OutputDataReceived += (s, e) => { if (e.Data != null) Log(e.Data); };
            p.ErrorDataReceived += (s, e) => { if (e.Data != null) Log(e.Data); };
            p.Start();
            p.BeginOutputReadLine();
            p.BeginErrorReadLine();
        }
        catch (Exception e)
        {
            Log("start failed: " + e);
            MessageBox.Show("Could not start Stereo3D Studio:\n" + e.Message + "\n\nLog: " + bootPath, "Stereo3D Studio",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }

        p.WaitForExit();
        p.WaitForExit(2000); // flush async readers
        int code = p.ExitCode;
        Log("exit code: " + code);
        if (code != 0)
        {
            MessageBox.Show(
                "Stereo3D Studio closed with an error (code " + code + ").\n\n" + Tail(bootPath, 1800) +
                "\n\nFull log: " + bootPath,
                "Stereo3D Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        return code;
    }
}
