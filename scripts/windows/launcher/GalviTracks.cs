// GalviTracks.exe: um clique para instalar (se preciso), abrir o túnel dos celulares,
// subir o servidor e abrir o painel. Fechar a janela encerra tudo.
//
// Compilação: scripts\windows\launcher\compilar.bat (usa o csc.exe do .NET Framework 4,
// presente em todo Windows 10/11). Escrito em C# 5 por causa desse compilador.
//
// Opções: --sem-tunel (não abre o ngrok)  --sem-navegador (não abre o navegador)

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Threading;

[assembly: System.Reflection.AssemblyTitle("GalviTracks")]
[assembly: System.Reflection.AssemblyDescription("Rastreamento de motoboys em tempo real")]
[assembly: System.Reflection.AssemblyCompany("Galvitech Ltda")]
[assembly: System.Reflection.AssemblyProduct("GalviTracks")]
[assembly: System.Reflection.AssemblyVersion("1.0.0.0")]
[assembly: System.Reflection.AssemblyFileVersion("1.0.0.0")]

static class GalviTracks
{
    static string raiz;
    // Um job por processo filho; os handles ficam abertos enquanto esta janela existir.
    static readonly List<IntPtr> jobs = new List<IntPtr>();

    static int Main(string[] args)
    {
        try { Console.OutputEncoding = Encoding.UTF8; } catch { }
        Console.Title = "GalviTracks";
        raiz = AppDomain.CurrentDomain.BaseDirectory;
        Directory.SetCurrentDirectory(raiz);
        bool semTunel = Array.IndexOf(args, "--sem-tunel") >= 0;
        bool semNavegador = Array.IndexOf(args, "--sem-navegador") >= 0;

        Cabecalho();
        try
        {
            string python = PrepararAmbiente();
            Dictionary<string, string> env = LerEnv(Path.Combine(raiz, ".env"));
            string porta = Valor(env, "PORT", "5000");
            string urlPainel = "http://127.0.0.1:" + porta;

            if (Responde(urlPainel + "/api/health"))
            {
                Info("O GalviTracks já está aberto em outra janela. Abrindo o painel...");
                if (!semNavegador) AbrirNavegador(urlPainel);
                Thread.Sleep(2500);
                return 0;
            }

            string dominio = Valor(env, "NGROK_DOMAIN", "");
            Process tunel = semTunel ? null : IniciarTunel(dominio, porta);

            Etapa("Iniciando o servidor");
            Process servidor = Iniciar(Path.Combine(raiz, @".venv\Scripts\python.exe"),
                "run.py --no-browser --port " + porta, true);
            if (!AguardarServidor(urlPainel + "/api/health", servidor, 60))
            {
                Erro("O servidor não respondeu. Veja as mensagens acima.");
                Pausar();
                return 1;
            }
            Resumo(urlPainel, tunel != null && !tunel.HasExited ? dominio : null);
            if (!semNavegador) AbrirNavegador(urlPainel);

            servidor.WaitForExit();
            if (servidor.ExitCode != 0)
            {
                Erro("O servidor foi encerrado com erro (código " + servidor.ExitCode + ").");
                Pausar();
                return servidor.ExitCode;
            }
            return 0;
        }
        catch (Exception e)
        {
            Erro(e.Message);
            Pausar();
            return 1;
        }
    }

    // --- Ambiente Python ---------------------------------------------------
    static string PrepararAmbiente()
    {
        string venvPy = Path.Combine(raiz, @".venv\Scripts\python.exe");
        string marca = Path.Combine(raiz, @".venv\.galvitracks-deps");
        string hash = HashArquivo(Path.Combine(raiz, "requirements.txt"));
        bool primeiraVez = !File.Exists(venvPy);

        if (primeiraVez)
        {
            Etapa("Primeira execução: preparando o ambiente (leva alguns minutos, só desta vez)");
            string[] py = AcharPython();
            if (py == null)
            {
                Erro("Python 3.10 ou mais novo não foi encontrado neste computador.");
                Console.WriteLine("  Instale em https://www.python.org/downloads/ e marque \"Add python.exe to PATH\".");
                Console.WriteLine("  Depois abra o GalviTracks de novo.");
                AbrirNavegador("https://www.python.org/downloads/");
                throw new Exception("Instalação interrompida: Python ausente.");
            }
            Rodar(py[0], py[1] + "-m venv .venv", "Não foi possível criar o ambiente Python (.venv).");
        }

        if (!File.Exists(marca) || File.ReadAllText(marca).Trim() != hash)
        {
            Etapa("Instalando/atualizando as dependências");
            Rodar(venvPy, "-m pip install --disable-pip-version-check -q -r requirements.txt",
                "Falha ao instalar as dependências. Verifique a conexão com a internet.");
            File.WriteAllText(marca, hash);
        }

        CopiarSeFaltar(".env.example", ".env");
        CopiarSeFaltar(@"config\motoboys.example.json", @"config\motoboys.json");
        if (primeiraVez) Rodar(venvPy, @"scripts\seed_demo.py", null);
        return venvPy;
    }

    static string[] AcharPython()
    {
        // [executável, argumentos iniciais]
        string[][] candidatos = { new[] { "py", "-3 " }, new[] { "python", "" }, new[] { "python3", "" } };
        foreach (string[] c in candidatos)
        {
            try
            {
                var psi = new ProcessStartInfo(c[0], c[1] + "-c \"import sys; print(sys.version_info >= (3, 10))\"")
                {
                    UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true, CreateNoWindow = true
                };
                using (Process p = Process.Start(psi))
                {
                    string saida = p.StandardOutput.ReadToEnd();
                    p.WaitForExit(15000);
                    if (p.ExitCode == 0 && saida.Trim() == "True") return c;
                }
            }
            catch { /* não encontrado: tenta o próximo */ }
        }
        return null;
    }

    // --- Túnel ngrok -------------------------------------------------------
    static Process IniciarTunel(string dominio, string porta)
    {
        if (string.IsNullOrEmpty(dominio))
        {
            Aviso("Túnel para os celulares desligado (NGROK_DOMAIN vazio no .env). O painel funciona normalmente.");
            return null;
        }
        string ngrok = Path.Combine(raiz, @"tools\ngrok.exe");
        if (!File.Exists(ngrok)) ngrok = NoPath("ngrok.exe");
        if (ngrok == null)
        {
            Aviso("ngrok não encontrado (tools\\ngrok.exe). Os celulares não conseguirão enviar posições de fora da rede.");
            return null;
        }
        Etapa("Abrindo o túnel para os celulares (" + dominio + ")");
        string log = Path.Combine(raiz, @"data\ngrok.log");
        Directory.CreateDirectory(Path.GetDirectoryName(log));
        try { File.Delete(log); } catch { }
        Process p = Iniciar(ngrok, "http --domain=" + dominio + " " + porta + " --log \"" + log + "\"", false);
        Thread.Sleep(2500);
        if (p.HasExited)
        {
            Aviso("O túnel não abriu (talvez já esteja aberto em outro lugar). Detalhes em data\\ngrok.log.");
            return null;
        }
        return p;
    }

    // --- Processos ---------------------------------------------------------
    /// Inicia um processo filho preso ao "job" do GalviTracks: se esta janela fechar, ele fecha junto.
    static Process Iniciar(string exe, string argumentos, bool mesmaJanela)
    {
        var psi = new ProcessStartInfo(exe, argumentos)
        {
            UseShellExecute = false,
            CreateNoWindow = !mesmaJanela,
            WorkingDirectory = raiz,
        };
        psi.EnvironmentVariables["PYTHONUTF8"] = "1";
        Process p = Process.Start(psi);
        IntPtr job = CriarJob();
        if (job == IntPtr.Zero || !AssignProcessToJobObject(job, p.Handle))
            Aviso("Não foi possível vincular " + Path.GetFileName(exe) + " à janela (erro " + Marshal.GetLastWin32Error() + ").");
        else jobs.Add(job);
        return p;
    }

    static void Rodar(string exe, string argumentos, string erro)
    {
        Process p = Iniciar(exe, argumentos, true);
        p.WaitForExit();
        if (p.ExitCode != 0 && erro != null) throw new Exception(erro);
    }

    static bool AguardarServidor(string url, Process servidor, int segundos)
    {
        DateTime limite = DateTime.Now.AddSeconds(segundos);
        while (DateTime.Now < limite)
        {
            if (servidor.HasExited) return false;
            if (Responde(url)) return true;
            Thread.Sleep(400);
        }
        return false;
    }

    static bool Responde(string url)
    {
        try
        {
            var req = (HttpWebRequest)WebRequest.Create(url);
            req.Timeout = 1000;
            req.Proxy = null;
            using (var resp = (HttpWebResponse)req.GetResponse()) return resp.StatusCode == HttpStatusCode.OK;
        }
        catch { return false; }
    }

    static void AbrirNavegador(string url)
    {
        try { Process.Start(new ProcessStartInfo(url) { UseShellExecute = true }); } catch { }
    }

    static string NoPath(string nome)
    {
        string path = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (string pasta in path.Split(';'))
        {
            try
            {
                string c = Path.Combine(pasta.Trim(), nome);
                if (File.Exists(c)) return c;
            }
            catch { }
        }
        return null;
    }

    // --- Configuração ------------------------------------------------------
    static Dictionary<string, string> LerEnv(string caminho)
    {
        var d = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (!File.Exists(caminho)) return d;
        foreach (string linha in File.ReadAllLines(caminho))
        {
            string l = linha.Trim();
            if (l.Length == 0 || l.StartsWith("#")) continue;
            int i = l.IndexOf('=');
            if (i <= 0) continue;
            string v = l.Substring(i + 1);
            int comentario = v.IndexOf(" #");
            if (comentario >= 0) v = v.Substring(0, comentario);
            d[l.Substring(0, i).Trim()] = v.Trim().Trim('"');
        }
        return d;
    }

    static string Valor(Dictionary<string, string> env, string chave, string padrao)
    {
        string v = Environment.GetEnvironmentVariable(chave);
        if (!string.IsNullOrEmpty(v)) return v;
        return env.TryGetValue(chave, out v) && v.Length > 0 ? v : padrao;
    }

    static void CopiarSeFaltar(string origem, string destino)
    {
        string o = Path.Combine(raiz, origem), d = Path.Combine(raiz, destino);
        if (!File.Exists(d) && File.Exists(o)) File.Copy(o, d);
    }

    static string HashArquivo(string caminho)
    {
        using (var sha = SHA256.Create())
        using (var f = File.OpenRead(caminho))
            return BitConverter.ToString(sha.ComputeHash(f)).Replace("-", "");
    }

    // --- Mensagens ---------------------------------------------------------
    static void Cabecalho()
    {
        Console.ForegroundColor = ConsoleColor.Cyan;
        Console.WriteLine();
        Console.WriteLine("   GalviTracks · Rastreamento de motoboys");
        Console.ResetColor();
        Console.WriteLine("   Galvitech Ltda");
        Console.WriteLine();
    }

    static void Resumo(string painel, string dominio)
    {
        Console.WriteLine();
        Console.ForegroundColor = ConsoleColor.Green;
        Console.WriteLine("   ===================================================");
        Console.WriteLine("    GalviTracks está rodando");
        Console.WriteLine("   ===================================================");
        Console.ResetColor();
        Console.WriteLine("    Painel:    " + painel);
        if (dominio != null) Console.WriteLine("    Celulares: https://" + dominio + "/api/gps/owntracks");
        Console.WriteLine();
        Console.ForegroundColor = ConsoleColor.Yellow;
        Console.WriteLine("    Para encerrar, feche esta janela.");
        Console.ResetColor();
        Console.WriteLine();
    }

    static void Etapa(string msg) { Console.ForegroundColor = ConsoleColor.Cyan; Console.Write(" > "); Console.ResetColor(); Console.WriteLine(msg); }
    static void Info(string msg) { Console.WriteLine("   " + msg); }
    static void Aviso(string msg) { Console.ForegroundColor = ConsoleColor.Yellow; Console.WriteLine(" ! " + msg); Console.ResetColor(); }
    static void Erro(string msg) { Console.ForegroundColor = ConsoleColor.Red; Console.WriteLine(); Console.WriteLine(" X " + msg); Console.ResetColor(); }

    static void Pausar()
    {
        Console.WriteLine();
        Console.WriteLine("   Pressione Enter para fechar.");
        try { Console.ReadLine(); } catch { }
    }

    // --- Job object: filhos morrem junto com esta janela -------------------
    // Um job novo por processo: um job cujo único membro já terminou deixa de aceitar
    // novos processos (erro 87), o que acontecia na primeira execução após a instalação.
    static IntPtr CriarJob()
    {
        IntPtr job = CreateJobObject(IntPtr.Zero, null);
        if (job == IntPtr.Zero) return job;
        var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
        info.BasicLimitInformation.LimitFlags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        int tamanho = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
        IntPtr ptr = Marshal.AllocHGlobal(tamanho);
        try
        {
            Marshal.StructureToPtr(info, ptr, false);
            if (!SetInformationJobObject(job, 9, ptr, (uint)tamanho)) job = IntPtr.Zero; // 9 = ExtendedLimitInformation
        }
        finally { Marshal.FreeHGlobal(ptr); }
        return job;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateJobObject(IntPtr atributos, string nome);

    [DllImport("kernel32.dll")]
    static extern bool SetInformationJobObject(IntPtr job, int classe, IntPtr info, uint tamanho);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool AssignProcessToJobObject(IntPtr job, IntPtr processo);

    [StructLayout(LayoutKind.Sequential)]
    struct JOBOBJECT_BASIC_LIMIT_INFORMATION
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct IO_COUNTERS
    {
        public ulong ReadOperationCount, WriteOperationCount, OtherOperationCount;
        public ulong ReadTransferCount, WriteTransferCount, OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed;
        public UIntPtr PeakJobMemoryUsed;
    }
}
