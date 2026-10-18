const USE_MOCK = true;

export async function runCode(code) {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 1000));

    return {
      status: "ok",
      stdout: "Heello from Python!\nWasmbox is working!\n",
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

    return await response.json();
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