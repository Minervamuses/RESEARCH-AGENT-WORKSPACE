import type { BoundedRuntimeDiagnostics } from "../backend.ts";

function configuredLabel(value: boolean): string {
  return value ? "Configured" : "Not configured";
}

export function RuntimeDetails({ diagnostics }: { diagnostics: BoundedRuntimeDiagnostics }) {
  return (
    <details className="runtime-details">
      <summary>Local runtime details</summary>
      <dl>
        <div><dt>Python</dt><dd>{diagnostics.pythonVersion}</dd></div>
        <div><dt>Backend</dt><dd>{diagnostics.backendVersion}</dd></div>
        <div><dt>Protocol</dt><dd>v{diagnostics.protocolVersion}</dd></div>
        <div><dt>Conda environment</dt><dd>{diagnostics.condaEnvironment ?? "Not detected"}</dd></div>
        <div><dt>OpenRouter</dt><dd>{configuredLabel(diagnostics.openRouterConfigured)}</dd></div>
        <div><dt>OpenAlex</dt><dd>{configuredLabel(diagnostics.openAlexConfigured)}</dd></div>
        <div><dt>MCP</dt><dd>{diagnostics.mcpEnabled ? "Enabled" : "Disabled"}</dd></div>
        <div className="wide-detail"><dt>MCP families</dt><dd>{diagnostics.mcpFamilies.length > 0 ? diagnostics.mcpFamilies.join(", ") : "None"}</dd></div>
        <div className="wide-detail"><dt>App root</dt><dd>{diagnostics.appRoot}</dd></div>
        <div className="wide-detail"><dt>Working directory</dt><dd>{diagnostics.workingDirectory}</dd></div>
        <div className="wide-detail"><dt>Conda prefix</dt><dd>{diagnostics.condaPrefix ?? "Not detected"}</dd></div>
        <div className="wide-detail"><dt>Research store</dt><dd>{diagnostics.storePath}</dd></div>
      </dl>
    </details>
  );
}
