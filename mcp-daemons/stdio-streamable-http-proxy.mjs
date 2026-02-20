import process from 'node:process';

import { randomUUID } from 'node:crypto';
import { createMcpExpressApp } from '@modelcontextprotocol/sdk/server/express.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import {
  CallToolRequestSchema,
  CompleteRequestSchema,
  GetPromptRequestSchema,
  ListPromptsRequestSchema,
  ListResourcesRequestSchema,
  ListResourceTemplatesRequestSchema,
  ListToolsRequestSchema,
  PingRequestSchema,
  ReadResourceRequestSchema,
  SubscribeRequestSchema,
  UnsubscribeRequestSchema,
  SetLevelRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith('--'))
      continue;
    const key = a.slice(2);
    const next = argv[i + 1];
    if (next && !next.startsWith('--')) {
      if (key === 'env') {
        if (!args.env)
          args.env = [];
        args.env.push(next);
        i++;
      } else {
        args[key] = next;
        i++;
      }
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
const port = parseInt(args.port ?? process.env.MCP_PORT ?? '3003', 10);
const endpoint = args.endpoint ?? '/mcp';
const command = requireArg(args, 'command');
const name = args.name ?? 'stdio-proxy';

const cmdArgs = [];
if (typeof args.args === 'string' && args.args.length) {
  // Split on spaces, but allow \"quoted segments\".
  // This is intentionally simple; prefer repeated --arg in the future if needed.
  const re = /"([^"]*)"|([^\s]+)/g;
  let m;
  while ((m = re.exec(args.args)) !== null) {
    cmdArgs.push(m[1] ?? m[2]);
  }
}

const env = {};
if (Array.isArray(args.env)) {
  for (const kv of args.env) {
    const idx = kv.indexOf('=');
    if (idx <= 0)
      throw new Error(`Invalid --env ${kv} (expected KEY=VALUE)`);
    env[kv.slice(0, idx)] = kv.slice(idx + 1);
  }
}

const downstream = new Client(
  { name: `${name}-client`, version: '1.0.0' },
  {
    // Be permissive; downstream tools/resources are authoritative.
    capabilities: {
      tools: {},
      resources: {},
      prompts: {},
      completions: {},
      logging: {},
    },
  }
);

const transport = new StdioClientTransport({
  command,
  args: cmdArgs,
  env,
  stderr: 'inherit',
});

// Connect in background so the HTTP server can start listening immediately.
let downstreamConnectError = null;
const downstreamReady = downstream.connect(transport).catch((err) => {
  downstreamConnectError = err;
  // eslint-disable-next-line no-console
  console.error('Downstream connect failed:', err);
  return null;
});

async function ensureDownstream(extra) {
  // Wait for stdio transport + MCP initialization to complete.
  await downstreamReady;
  if (downstreamConnectError) {
    throw downstreamConnectError;
  }
  return extra;
}

function createProxyServer() {
  const server = new Server(
    { name: `${name}-server`, version: '1.0.0' },
    {
      capabilities: {
        tools: { listChanged: true },
        resources: { listChanged: true, subscribe: true },
        prompts: { listChanged: true },
        completions: {},
        logging: {},
      },
    }
  );

  // Forward the common MCP surface.
  server.setRequestHandler(PingRequestSchema, async (_req, extra) => {
    await ensureDownstream(extra);
    return downstream.ping({ signal: extra.signal });
  });
  server.setRequestHandler(SetLevelRequestSchema, async (req, extra) => {
    await ensureDownstream(extra);
    return downstream.setLoggingLevel(req.params.level, { signal: extra.signal });
  });

  server.setRequestHandler(ListToolsRequestSchema, async (req, extra) => {
    await ensureDownstream(extra);
    return downstream.listTools(req.params, { signal: extra.signal });
  });
  server.setRequestHandler(CallToolRequestSchema, async (req, extra) => {
    await ensureDownstream(extra);
    return downstream.callTool(req.params, undefined, { signal: extra.signal });
  });

  server.setRequestHandler(CompleteRequestSchema, async (req, extra) => {
    await ensureDownstream(extra);
    return downstream.complete(req.params, { signal: extra.signal });
  });

  server.setRequestHandler(ListResourcesRequestSchema, async (req, extra) => {
    await ensureDownstream(extra);
    return downstream.listResources(req.params, { signal: extra.signal });
  });
  server.setRequestHandler(ListResourceTemplatesRequestSchema, async (req, extra) => {
    await ensureDownstream(extra);
    return downstream.listResourceTemplates(req.params, { signal: extra.signal });
  });
  server.setRequestHandler(ReadResourceRequestSchema, async (req, extra) => {
    await ensureDownstream(extra);
    return downstream.readResource(req.params, { signal: extra.signal });
  });
  server.setRequestHandler(SubscribeRequestSchema, async (req, extra) => {
    await ensureDownstream(extra);
    return downstream.subscribeResource(req.params, { signal: extra.signal });
  });
  server.setRequestHandler(UnsubscribeRequestSchema, async (req, extra) => {
    await ensureDownstream(extra);
    return downstream.unsubscribeResource(req.params, { signal: extra.signal });
  });

  server.setRequestHandler(ListPromptsRequestSchema, async (req, extra) => {
    await ensureDownstream(extra);
    return downstream.listPrompts(req.params, { signal: extra.signal });
  });
  server.setRequestHandler(GetPromptRequestSchema, async (req, extra) => {
    await ensureDownstream(extra);
    return downstream.getPrompt(req.params, { signal: extra.signal });
  });

  return server;
}

const app = createMcpExpressApp();

const transports = {};

const postHandler = async (req, res) => {
  const sessionId = req.headers['mcp-session-id'];
  try {
    let t = sessionId ? transports[sessionId] : undefined;

    // New session only allowed via initialize request.
    if (!t) {
      // sdk helper in types.js
      // Avoid importing isInitializeRequest to keep dependencies minimal; just check shape.
      const body = req.body;
      const isInit = body && body.jsonrpc === '2.0' && body.method === 'initialize';
      if (!isInit) {
        res.status(400).json({
          jsonrpc: '2.0',
          error: { code: -32000, message: 'Bad Request: No valid session ID provided' },
          id: null,
        });
        return;
      }

      t = new StreamableHTTPServerTransport({
        sessionIdGenerator: () => randomUUID(),
        onsessioninitialized: (sid) => {
          transports[sid] = t;
        },
      });

      t.onclose = () => {
        const sid = t.sessionId;
        if (sid && transports[sid])
          delete transports[sid];
      };

      const proxyServer = createProxyServer();
      await proxyServer.connect(t);
      await t.handleRequest(req, res, body);
      return;
    }

    await t.handleRequest(req, res, req.body);
  } catch (err) {
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: '2.0',
        error: { code: -32603, message: 'Internal server error' },
        id: null,
      });
    }
  }
};

const getHandler = async (req, res) => {
  const sessionId = req.headers['mcp-session-id'];
  if (!sessionId || !transports[sessionId]) {
    res.status(400).send('Invalid or missing session ID');
    return;
  }
  await transports[sessionId].handleRequest(req, res);
};

const deleteHandler = async (req, res) => {
  const sessionId = req.headers['mcp-session-id'];
  if (!sessionId || !transports[sessionId]) {
    res.status(400).send('Invalid or missing session ID');
    return;
  }
  await transports[sessionId].handleRequest(req, res);
};

app.post(endpoint, postHandler);
app.get(endpoint, getHandler);
app.delete(endpoint, deleteHandler);

app.listen(port, (error) => {
  if (error) {
    // eslint-disable-next-line no-console
    console.error('Failed to start proxy server:', error);
    process.exit(1);
  }
  // eslint-disable-next-line no-console
  console.log(`MCP stdio proxy '${name}' listening on http://127.0.0.1:${port}${endpoint}`);
  // eslint-disable-next-line no-console
  console.log(`Downstream: ${command} ${cmdArgs.join(' ')}`);
});

process.on('SIGINT', async () => {
  try {
    for (const sid of Object.keys(transports)) {
      try {
        await transports[sid].close();
      } catch {
        // ignore
      }
      delete transports[sid];
    }
  } finally {
    try {
      await downstream.close();
    } catch {
      // ignore
    }
    process.exit(0);
  }
});

process.on('unhandledRejection', (reason) => {
  // Keep proxy alive; request handlers already surface downstream errors.
  // eslint-disable-next-line no-console
  console.error('Unhandled rejection:', reason);
});
