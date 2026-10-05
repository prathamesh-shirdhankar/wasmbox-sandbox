import Editor from "@monaco-editor/react";

function CodeEditor({ code, setCode }) {
  return (
    <Editor
      height="450px"
      defaultLanguage="python"
      value={code}
      onChange={(value) => setCode(value || "")}
      theme="vs-dark"
      options={{
        minimap: { enabled: false },
        fontSize: 15,
      }}
    />
  );
}

export default CodeEditor;