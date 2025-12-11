
from __future__ import annotations
import os, json, textwrap

TS_PACKAGE_JSON = '''{
  "name": "specdev-scaffold",
  "version": "0.1.0",
  "type": "module",
  "scripts": { "dev": "node src/server.js" },
  "dependencies": {}
}'''

SERVER_JS = '''// Generated scaffold (placeholder).
// Wire real validation in your runtime using your preferred stack.
import http from 'http';
const routes = new Map();
export function register(method, path, handler){ routes.set(method+':'+path, handler); }
export function start(port=8080){
  const server = http.createServer(async (req,res)=>{
    const key = (req.method||'GET')+':'+(req.url||'/');
    if(routes.has(key)){
      let body=''; for await (const chunk of req) body += chunk;
      const json = body ? JSON.parse(body) : {};
      const result = await routes.get(key)({body: json});
      res.writeHead(result.status||200, {'content-type':'application/json'});
      res.end(JSON.stringify(result.body||{}));
    } else { res.writeHead(404); res.end(); }
  });
  server.listen(port, ()=>console.log('listening on', port));
}
if (import.meta.url === `file://${process.argv[1]}`){ start(8080); }
'''

def generate_scaffold(spec_dir: str, out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    # read interface contracts and scaffold map
    apis = []
    route_map = []
    for root, _, files in os.walk(spec_dir):
        for fn in files:
            if fn.endswith(".json"):
                p = os.path.join(root, fn)
                try:
                    data = json.load(open(p, "r", encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                s = data.get("$schema","")
                if s.endswith("/05_interface_contracts.schema.json"):
                    apis.extend(data.get("apis", []))
                if s.endswith("/15_scaffold.schema.json"):
                    route_map.extend(data.get("route_map", []))

    # create simple Node scaffold
    src = os.path.join(out_dir, "src")
    os.makedirs(src, exist_ok=True)
    with open(os.path.join(out_dir, "package.json"), "w", encoding="utf-8") as f:
        f.write(TS_PACKAGE_JSON)
    with open(os.path.join(src, "server.js"), "w", encoding="utf-8") as f:
        f.write(SERVER_JS)

    # generate route handlers
    handlers = []
    for r in route_map:
        api_ref = r.get("api_ref")
        api = next((a for a in apis if a.get("api_id")==api_ref), None)
        if not api: 
            handlers.append(f"// WARN: route for unknown api_ref {api_ref}")
            continue
        method = r.get("method","GET")
        path = r.get("path","/")
        name = api.get("name","handler")
        js = f'''
import {{ register }} from './server.js';
register('{method}', '{path}', async (ctx)=>{{
  // TODO: validate ctx.body against {api.get('request_schema_ref','<req-schema>')}
  // TODO: enforce invariants
  // TODO: implement {name}
  return {{ status: 200, body: {{ "ok": true }} }};
}});'''
        handlers.append(js)
    with open(os.path.join(src, "routes.js"), "w", encoding="utf-8") as f:
        f.write("\n".join(handlers) if handlers else "// no routes defined")

    # index
    with open(os.path.join(src, "index.js"), "w", encoding="utf-8") as f:
        f.write("import './routes.js'; import { start } from './server.js'; start(8080);\n")

    return [os.path.join(out_dir, "package.json"), os.path.join(src,"server.js"), os.path.join(src,"routes.js"), os.path.join(src,"index.js")]
