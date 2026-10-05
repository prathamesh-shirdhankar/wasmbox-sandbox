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
  });

  const [loading, setLoading] = useState(false);

  const handleRun = async () => {
    setLoading(true);

    setOutput({
      status: "ok",
      stdout: "",
      stderr: "",
    });

    const result = await runCode(code);

    setOutput(result);
    setLoading(false);
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
              style={styles.runButton}
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