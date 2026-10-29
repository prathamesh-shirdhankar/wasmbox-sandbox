const API_BASE = "http://localhost:8000";

// Keep false to use the real backend.
// Change to true only when you intentionally want mock mode.
const MOCK_MODE = false;

const mockPlugins = [];
let nextMockId = 1;

const delay = (ms = 300) =>
  new Promise((resolve) => setTimeout(resolve, ms));

async function request(path, options = {}) {
  let response;

  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new Error(
      "Cannot connect to the backend. Make sure it is running at http://localhost:8000 and CORS is configured."
    );
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail.map((item) => item.msg).join(", ")
          : `Request failed with HTTP ${response.status}`;

    throw new Error(detail || `Request failed with HTTP ${response.status}`);
  }

  return data;
}

// Run Python code
export async function runCode(code) {
  if (MOCK_MODE) {
    await delay();

    if (!code?.trim()) {
      return {
        status: "error",
        stdout: "",
        stderr: "No code provided",
        exec_ms: 125,
        mem_bytes: null,
      };
    }

    if (code.includes("MOCK_TIMEOUT")) {
      return {
        status: "timeout",
        stdout: "",
        stderr: "Execution timed out (demo).",
        exec_ms: 1500,
        mem_bytes: null,
      };
    }

    if (code.includes("MOCK_ERROR")) {
      return {
        status: "error",
        stdout: "",
        stderr: "Example execution error (demo).",
        exec_ms: 125,
        mem_bytes: null,
      };
    }

    return {
      status: "ok",
      stdout: "Mock run completed successfully.",
      stderr: "",
      exec_ms: 125,
      mem_bytes: null,
    };
  }

  return request("/run", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

// Save a plugin
export async function savePlugin(name, code) {
  if (MOCK_MODE) {
    await delay();

    if (!name?.trim() || !code?.trim()) {
      throw new Error("Plugin name and code are required.");
    }

    const plugin = {
      id: String(nextMockId++),
      name: name.trim(),
      code,
    };

    mockPlugins.push(plugin);
    return { id: plugin.id, name: plugin.name };
  }

  return request("/plugins", {
    method: "POST",
    body: JSON.stringify({ name: name.trim(), code }),
  });
}

// List saved plugins
export async function listPlugins() {
  if (MOCK_MODE) {
    await delay();
    return mockPlugins.map(({ id, name }) => ({ id, name }));
  }

  const data = await request("/plugins");

  // Accept either a direct array or an object containing a plugin array.
  if (Array.isArray(data)) return data;
  if (Array.isArray(data.plugins)) return data.plugins;

  throw new Error("Unexpected response from GET /plugins.");
}

// Load a plugin by ID
export async function loadPlugin(id) {
  if (MOCK_MODE) {
    await delay();
    const plugin = mockPlugins.find((item) => String(item.id) === String(id));

    if (!plugin) throw new Error("Plugin not found.");

    return { ...plugin };
  }

  return request(`/plugins/${encodeURIComponent(id)}`);
}

// Run a saved plugin through the webhook endpoint
export async function runWebhook(id) {
  if (MOCK_MODE) {
    await delay();

    const plugin = mockPlugins.find((item) => String(item.id) === String(id));
    if (!plugin) throw new Error("Plugin not found.");

    return {
      status: "ok",
      stdout: `Mock webhook completed for ${plugin.name}.`,
      stderr: "",
      exec_ms: 125,
      mem_bytes: null,
    };
  }

  return request(`/webhooks/${encodeURIComponent(id)}`, {
    method: "POST",
  });
}