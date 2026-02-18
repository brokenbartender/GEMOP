"""
Local MCP package.

This file exists to avoid conflicts with any third-party `mcp` packages that may be
installed in the Python environment. By making this directory a regular package,
`import mcp.*` resolves to this repo's implementation first.
"""

