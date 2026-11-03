import { useEffect, useState } from "react";
import CodeEditor from "./components/CodeEditor";
import OutputPanel from "./components/OutputPanel";
import {
  runCode,
  savePlugin,
  listPlugins,
  loadPlugin,
  runWebhook,
} from "./api";

function App() {
  const [code, setCode] = useState(
    `print("Hello from Python!")
print("Wasmbox is working!")`
  );

  const [output, setOutput] = useState({
    status: "ready",
    stdout: "",
    stderr: "",
    exec_ms: null,
    mem_bytes: null,
  });

  const [loading, setLoading] = useState(false);
  const [pluginName, setPluginName] = useState("");
  const [savedPlugins, setSavedPlugins] = useState([]);
  const [selectedPluginId, setSelectedPluginId] = useState("");
  const [pluginMessage, setPluginMessage] = useState("");
  const [pluginError, setPluginError] = useState(false);
  const [webhookMessage, setWebhookMessage] = useState("");
  const [webhookError, setWebhookError] = useState(false);
  const [webhookLoading, setWebhookLoading] = useState(false);
  const [outputLabel, setOutputLabel] = useState("");

  async function refreshPlugins() {
    try {
      const plugins = await listPlugins();
      setSavedPlugins(Array.isArray(plugins) ? plugins : []);
    } catch (error) {
      setPluginError(true);
      setPluginMessage(error.message || "Unable to load plugins.");
    }
  }

  useEffect(() => {
    refreshPlugins();
  }, []);

  async function handleRun() {
    setLoading(true);
    setOutputLabel("");

    try {
      const result = await runCode(code);

      setOutput({
        status: result.status ?? "error",
        statusCode: result.statusCode,
        stdout: result.stdout ?? "",
        stderr: result.stderr ?? "",
        exec_ms: result.exec_ms ?? null,
        mem_bytes: result.mem_bytes ?? null,
      });
    } catch (error) {
      setOutput({
        status: "error",
        stdout: "",
        stderr: error.message || "Unable to run code.",
        exec_ms: null,
        mem_bytes: null,
      });
    } finally {
      setLoading(false);
    }
  }

  async function handleSavePlugin() {
    setPluginMessage("");
    setPluginError(false);

    if (!pluginName.trim()) {
      setPluginError(true);
      setPluginMessage("Please enter a plugin name.");
      return;
    }

    try {
      const plugin = await savePlugin(pluginName, code);

      if (plugin.id == null) {
        throw new Error("The saved plugin did not return an ID.");
      }

      setSelectedPluginId(String(plugin.id));
      setPluginMessage(
        `Saved "${plugin.name || pluginName.trim()}" (id ${plugin.id}).`
      );
      setPluginName("");
      await refreshPlugins();
    } catch (error) {
      setPluginError(true);
      setPluginMessage(error.message || "Failed to save plugin.");
    }
  }

  async function handleLoadPlugin(id) {
    setPluginMessage("");
    setPluginError(false);

    try {
      const plugin = await loadPlugin(id);

      if (typeof plugin.code !== "string") {
        throw new Error("The plugin does not contain code.");
      }

      setCode(plugin.code);
      setSelectedPluginId(String(plugin.id));
      setPluginMessage(`Loaded "${plugin.name}".`);
    } catch (error) {
      setPluginError(true);
      setPluginMessage(error.message || "Failed to load plugin.");
    }
  }

  async function handleWebhook() {
    setWebhookMessage("");
    setWebhookError(false);

    if (!selectedPluginId) {
      setWebhookError(true);
      setWebhookMessage("Please select or load a plugin first.");
      return;
    }

    setWebhookLoading(true);

    try {
      const result = await runWebhook(selectedPluginId);

      setOutput({
        status: result.status ?? "error",
        statusCode: result.statusCode,
        stdout: result.stdout ?? "",
        stderr: result.stderr ?? "",
        exec_ms: result.exec_ms ?? null,
        mem_bytes: result.mem_bytes ?? null,
      });

      setOutputLabel(
        result.simulated
          ? "Triggered by webhook (simulated)"
          : "Triggered by webhook"
      );

      if (result.status === "ok") {
        setWebhookMessage(
          result.simulated
            ? "Simulated webhook completed."
            : "Webhook completed."
        );
      } else {
        setWebhookError(true);
        setWebhookMessage("Webhook returned an error.");
      }
    } catch (error) {
      setWebhookError(true);
      setWebhookMessage(error.message || "Webhook failed.");

      setOutput({
        status: "error",
        stdout: "",
        stderr: error.message || "Webhook failed.",
        exec_ms: null,
        mem_bytes: null,
      });

      setOutputLabel("Webhook error");
    } finally {
      setWebhookLoading(false);
    }
  }

  function showDemoStatus(status) {
    const demoOutputs = {
      ok: {
        status: "ok",
        stdout: "Demo completed successfully.\n",
        stderr: "",
        exec_ms: 125,
        mem_bytes: null,
      },
      error: {
        status: "error",
        stdout: "",
        stderr: "Example execution error (demo).",
        exec_ms: 125,
        mem_bytes: null,
      },
      timeout: {
        status: "timeout",
        stdout: "",
        stderr: "Execution timed out (demo).",
        exec_ms: 1500,
        mem_bytes: null,
      },
    };

    setOutput(demoOutputs[status]);
    setOutputLabel("Demo status preview — not a real execution");
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
              style={styles.runButton}
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
                if (event.key === "Enter") handleSavePlugin();
              }}
              style={styles.input}
            />

            <button
              onClick={handleSavePlugin}
              style={styles.saveButton}
            >
              Save Plugin
            </button>

            <button
              onClick={refreshPlugins}
              style={styles.loadButton}
            >
              Refresh List
            </button>
          </div>

          {pluginMessage && (
            <p
              role="status"
              style={{
                ...styles.message,
                color: pluginError ? "#b91c1c" : "#166534",
              }}
            >
              {pluginMessage}
            </p>
          )}

          <h3>Saved Plugins ({savedPlugins.length})</h3>

          {savedPlugins.length === 0 ? (
            <p style={styles.description}>No saved plugins yet.</p>
          ) : (
            savedPlugins.map((plugin) => (
              <div key={plugin.id} style={styles.pluginRow}>
                <label style={styles.pluginLabel}>
                  <input
                    type="radio"
                    name="selectedPlugin"
                    checked={
                      String(selectedPluginId) === String(plugin.id)
                    }
                    onChange={() =>
                      setSelectedPluginId(String(plugin.id))
                    }
                  />
                  <strong>{plugin.name || `Plugin ${plugin.id}`}</strong>
                  <span style={styles.pluginId}>ID: {plugin.id}</span>
                </label>

                <button
                  onClick={() => handleLoadPlugin(plugin.id)}
                  style={styles.loadButton}
                >
                  Load
                </button>
              </div>
            ))
          )}

          <p style={styles.note}>
          </p>
        </section>

        <section style={styles.section}>
          <h2>Webhook</h2>
          <p style={styles.description}>
            Select a plugin above, then trigger its simulated webhook.
          </p>

          <button
            onClick={handleWebhook}
            disabled={webhookLoading}
            style={styles.saveButton}
          >
            {webhookLoading ? "Triggering..." : "Trigger Webhook"}
          </button>

          {webhookMessage && (
            <p
              role="status"
              style={{
                ...styles.message,
                color: webhookError ? "#b91c1c" : "#166534",
              }}
            >
              {webhookMessage}
            </p>
          )}
        </section>

        <section style={styles.section}>
          <h2>Demo Status Preview</h2>
          <p style={styles.description}>
            These buttons demonstrate output states; they do not run Python.
          </p>

          <div style={styles.controls}>
            <button
              onClick={() => showDemoStatus("ok")}
              style={styles.loadButton}
            >
              Preview Success
            </button>

            <button
              onClick={() => showDemoStatus("error")}
              style={styles.removeButton}
            >
              Preview Error
            </button>

            <button
              onClick={() => showDemoStatus("timeout")}
              style={styles.timeoutButton}
            >
              Preview Timed out
            </button>
          </div>
        </section>

        {outputLabel && (
          <p style={styles.outputLabel}>{outputLabel}</p>
        )}

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
  timeoutButton: {
    background: "#b45309",
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
  pluginLabel: {
    display: "flex",
    alignItems: "center",
    flexWrap: "wrap",
    gap: "10px",
  },
  pluginId: {
    color: "#666",
    fontSize: "12px",
  },
  description: {
    color: "#666",
    fontSize: "14px",
  },
  message: {
    fontSize: "14px",
  },
  note: {
    color: "#666",
    fontSize: "12px",
    marginTop: "18px",
  },
  outputLabel: {
    color: "#1d4ed8",
    fontSize: "14px",
    fontWeight: "bold",
  },
};

export default App;