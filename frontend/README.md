# Theia NG — frontend

Angular source for the Theia NG admin SPA.

**Toolchain:** Angular 22, TypeScript 6.0, zoneless change detection (no zone.js;
signals drive rendering). Requires **Node ≥ 22.22.3 / 24.15 / 26** (Angular 22
CLI hard-requirement). Use `nvm use 24` if your default Node is older.

This is a skeleton. To turn it into a runnable Angular workspace, scaffold with
the Angular CLI (`ng new`) over this directory or wire up `angular.json`,
`tsconfig.json`, and `src/main.ts`/`src/app/app.component.ts`. The pieces that
are intentional and load-bearing:

- **`src/app/theia-config.ts`** — reads `window.__THEIA_NG_CONFIG__`, injected by
  Django at serve time. This is what makes the built bundle prefix-independent.
- **`proxy.conf.json`** — dev-server proxy so `npm start` talks to a Django
  backend on `localhost:8000`.
- **`package.json` `build` script** — outputs to `dist/theia-ng/browser/`, which
  the Python build hook (`hatch_build.py`) copies into
  `theia_ng/static/theia_ng/`.

The SPA consumes the IR from:
- `GET <apiBase>schema/` — registry / nav
- `GET <apiBase>schema/<app.model>/` — per-model descriptor
