import process from 'node:process';

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';

function printUsage(exitCode = 0) {
  // eslint-disable-next-line no-console
  console.error([
    'Usage: node mcp-call.mjs --url <http://host:port/mcp> --tool <toolName|__list_tools__> [--json <jsonArgs>]',
    '',
    'Examples:',
    "  node mcp-call.mjs --url http://localhost:3013/mcp --tool __list_tools__ --json '{}'",
    "  node mcp-call.mjs --url http://localhost:3014/mcp --tool search_code --json '{\"query\":\"where is ingest script\"}'",
    '',
  ].join('\n'));
  process.exitCode = exitCode;
}

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--'))
      continue;
    const key = a.slice(2);
    const next = argv[i + 1];
    if (next && !next.startsWith('--')) {
      args[key] = next;
      i++;
    } else {
      args[key] = true;
    }
  }
  return args;
}

function requireArg(args, name) {
  const v = args[name];
  if (v === undefined || v === true || v === '')
    throw new Error(`Missing required --${name}`);
  return v;
}

const args = parseArgs(process.argv);
if (args.help || args.h) {
  printUsage(0);
  process.exit(0);
}

let params;
let client;
let transport;

try {
  const url = requireArg(args, 'url');
  const tool = requireArg(args, 'tool');
  const json = args.json ?? '{}';

  try {
    params = JSON.parse(json);
  } catch (e) {
    // Powershell users often pass escaped JSON like: {\"k\":true}
    try {
      params = JSON.parse(json.replace(/\\"/g, '"'));
    } catch {
      throw new Error(`Invalid --json: ${e}`);
    }
  }

  client = new Client({ name: 'codex-op', version: '1.0.0' }, { capabilities: { tools: {} } });
  transport = new StreamableHTTPClientTransport(new URL(url));
  await client.connect(transport);

  if (tool === '__list_tools__') {
    const res = await client.listTools();
    // eslint-disable-next-line no-console
    console.log(JSON.stringify(res, null, 2));
  } else {
    const res = await client.callTool({ name: tool, arguments: params });
    // eslint-disable-next-line no-console
    console.log(JSON.stringify(res, null, 2));
  }

  process.exitCode = 0;
} catch (err) {
  // eslint-disable-next-line no-console
  console.error(err?.stack ?? String(err));
  printUsage(2);
} finally {
  // Gracefully close transports; avoids flaky Node/UV shutdown crashes on Windows.
  try {
    await client?.close?.();
  } catch {
    // ignore
  }
  try {
    await transport?.close?.();
  } catch {
    // ignore
  }
}
