function OutputPanel({ output = {} }) {
  const statusLabels = {
    ok: "Success",
    error: "Error",
    denied: "Denied",
    timeout: "Timed out",
    memory_exceeded: "Memory Exceeded",
  };

  const status = output.status || "ready";
  const statusLabel = statusLabels[status] || "Ready";
  const statusColor =
    status === "ok"
      ? "#15803d"
      : status === "timeout"
      ? "#b45309"
      : ["error", "denied", "memory_exceeded"].includes(status)
      ? "#b91c1c"
      : "#475569";

  const isServerUnavailable =
    output.stderr?.toLowerCase().includes("cannot reach the server");

  const isInvalidRequest =
    output.statusCode === 422 || output.status === "invalid_request";

  return (
    <section style={styles.outputSection}>
      <h2>Output</h2>

      <div
        style={{
          ...styles.status,
          color: statusColor,
          borderLeft: `5px solid ${statusColor}`,
        }}
      >
        Status: <strong>{statusLabel}</strong>
      </div>

      {output.exec_ms !== undefined && (
        <p style={styles.info}>
          Execution time: {output.exec_ms} ms
        </p>
      )}

      <p style={styles.info}>
        Memory: not measured yet
      </p>

      {isServerUnavailable && (
        <p style={styles.warning}>Cannot reach the server.</p>
      )}

      {isInvalidRequest && (
        <p style={styles.warning}>Invalid request. Please check your input.</p>
      )}

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
  info: {
    color: "#333",
    margin: "8px 0",
  },
  warning: {
    color: "#b45309",
    background: "#fff7ed",
    padding: "10px",
    borderRadius: "5px",
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
    whiteSpace: "pre-wrap",
  },
};

export default OutputPanel;