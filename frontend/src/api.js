const USE_MOCK = false;

export async function runCode(code) {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 1000));

    return {
      status: "ok",
      stdout: "Hello from Python!\nWasmbox is working!\n",
      stderr: "",
      exec_ms: null,
      mem_bytes: null,
    };
  }

  try {
    const response = await fetch("http://localhost:8000/run", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ code }),
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      let message = "Request failed. Please try again.";

      if (response.status === 422) {
        const detail = data.detail?.[0]?.msg || data.detail;

        message = detail
          ? `Invalid request: ${
              typeof detail === "string"
                ? detail
                : JSON.stringify(detail)
            }`
          : "Invalid request";
      } else if (response.status >= 500) {
        message = "Server error. Please try again later.";
      }

      return {
        status: "error",
        stdout: data.stdout || "",
        stderr: message,
        exec_ms: data.exec_ms ?? null,
        mem_bytes: data.mem_bytes ?? null,
      };
    }

    return data;
  } catch {
    return {
      status: "error",
      stdout: "",
      stderr: "Cannot reach the server. Is the backend running?",
      exec_ms: null,
      mem_bytes: null,
    };
  }
}

export async function savePlugin(name, code) {
  if (!name.trim()) {
    throw new Error("Please enter a plugin name.");
  }

  try {
    const response = await fetch("http://localhost:8000/plugins", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name, code }),
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const detail = data.detail;
      const message = Array.isArray(detail)
        ? detail.map((item) => item.msg || JSON.stringify(item)).join(", ")
        : typeof detail === "string"
          ? detail
          : "Failed to save plugin.";

      throw new Error(
        response.status === 422
          ? `Invalid request: ${message}`
          : message
      );
    }

    return data;
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error("Cannot reach the server. Is the backend running?");
    }

    throw error;
  }
}