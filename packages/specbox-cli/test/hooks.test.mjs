// UC-11201 — `specbox hooks status | update`: los hooks del proyecto frente a los
// publicados, sin pisar los que se cambiaron en local.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { run } from "../bin/specbox.mjs";
import { REGISTRY, hooksStatus, loadPackaged, updateHooks } from "../lib/hooks.mjs";
import { runInternal } from "../lib/internal.mjs";
import { ENGINE_ROOT, hookFiles, packHooks } from "../scripts/pack-hooks.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const sha = (s) => createHash("sha256").update(s).digest("hex");

function write(root, rel, content) {
  mkdirSync(dirname(join(root, rel)), { recursive: true });
  writeFileSync(join(root, rel), content);
}

const TEMPLATE = {
  hooks: {
    PreToolUse: [{ matcher: "Write", hooks: [{ type: "command", command: "node .claude/hooks/a.mjs", timeout: 5 }] }],
    PostToolUse: [{ matcher: "Read", hooks: [{ type: "command", command: "node .claude/hooks/c.mjs", timeout: 3 }] }],
  },
};

/** Un engine de juguete con una etiqueta v6.20.0 (a.mjs antiguo) y su versión actual empaquetada. */
function packagedFixture() {
  const engine = mkdtempSync(join(tmpdir(), "specbox-engine-"));
  const git = (...a) => execFileSync("git", ["-C", engine, ...a], { stdio: "ignore" });
  git("init", "-q");
  git("config", "user.email", "t@t");
  git("config", "user.name", "t");
  write(engine, ".claude/hooks/a.mjs", "// a v1\n");
  write(engine, ".claude/hooks/b.mjs", "// b v1\n");
  write(engine, ".claude/hooks/c.mjs", "// c\n");
  write(engine, ".claude/hooks/lib/x.mjs", "// x v1\n");
  write(engine, ".claude/hooks/lib/x.test.mjs", "// prueba: no se publica\n");
  write(engine, "templates/settings.json.template", JSON.stringify(TEMPLATE));
  git("add", "-A");
  git("commit", "-qm", "6.20.0");
  git("tag", "v6.20.0");
  write(engine, ".claude/hooks/a.mjs", "// a v2\n");
  write(engine, ".claude/hooks/b.mjs", "// b v2\n");
  write(engine, ".claude/hooks/lib/x.mjs", "// x v2\n");
  const out = join(engine, "out");
  packHooks(out, { engineRoot: engine, version: "6.29.2" });
  return { engine, packaged: loadPackaged(out) };
}

/** Un proyecto con un hook de cada clase. */
function project() {
  const root = mkdtempSync(join(tmpdir(), "specbox-project-"));
  write(root, ".claude/hooks/a.mjs", "// a v1\n"); // publicado en la 6.20.0, sin tocar → se actualiza
  write(root, ".claude/hooks/b.mjs", "// b v1 con mi arreglo\n"); // retocado
  write(root, ".claude/hooks/c.mjs", "// c\n"); // al día
  write(root, ".claude/hooks/z.mjs", "// z\n"); // lo instaló una versión anterior
  write(root, `.claude/hooks/${REGISTRY}`, JSON.stringify({ version: "6.20.0", files: { "z.mjs": sha("// z\n") } }));
  write(root, ".claude/settings.json", JSON.stringify({
    permissions: { allow: ["Read"] },
    hooks: { PreToolUse: [{ matcher: "Write", hooks: [{ type: "command", command: "node mi-hook.mjs" }] }] },
  }));
  return root;
}

test("el paquete trae los hooks con su huella y el historial de las versiones publicadas", () => {
  const { engine, packaged } = packagedFixture();
  try {
    assert.equal(packaged.version, "6.29.2");
    assert.deepEqual(Object.keys(packaged.files).sort(), ["a.mjs", "b.mjs", "c.mjs", "lib/x.mjs"]);
    assert.equal(packaged.files["a.mjs"], sha("// a v2\n"));
    assert.deepEqual(packaged.history["a.mjs"], [sha("// a v1\n"), sha("// a v2\n")]);
    assert.deepEqual(packaged.settingsHooks, TEMPLATE.hooks);
  } finally {
    rmSync(engine, { recursive: true, force: true });
  }
});

test("AC-01: status lista cada hook que difiere del publicado y los registros que faltan", () => {
  const { engine, packaged } = packagedFixture();
  const root = project();
  try {
    const status = hooksStatus({ projectRoot: root, packaged });
    const states = Object.fromEntries(status.hooks.map((h) => [h.path, h.state]));
    assert.deepEqual(states, { "a.mjs": "updatable", "b.mjs": "modified", "c.mjs": "current", "lib/x.mjs": "missing", "z.mjs": "retired" });
    assert.deepEqual(status.settings_missing.map((s) => s.command), ["node .claude/hooks/a.mjs", "node .claude/hooks/c.mjs"]);
    assert.equal(status.installed_version, "6.20.0");
    assert.equal(status.differs, true);
  } finally {
    rmSync(engine, { recursive: true, force: true });
    rmSync(root, { recursive: true, force: true });
  }
});

test("AC-02: un hook retocado no se pisa; la versión nueva queda al lado y --overwrite lo sustituye", () => {
  const { engine, packaged } = packagedFixture();
  const root = project();
  try {
    const result = updateHooks({ projectRoot: root, packaged, now: () => "2026-10-28T00:00:00Z" });
    const read = (rel) => readFileSync(join(root, ".claude/hooks", rel), "utf8");
    assert.equal(read("b.mjs"), "// b v1 con mi arreglo\n");
    assert.equal(read("b.mjs.new"), "// b v2\n");
    assert.deepEqual(result.kept, [{ path: "b.mjs", new: ".claude/hooks/b.mjs.new" }]);
    assert.deepEqual(result.written.sort(), ["a.mjs", "lib/x.mjs"]);
    assert.equal(read("a.mjs"), "// a v2\n");
    assert.equal(read("z.mjs"), "// z\n"); // no se borra
    assert.deepEqual(result.retired, ["z.mjs"]);

    // settings.json: solo se añade, con copia; lo del usuario sigue.
    const settings = JSON.parse(readFileSync(join(root, ".claude/settings.json"), "utf8"));
    assert.deepEqual(settings.permissions, { allow: ["Read"] });
    assert.deepEqual(settings.hooks.PreToolUse[0].hooks.map((h) => h.command), ["node mi-hook.mjs", "node .claude/hooks/a.mjs"]);
    assert.equal(settings.hooks.PostToolUse[0].matcher, "Read");
    assert.ok(existsSync(join(root, ".claude/settings.json.bak")));
    assert.equal(result.settings_added, 2);

    // Una segunda pasada solo ve el retocado; con --overwrite se sustituye.
    const again = hooksStatus({ projectRoot: root, packaged });
    assert.deepEqual(again.hooks.filter((h) => h.state !== "current").map((h) => `${h.path}:${h.state}`), ["b.mjs:modified", "z.mjs:retired"]);
    assert.equal(again.settings_missing.length, 0);
    updateHooks({ projectRoot: root, packaged, overwrite: ["b"] });
    assert.equal(read("b.mjs"), "// b v2\n");
    assert.equal(JSON.parse(read(REGISTRY)).version, "6.29.2");
  } finally {
    rmSync(engine, { recursive: true, force: true });
    rmSync(root, { recursive: true, force: true });
  }
});

test("AC-03: con una sola orden, sin clon del engine ni servidor, el proyecto queda con los hooks publicados", async () => {
  const { engine, packaged } = packagedFixture();
  const root = mkdtempSync(join(tmpdir(), "specbox-empty-"));
  const out = [];
  try {
    const deps = { env: { LANG: "es_ES.UTF-8" }, print: (l) => out.push(l), printErr: (l) => out.push(l), loadPackaged: () => packaged, cwd: root };
    assert.equal(await run(["hooks", "update"], deps), 0);
    assert.match(out[0], /frente a SpecBox 6\.29\.2 \(instalados: sin registro\)/);
    assert.match(out[0], /lib\/x\.mjs\s+falta: se instala/); // la lista sale antes de actualizar
    assert.match(out.at(-1), /Hooks actualizados a 6\.29\.2: 4 escritos/);
    const status = hooksStatus({ projectRoot: root, packaged });
    assert.equal(status.differs, false);

    out.length = 0;
    assert.equal(await run(["hooks", "status"], deps), 0);
    assert.match(out.join("\n"), /Todo al día/);
  } finally {
    rmSync(engine, { recursive: true, force: true });
    rmSync(root, { recursive: true, force: true });
  }
});

test("la CLI explica un retocado y cómo pasar a la versión nueva", async () => {
  const { engine, packaged } = packagedFixture();
  const root = project();
  const out = [];
  try {
    const deps = { env: { LANG: "es_ES.UTF-8" }, print: (l) => out.push(l), loadPackaged: () => packaged, cwd: root };
    await run(["hooks", "update"], deps);
    const text = out.join("\n");
    assert.match(text, /b\.mjs\s+retocado: no se toca/);
    assert.match(text, /b\.mjs: lo cambiaste tú; la versión nueva está en \.claude\/hooks\/b\.mjs\.new\. .*--overwrite b/);
  } finally {
    rmSync(engine, { recursive: true, force: true });
    rmSync(root, { recursive: true, force: true });
  }
});

test("las órdenes internas de la extensión dan el mismo estado y la misma actualización", async () => {
  const { engine, packaged } = packagedFixture();
  const root = project();
  try {
    const call = async (command, input) => {
      let value;
      await runInternal(command, { config: {}, store: {}, account: "", home: root, readInput: async () => input, out: (v) => { value = v; }, deps: { loadPackaged: () => packaged } });
      return value;
    };
    const status = await call("_hooks_status", { project_root: root });
    assert.equal(status.ok, true);
    assert.equal(status.hooks.find((h) => h.path === "b.mjs").state, "modified");
    const update = await call("_hooks_update", { project_root: root, overwrite: [] });
    assert.deepEqual(update.kept.map((k) => k.path), ["b.mjs"]);
    assert.deepEqual(await call("_hooks_status", {}), { ok: false, reason: "missing_project_root" });
  } finally {
    rmSync(engine, { recursive: true, force: true });
    rmSync(root, { recursive: true, force: true });
  }
});

test("el empaquetado real lleva todos los hooks del engine con su huella exacta", () => {
  const out = mkdtempSync(join(tmpdir(), "specbox-pack-"));
  try {
    packHooks(join(out, "hooks"));
    const packaged = loadPackaged(join(out, "hooks"));
    const expected = hookFiles(ENGINE_ROOT);
    assert.deepEqual(Object.keys(packaged.files), expected);
    assert.ok(expected.includes("freeform-fragment.mjs") && expected.includes("lib/utils.mjs"));
    assert.ok(!expected.some((p) => p.endsWith(".test.mjs")));
    for (const rel of expected) {
      assert.equal(packaged.files[rel], sha(readFileSync(join(ENGINE_ROOT, ".claude/hooks", rel))));
      assert.ok(packaged.history[rel].includes(packaged.files[rel]));
    }
    assert.ok(packaged.settingsHooks.PreToolUse.length > 0);
  } finally {
    rmSync(out, { recursive: true, force: true });
  }
});

test("el repositorio del engine no se toma por un paquete (no hay hooks empaquetados)", () => {
  assert.equal(loadPackaged(resolve(HERE, "no-existe")), null);
});

test("AC-04: la guía de actualización del engine da el comando y qué hacer con un hook retocado", () => {
  const engineRoot = resolve(HERE, "..", "..", "..");
  const guide = readFileSync(join(engineRoot, "docs", "getting-started.md"), "utf8").split("## Actualizacion del engine")[1].split("\n## ")[0];
  assert.match(guide, /npx specbox@latest hooks update/);
  assert.match(guide, /Update Project Hooks/);
  assert.match(guide, /\.mjs\.new/);
  assert.match(guide, /--overwrite <hook>/);
  const hooksGuide = readFileSync(join(engineRoot, "doc", "guides", "hooks.md"), "utf8");
  assert.match(hooksGuide, /## Cómo se actualizan en un proyecto/);
});
