const USE_MOCK = false;

export async function runCode(code) {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 1000));

    return {
      status: "ok",
      stdout: "Hello from Python!\nWasmbox is working!\n",
      stderr: "",
      exec_ms: 0,
      mem_bytes: 0,
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
        message =
          data.detail?.[0]?.msg ||
          data.detail ||
          "Invalid request. Please check your Python code.";
      } else if (response.status >= 500) {
        message = "Server error. Please try again later.";
      }

      return {
        status: "error",
        stdout: data.stdout || "",
        stderr:
          typeof message === "string" ? message : JSON.stringify(message),
        exec_ms: data.exec_ms || 0,
        mem_bytes: data.mem_bytes || 0,
      };
    }

    return data;
  } catch (error) {
    return {
      status: "error",
      stdout: "",
      stderr: "Cannot reach the server. Is the backend running?",
      exec_ms: 0,
      mem_bytes: 0,
    };
  }
}