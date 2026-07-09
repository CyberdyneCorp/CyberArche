# Agent Python execution

## Why
Users want the agent to compute — run Python for data statistics (pandas/numpy),
simulate/verify code, and create plots that land in the document. CyberArche
already has an image block, a file upload/serve path, and tool-call surfacing;
Cyberdyne runs a Python Interpreter service
(`https://interpreter.backend.coolify.cyberdynecorp.ai`) that executes code in a
sandboxed session and returns stdout/result plus rich outputs (matplotlib
figures, DataFrame HTML). This change wires the agent to it.

## What Changes
- **Code-execution capability** (new): a `CodeExecutionPort` + a Cyberdyne
  Interpreter adapter that creates a session, runs code, and returns
  `{success, stdout, stderr, result, error, images, tables}`. Matplotlib figures
  are auto-captured (a savefig epilogue is appended when the code plots but does
  not save) and downloaded as bytes; DataFrame/HTML/JSON rich outputs are
  returned as text.
- **`run_python` agent tool**: executes Python; any figures are stored and
  inserted into the open document as image blocks (a CRDT peer edit, attributed
  to the agent), and stdout/result/errors are returned to the model to explain.
  Requires edit permission on the document. When the interpreter is not
  configured, the tool reports it is unavailable rather than failing the run.
- **Auth**: the adapter calls the interpreter with our CyberdyneAuth **service
  token** (client-credentials), the same seam the RAG adapter uses. Sessions are
  ephemeral (one per run) and figures are downloaded immediately, so the calling
  identity does not need per-user file persistence.
- **Config**: `CYBERARCHE_INTERPRETER_URL` (defaults to the production
  interpreter). Empty URL or no service token → the tool is disabled.

## Impact
- New spec: `code-execution`. Modified: `ai-agent` (agent runs Python).
- New code: `ports/code_exec.py`, `adapters/outbound/code_exec/`,
  `run_python` in `use_cases/agent.py`, wiring + config. Reuses the existing
  image block, `/files` serve route, and tool-call surfacing — **no frontend
  changes** (plots render as image blocks; the call shows in the tool list).
- Security: code runs in the interpreter's remote sandbox (`restricted` mode),
  not in our process; only workspace editors can invoke it; generated images go
  through the same membership-gated serve route as uploads.
