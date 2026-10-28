import { useState } from "react";
import CodeEditor from "./components/CodeEditor";
import OutputPanel from "./components/OutputPanel";
import { runCode } from "./api";

function App() {
  const [code, setCode] = useState(
    `print("Hello from Python!")
print("Wasmbox is working!")`
  );

  const [output, setOutput] = useState({
    status: "ok",
    stdout: "",
    stderr: "",
    exec_ms: 0,
    mem_bytes: 0,
  });

  const [loading, setLoading] = useState(false);

  const handleRun = async () => {
    // Prevent empty code submission
    if (!code.trim()) {
      setOutput({
        status: "error",
        stdout: "",
        stderr: "Please enter some Python code to run.",
        exec_ms: 0,
        mem_bytes: 0,
      });
      return;
    }

    setLoading(true);

    setOutput({
      status: "ok",
      stdout: "",
      stderr: "",
      exec_ms: 0,
      mem_bytes: 0,
    });

    try {
      const result = await runCode(code);

      setOutput({
        status: result.status ?? "error",
        stdout: result.stdout ?? "",
        stderr: result.stderr ?? "",
        exec_ms: result.exec_ms ?? 0,
        mem_bytes: result.mem_bytes ?? 0,
      });
    } catch (error) {
      setOutput({
        status: "error",
        stdout: "",
        stderr: "Unable to run code. Please check whether the backend is running.",
        exec_ms: 0,
        mem_bytes: 0,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <h1>Python Code Runner</h1>
        <p>Write Python code and run it</p>
      </header>

      <main style={styles.main}>
        <section style={styles.editorSection}>
          <div style={styles.sectionHeader}>
            <h2>Code Editor</h2>

            <button
              onClick={handleRun}
              disabled={loading}
              style={{
                ...styles.runButton,
                opacity: loading ? 0.7 : 1,
              }}
            >
              {loading ? "Running..." : "▶ Run"}
            </button>
          </div>

          <div style={styles.editor}>
            <CodeEditor
              code={code}
              setCode={setCode}
            />
          </div>
        </section>

        <OutputPanel output={output} />
      </main>
    </div>
  );
}

const styles = {
  page: {
    minHeight: "100vh",
    background: "#f5f5f5",
    color: "#222",
    fontFamily: "Arial, sans-serif",
    padding: "30px",
    boxSizing: "border-box",
  },

  header: {
    marginBottom: "25px",
    textAlign: "center",
  },

  main: {
    maxWidth: "1100px",
    margin: "0 auto",
  },

  editorSection: {
    background: "#fff",
    padding: "20px",
    borderRadius: "10px",
    marginBottom: "25px",
  },

  sectionHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "15px",
  },

  runButton: {
    background: "#2563eb",
    color: "#fff",
    border: "none",
    padding: "10px 20px",
    borderRadius: "6px",
    cursor: "pointer",
    fontSize: "15px",
  },

  editor: {
    borderRadius: "6px",
    overflow: "hidden",
  },
};

export default App;