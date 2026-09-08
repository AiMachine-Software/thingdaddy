#!/usr/bin/env bash
# Fails if the platform file is not valid TSX/JSX. Run before every commit.
set -e
cd "$(dirname "$0")"
if ! node -e "require('@babel/core')" 2>/dev/null; then
  echo "installing babel (one-time)…"
  npm i -D @babel/core @babel/preset-react @babel/preset-typescript >/dev/null 2>&1
fi
node -e "require('@babel/core').transformSync(require('fs').readFileSync('ThingDaddy_V4_Unified.jsx','utf8'),{filename:'f.tsx',presets:['@babel/preset-typescript','@babel/preset-react']});console.log('PARSE OK')"
