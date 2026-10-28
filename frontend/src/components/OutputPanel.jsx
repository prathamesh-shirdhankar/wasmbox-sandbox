function OutputPanel({ output = {} }) {
  const statusLabels = {
    ok: "Success",
    error: "Error",
    denied: "Denied",
    timeout: "Timeout",
    memory_exceeded: "Memory Exceeded",
  };

  return (
    <section style={styles.outputSection}>
      <h2>Output</h2>

      <div style={styles.status}>
        Status: <strong>{statusLabels[output.status] || output.status}</strong>
      </div>

      <div style={styles.outputBox}>
        <h3>stdout</h3>
        <pre>{output.stdout || "No output yet."}</pre>
      </div>

      {output.stderr && (
        <div style={styles.errorBox}>
          <h3>stderr</h3>
          <pre>{output.stderr}</pre>
        </div>
      )}

      {(output.exec_ms !== undefined ||
        output.mem_bytes !== undefined) && (
        <small>
          Execution time: {output.exec_ms ?? 0} ms | Memory: not measured yet
        </small>
      )}
    </section>
  );
}

const styles = {
  outputSection: {
    background: "#fff",
    padding: "20px",
    borderRadius: "10px",
  },

  status: {
    padding: "10px",
    background: "#eee",
    borderRadius: "5px",
    marginBottom: "15px",
  },

  outputBox: {
    background: "#111",
    color: "#fff",
    padding: "15px",
    borderRadius: "6px",
    marginBottom: "15px",
    textAlign: "left",
  },

  errorBox: {
    background: "#fff0f0",
    color: "#900",
    padding: "15px",
    borderRadius: "6px",
    textAlign: "left",
  },
};

export default OutputPanel;