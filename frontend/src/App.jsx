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
    exec_ms: null,
    mem_bytes: null,
  });

  const [loading, setLoading] = useState(false);
  const [pluginName, setPluginName] = useState("");
  const [savedPlugins, setSavedPlugins] = useState([]);
  const [message, setMessage] = useState("");

  async function handleRun() {
    if (!code.trim()) {
      setOutput({
        status: "error",
        stdout: "",
        stderr: "Please enter some Python code to run.",
        exec_ms: null,
        mem_bytes: null,
      });
      return;
    }

    setLoading(true);

    try {
      const result = await runCode(code);

      setOutput({
        status: result.status ?? "error",
        stdout: result.stdout ?? "",
        stderr: result.stderr ?? "",
        exec_ms: result.exec_ms ?? null,
        mem_bytes: result.mem_bytes ?? null,
      });
    } catch {
      setOutput({
        status: "error",
        stdout: "",
        stderr: "Unable to run code. Please check whether the backend is running.",
        exec_ms: null,
        mem_bytes: null,
      });
    } finally {
      setLoading(false);
    }
  }

  function handleSavePlugin() {
    const name = pluginName.trim();

    if (!name) {
      setMessage("Please enter a plugin name.");
      return;
    }

    if (savedPlugins.some((plugin) => plugin.name === name)) {
      setMessage("A plugin with this name already exists.");
      return;
    }

    setSavedPlugins((previous) => [
      ...previous,
      {
        id: `${Date.now()}-${name}`,
        name,
        code,
      },
    ]);

    setPluginName("");
    setMessage(`"${name}" saved successfully.`);
  }

  function handleLoadPlugin(plugin) {
    setCode(plugin.code);
    setMessage(`Loaded "${plugin.name}".`);
  }

  function handleRemovePlugin(id) {
    setSavedPlugins((previous) =>
      previous.filter((plugin) => plugin.id !== id)
    );
    setMessage("Plugin removed.");
  }

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <h1>Python Code Runner</h1>
        <p>Write Python code and run it</p>
      </header>

      <main style={styles.main}>
        <section style={styles.section}>
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
            <CodeEditor code={code} setCode={setCode} />
          </div>
        </section>

        <section style={styles.section}>
          <h2>Plugin Manager</h2>
          <p style={styles.description}>
            Save your Python code as a plugin and load it later.
          </p>

          <div style={styles.controls}>
            <input
              type="text"
              placeholder="Enter plugin name"
              value={pluginName}
              onChange={(event) => setPluginName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  handleSavePlugin();
                }
              }}
              style={styles.input}
            />

            <button
              onClick={handleSavePlugin}
              style={styles.saveButton}
            >
              Save Plugin
            </button>
          </div>

          {message && (
            <p role="status" style={styles.message}>
              {message}
            </p>
          )}

          <h3>Saved Plugins ({savedPlugins.length})</h3>

          {savedPlugins.length === 0 ? (
            <p style={styles.description}>No saved plugins yet.</p>
          ) : (
            savedPlugins.map((plugin) => (
              <div key={plugin.id} style={styles.pluginRow}>
                <strong>{plugin.name}</strong>

                <div style={styles.controls}>
                  <button
                    onClick={() => handleLoadPlugin(plugin)}
                    style={styles.loadButton}
                  >
                    Load
                  </button>

                  <button
                    onClick={() => handleRemovePlugin(plugin.id)}
                    style={styles.removeButton}
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))
          )}

          <p style={styles.note}>
            Demo mode: plugins are stored temporarily and disappear when the
            page is refreshed.
          </p>
        </section>
        <section style={styles.section}>
  <h2>Webhook</h2>
  <p style={styles.description}>
    Trigger a demo webhook action.
  </p>

  <button
    onClick={() => {
      setMessage("Webhook demo triggered successfully.");
    }}
    style={styles.saveButton}
  >
    Trigger Webhook
  </button>

  {message && (
    <p role="status" style={styles.message}>
      {message}
    </p>
  )}
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

  section: {
    background: "#fff",
    padding: "20px",
    borderRadius: "10px",
    marginBottom: "25px",
    boxShadow: "0 2px 8px rgba(0, 0, 0, 0.05)",
  },

  sectionHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "12px",
    marginBottom: "15px",
  },

  editor: {
    borderRadius: "6px",
    overflow: "hidden",
  },

  controls: {
    display: "flex",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "10px",
    margin: "12px 0",
  },

  input: {
    flex: "1",
    minWidth: "180px",
    padding: "10px",
    border: "1px solid #ccc",
    borderRadius: "6px",
    fontSize: "14px",
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

  saveButton: {
    background: "#15803d",
    color: "#fff",
    border: "none",
    padding: "10px 16px",
    borderRadius: "6px",
    cursor: "pointer",
  },

  loadButton: {
    background: "#2563eb",
    color: "#fff",
    border: "none",
    padding: "8px 12px",
    borderRadius: "5px",
    cursor: "pointer",
  },

  removeButton: {
    background: "#dc2626",
    color: "#fff",
    border: "none",
    padding: "8px 12px",
    borderRadius: "5px",
    cursor: "pointer",
  },

  pluginRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "12px",
    padding: "12px",
    border: "1px solid #ddd",
    borderRadius: "6px",
    marginBottom: "10px",
  },

  description: {
    color: "#666",
    fontSize: "14px",
  },

  message: {
    color: "#166534",
    fontSize: "14px",
  },

  note: {
    color: "#666",
    fontSize: "12px",
    marginTop: "18px",
  },
};

export default App;