const USE_MOCK = true;

const API_BASE = "http://localhost:8000";

const mockPlugins = [];
let nextMockId = 1;

const delay = (ms = 300) =>
  new Promise((resolve) => setTimeout(resolve, ms));

export async function runCode(code) {
  if (USE_MOCK) {
    await delay();

    if (!code?.trim()) {
      return {
        status: "error",
        stdout: "",
        stderr: "No code provided",
        exec_ms: 0,
        mem_bytes: 0,
      };
    }

    return {
      status: "ok",
      stdout: "Mock mode: Python backend is not connected.\n",
      stderr: "",
      exec_ms: 0,
      mem_bytes: 0,
    };
  }

  try {
    const response = await fetch(`${API_BASE}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const detail = data.detail;
      const message =
        response.status === 422
          ? `Invalid request: ${
              typeof detail === "string"
                ? detail
                : Array.isArray(detail)
                  ? detail.map((item) => item.msg).join(", ")
                  : "Please check your input."
            }`
          : `Request failed (${response.status}).`;

      return {
        status: "error",
        stdout: "",
        stderr: message,
        exec_ms: null,
        mem_bytes: null,
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
  if (!name?.trim()) {
    throw new Error("Please enter a plugin name.");
  }

  if (USE_MOCK) {
    await delay();

    const plugin = {
      id: nextMockId++,
      name: name.trim(),
      code,
    };

    mockPlugins.push(plugin);
    return { ...plugin };
  }

  throw new Error(
    "Plugin API contract is not documented yet. Please confirm the endpoint format with the backend developer."
  );
}

export async function listPlugins() {
  if (USE_MOCK) {
    await delay();
    return mockPlugins.map(({ id, name }) => ({ id, name }));
  }

  throw new Error("Plugin list API contract is not documented yet.");
}

export async function loadPlugin(id) {
  if (USE_MOCK) {
    await delay();

    const plugin = mockPlugins.find(
      (item) => String(item.id) === String(id)
    );

    if (!plugin) {
      throw new Error("Plugin not found.");
    }

    return { ...plugin };
  }

  throw new Error("Plugin load API contract is not documented yet.");
}

export async function runWebhook(id) {
  if (USE_MOCK) {
    await delay();

    const plugin = mockPlugins.find(
      (item) => String(item.id) === String(id)
    );

    if (!plugin) {
      throw new Error("Please select a valid plugin first.");
    }

    return {
      status: "ok",
      stdout: `Mock webhook triggered for "${plugin.name}".`,
      stderr: "",
      exec_ms: 0,
      mem_bytes: 0,
      simulated: true,
    };
  }

  throw new Error("Webhook API contract is not documented yet.");
}