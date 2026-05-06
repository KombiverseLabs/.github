#!/usr/bin/env node
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import https from "node:https";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const SHARED_REPO_ROOT = path.resolve(SCRIPT_DIR, "..");
const DEFAULT_WORKSPACE_ROOT = path.resolve(SHARED_REPO_ROOT, "..");
const DEFAULT_MANIFEST = path.join(SHARED_REPO_ROOT, "local-dev", "kombify-gates.json");
const DEFAULT_LOCAL_MANIFEST = path.join(SHARED_REPO_ROOT, "local-dev", "kombify-gates.local.json");
const LOCAL_DEV_DIR = path.join(SHARED_REPO_ROOT, "local-dev");
const LOCAL_LOG_DIR = path.join(LOCAL_DEV_DIR, "logs");
const LOCAL_STATE_DIR = path.join(LOCAL_DEV_DIR, "state");
const SECRET_KEY_PATTERN = /TOKEN|SECRET|PASSWORD|KEY|DSN|DATABASE_URL/i;
const VALID_GATES = new Set(["quick", "standard", "full"]);
const VALID_MODES = new Set(["local", "saas", "selfhosted", "hybrid", "integration"]);
const ASPIRE_RESOURCE_NAMES = [
  "admin",
  "ai",
  "ai-mobile",
  "ai-portal",
  "blog",
  "cloud",
  "db",
  "kong",
  "me",
  "sim",
  "stack",
];

const DEFAULT_GATE_TASKS = {
  quick: "preflight:quick",
  standard: "preflight:release",
  full: "preflight:deploy",
};

async function main() {
  const [command, ...rest] = process.argv.slice(2);
  const { options, positionals } = parseArgs(rest);

  try {
    let result;
    let exitCode = 0;

    switch (command) {
      case "doctor":
        result = doctor();
        exitCode = result.status === "ok" ? 0 : 1;
        break;
      case "audit":
        result = audit(options);
        exitCode = result.status === "ok" ? 0 : 1;
        break;
      case "list":
        result = listRepos(options);
        break;
      case "run":
        result = runGate(positionals, options);
        exitCode = result.status === "failed" ? 1 : 0;
        break;
      case "up":
        result = up(positionals, options);
        exitCode = result.status === "failed" ? 1 : 0;
        break;
      case "down":
        result = down(positionals, options);
        exitCode = result.status === "failed" ? 1 : 0;
        break;
      case "smoke":
        result = await smoke(positionals, options);
        exitCode = result.status === "failed" ? 1 : 0;
        break;
      case "help":
      case "-h":
      case "--help":
      case undefined:
        result = help();
        break;
      default:
        result = {
          status: "failed",
          error: `Unknown command '${command}'. Run: node scripts/kombi-local-gate.mjs help`,
        };
        exitCode = 1;
    }

    finish(result, options, exitCode);
  } catch (error) {
    const result = {
      status: "failed",
      error: error instanceof Error ? error.message : String(error),
    };
    finish(result, options, 1);
  }
}

function parseArgs(args) {
  const options = {};
  const positionals = [];

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (!arg.startsWith("--")) {
      positionals.push(arg);
      continue;
    }

    const raw = arg.slice(2);
    const equalsIndex = raw.indexOf("=");
    if (equalsIndex >= 0) {
      options[raw.slice(0, equalsIndex)] = raw.slice(equalsIndex + 1);
      continue;
    }

    if (["json", "dry-run", "keep", "strict"].includes(raw)) {
      options[raw] = true;
      continue;
    }

    const next = args[index + 1];
    if (next === undefined || next.startsWith("--")) {
      options[raw] = true;
      continue;
    }

    options[raw] = next;
    index += 1;
  }

  return { options, positionals };
}

function doctor() {
  const tools = [
    {
      name: "Docker Desktop",
      command: ["docker", "version", "--format", "{{.Server.Version}}"],
      required: true,
      installHint: "Start Docker Desktop and verify 'docker version' works.",
    },
    {
      name: "Docker Compose",
      command: ["docker", "compose", "version"],
      required: true,
      installHint: "Install Docker Desktop with the Compose plugin enabled.",
    },
    {
      name: "Doppler CLI",
      command: ["doppler", "--version"],
      required: true,
      installHint: "Install Doppler CLI (Windows: winget install Doppler.doppler) and authenticate before secret-backed setup tasks.",
    },
    {
      name: "mise",
      command: ["mise", "--version"],
      required: true,
      installHint: "Install mise (Windows: winget install jdx.mise) and trust each repo's mise.toml before running local gates.",
    },
    {
      name: "node",
      command: ["node", "--version"],
      required: true,
      installHint: "Install Node or expose the mise-managed Node binary on PATH.",
    },
    {
      name: "npm",
      command: ["npm", "--version"],
      required: true,
      installHint: "Install npm or expose the mise-managed npm binary on PATH.",
    },
    {
      name: "bun",
      command: ["bun", "--version"],
      required: true,
      installHint: "Install Bun or run 'mise install' in the target repo.",
    },
    {
      name: "pnpm",
      command: ["pnpm", "--version"],
      required: true,
      installHint: "Install pnpm or run 'mise install' in pnpm repos.",
    },
    {
      name: "go",
      command: ["go", "version"],
      required: true,
      installHint: "Install Go or run 'mise install' in Go repos.",
    },
    {
      name: ".NET SDK",
      command: ["dotnet", "--version"],
      required: true,
      installHint: "Install the .NET SDK required by Aspire AppHost projects before running Aspire profiles.",
    },
    {
      name: "aspire",
      command: ["aspire", "--version"],
      required: true,
      installHint: "Install the Aspire CLI for multi-repo local integration profiles after the .NET SDK is available.",
    },
  ].map(checkTool);

  const missingRequired = tools.filter((tool) => tool.required && !tool.found);
  return {
    status: missingRequired.length === 0 ? "ok" : "failed",
    workspaceRoot: DEFAULT_WORKSPACE_ROOT,
    tools,
  };
}

function checkTool(tool) {
  if (tool.name === "node") {
    return {
      ...tool,
      found: true,
      version: process.version,
    };
  }

  const result = spawnSync(tool.command[0], tool.command.slice(1), {
    cwd: SHARED_REPO_ROOT,
    encoding: "utf-8",
    shell: true,
    windowsHide: true,
  });

  return {
    ...tool,
    found: result.status === 0,
    version: result.status === 0 ? firstLine(result.stdout || result.stderr) : null,
    error: result.status === 0 ? undefined : firstLine(result.stderr || result.stdout),
  };
}

function audit(options) {
  const manifest = loadManifest(options);
  const workspaceRoot = resolveWorkspaceRoot(options);
  const requiredTasks = manifest.requiredMiseTasks || [];

  const repos = manifest.repos.map((repo) => {
    const repoPath = path.resolve(workspaceRoot, repo.path);
    const misePath = path.join(repoPath, "mise.toml");
    const exists = fs.existsSync(repoPath);
    const hasMiseToml = fs.existsSync(misePath);
    const presentTasks = hasMiseToml ? [...parseMiseTasks(fs.readFileSync(misePath, "utf-8"))].sort() : [];
    const presentSet = new Set(presentTasks);
    const missingTasks = requiredTasks.filter((task) => !presentSet.has(task));

    return {
      id: repo.id,
      path: repo.path,
      exists,
      miseToml: hasMiseToml,
      missingTasks: exists && hasMiseToml ? missingTasks : requiredTasks,
      presentTasks,
    };
  });

  const failed = repos.some((repo) => !repo.exists || !repo.miseToml || repo.missingTasks.length > 0);
  return {
    status: failed ? "failed" : "ok",
    requiredMiseTasks: requiredTasks,
    workspaceRoot,
    repos,
  };
}

function listRepos(options) {
  const manifest = loadManifest(options);
  return {
    status: "ok",
    repos: manifest.repos.map((repo) => ({
      id: repo.id,
      name: repo.name,
      path: repo.path,
      components: (repo.components || []).map((component) => ({
        id: component.id,
        modes: component.modes || [],
        runtime: component.runtime,
        packaging: component.packaging,
      })),
    })),
  };
}

function runGate(positionals, options) {
  const repoId = positionals[0];
  const gate = options.gate || "quick";
  if (!repoId) {
    throw new Error("Missing repo id. Usage: run <repo> --gate quick|standard|full");
  }
  if (!VALID_GATES.has(gate)) {
    throw new Error(`Invalid gate '${gate}'. Valid gates: ${[...VALID_GATES].join(", ")}`);
  }

  const context = resolveRepoContext(repoId, options);
  const component = resolveComponent(context.repo, options.component);
  const gateConfig = (component.gates && component.gates[gate]) || {};
  const miseTask = gateConfig.miseTask || DEFAULT_GATE_TASKS[gate];
  const tasks = readRepoMiseTasks(context.repoPath);

  if (tasks.has(miseTask)) {
    return executePlan(
      {
        status: options["dry-run"] ? "dry-run" : "running",
        source: "mise",
        repo: context.repo.id,
        component: component.id,
        gate,
        cwd: context.repoPath,
        command: ["mise", "run", miseTask],
      },
      options,
    );
  }

  if (Array.isArray(gateConfig.command)) {
    return executePlan(
      {
        status: options["dry-run"] ? "dry-run" : "running",
        source: "manifest",
        repo: context.repo.id,
        component: component.id,
        gate,
        cwd: context.repoPath,
        command: gateConfig.command,
      },
      options,
    );
  }

  if (gate === "full" && gateConfig.aspireProfile) {
    return executePlan(buildAspirePlan(context, component, gateConfig.aspireProfile, options), options);
  }

  return {
    status: "failed",
    repo: context.repo.id,
    component: component.id,
    gate,
    error: `Repo does not define mise task '${miseTask}' and has no manifest fallback for gate '${gate}'.`,
  };
}

function up(positionals, options) {
  const repoId = positionals[0];
  const mode = options.mode || "local";
  if (!repoId) {
    throw new Error("Missing repo id. Usage: up <repo> --mode local|saas|selfhosted|hybrid");
  }
  if (!VALID_MODES.has(mode)) {
    throw new Error(`Invalid mode '${mode}'. Valid modes: ${[...VALID_MODES].join(", ")}`);
  }

  const context = resolveRepoContext(repoId, options);
  const component = resolveComponent(context.repo, options.component);

  if (mode === "local" && component.runtime === "docker-compose" && component.composeFile) {
    return executePlan(
      {
        status: options["dry-run"] ? "dry-run" : "running",
        source: "docker-compose",
        repo: context.repo.id,
        component: component.id,
        mode,
        keep: Boolean(options.keep),
        cwd: context.repoPath,
        command: ["docker", "compose", "-f", component.composeFile, "up", "-d", "--build", "--remove-orphans"],
      },
      options,
    );
  }

  if (component.runtime === "aspire") {
    const manifest = loadManifest(options);
    const profile = component.aspire?.profiles?.[mode] || manifest.aspireProfiles?.[mode];
    if (profile) {
      return executePlan(buildAspirePlan(context, component, profile, options, mode), options);
    }
  }

  const tasks = readRepoMiseTasks(context.repoPath);
  const explicitTask = component.aspire?.tasks?.[mode];
  const modeTaskCandidates = [
    explicitTask,
    `aspire:${mode}`,
    mode === "local" ? "aspire:start" : null,
    mode === "local" ? "preview:local" : null,
    mode === "saas" ? "aspire:full" : null,
    mode === "selfhosted" ? "aspire:start" : null,
    mode === "integration" ? "aspire:integration" : null,
  ].filter(Boolean);
  const miseTask = modeTaskCandidates.find((task) => tasks.has(task));

  if (miseTask) {
    return executePlan(
      {
        status: options["dry-run"] ? "dry-run" : "running",
        source: "mise",
        repo: context.repo.id,
        component: component.id,
        mode,
        keep: Boolean(options.keep),
        cwd: context.repoPath,
        command: ["mise", "run", miseTask],
      },
      options,
    );
  }

  const manifest = loadManifest(options);
  const profile = component.aspire?.profiles?.[mode] || manifest.aspireProfiles?.[mode];
  if (profile) {
    return executePlan(buildAspirePlan(context, component, profile, options, mode), options);
  }

  if (component.composeFile) {
    return executePlan(
      {
        status: options["dry-run"] ? "dry-run" : "running",
        source: "docker-compose",
        repo: context.repo.id,
        component: component.id,
        mode,
        keep: Boolean(options.keep),
        cwd: context.repoPath,
        command: ["docker", "compose", "-f", component.composeFile, "up", "-d", "--build", "--remove-orphans"],
      },
      options,
    );
  }

  return {
    status: "failed",
    repo: context.repo.id,
    component: component.id,
    mode,
    error: `No mise, Aspire, or Docker Compose up path is configured for mode '${mode}'.`,
  };
}

function down(positionals, options) {
  const repoId = positionals[0];
  if (!repoId) {
    throw new Error("Missing repo id. Usage: down <repo>");
  }

  const context = resolveRepoContext(repoId, options);
  const component = resolveComponent(context.repo, options.component);
  const tasks = readRepoMiseTasks(context.repoPath);

  if (component.runtime === "aspire") {
    return executePlan(buildAspireStopPlan(context, component, options), options);
  }

  if (tasks.has("down")) {
    return executePlan(
      {
        status: options["dry-run"] ? "dry-run" : "running",
        source: "mise",
        repo: context.repo.id,
        component: component.id,
        cwd: context.repoPath,
        command: ["mise", "run", "down"],
      },
      options,
    );
  }

  if (component.composeFile) {
    return executePlan(
      {
        status: options["dry-run"] ? "dry-run" : "running",
        source: "docker-compose",
        repo: context.repo.id,
        component: component.id,
        cwd: context.repoPath,
        command: ["docker", "compose", "-f", component.composeFile, "down", "--remove-orphans"],
      },
      options,
    );
  }

  return {
    status: "failed",
    repo: context.repo.id,
    component: component.id,
    error: "No down task, Compose file, or Aspire runtime is configured.",
  };
}

async function smoke(positionals, options) {
  const repoId = positionals[0];
  if (!repoId) {
    throw new Error("Missing repo id. Usage: smoke <repo>");
  }

  const context = resolveRepoContext(repoId, options);
  const component = resolveComponent(context.repo, options.component);
  const mode = options.mode || "local";
  if (!VALID_MODES.has(mode)) {
    throw new Error(`Invalid mode '${mode}'. Valid modes: ${[...VALID_MODES].join(", ")}`);
  }
  const urls = resolveHealthUrls(component, mode).filter((url) => /^https?:\/\//i.test(url));
  const retries = Number.parseInt(options.retries || "5", 10);
  const timeoutMs = Number.parseInt(options["timeout-ms"] || "3000", 10);

  if (options["dry-run"]) {
    return {
      status: "dry-run",
      source: "smoke",
      repo: context.repo.id,
      component: component.id,
      mode,
      urls,
      retries,
      timeoutMs,
    };
  }

  if (urls.length === 0) {
    return {
      status: "skipped",
      source: "smoke",
      repo: context.repo.id,
      component: component.id,
      mode,
      urls,
      reason: "No HTTP health URLs are configured for this component.",
    };
  }

  const checks = [];
  for (const url of urls) {
    checks.push(await checkHealthUrlWithRetries(url, retries, timeoutMs));
  }

  return {
    status: checks.every((check) => check.ok) ? "ok" : "failed",
    source: "smoke",
    repo: context.repo.id,
    component: component.id,
    mode,
    urls,
    checks,
  };
}

function resolveHealthUrls(component, mode) {
  const modeUrls = component.healthUrlsByMode?.[mode];
  if (Array.isArray(modeUrls)) {
    return modeUrls;
  }
  return component.healthUrls || [];
}

async function checkHealthUrlWithRetries(url, retries, timeoutMs) {
  let last = null;
  for (let attempt = 1; attempt <= retries; attempt += 1) {
    last = await checkHealthUrl(url, timeoutMs, attempt);
    if (last.ok) {
      return last;
    }
    if (attempt < retries) {
      await sleep(Math.min(1000 * attempt, 5000));
    }
  }
  return last;
}

async function checkHealthUrl(url, timeoutMs, attempt) {
  return new Promise((resolve) => {
    const parsed = new URL(url);
    const client = parsed.protocol === "https:" ? https : http;
    const request = client.request(
      parsed,
      {
        method: "GET",
        timeout: timeoutMs,
      },
      (response) => {
        response.resume();
        response.on("end", () => {
          resolve({
            url,
            attempt,
            ok: response.statusCode >= 200 && response.statusCode < 400,
            statusCode: response.statusCode,
          });
        });
      },
    );

    request.on("timeout", () => {
      request.destroy(new Error(`Timeout after ${timeoutMs}ms`));
    });
    request.on("error", (error) => {
      resolve({
        url,
        attempt,
        ok: false,
        error: error instanceof Error ? error.message : String(error),
      });
    });
    request.end();
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildAspirePlan(context, component, profile, options, mode = "full") {
  const manifest = loadManifest(options);
  const workspaceRoot = resolveWorkspaceRoot(options);
  const appHostPath = manifest.aspireAppHost || "kombify-Core/aspire/apphost.cs";
  const appHost = path.resolve(workspaceRoot, appHostPath);
  const appHostCwd = path.dirname(appHost);
  const appHostFile = path.basename(appHost);

  return {
    status: options["dry-run"] ? "dry-run" : "running",
    source: "aspire",
    action: "start",
    repo: context.repo.id,
    component: component.id,
    mode,
    keep: Boolean(options.keep),
    appHost,
    cwd: appHostCwd,
    command: ["dotnet", "run", appHostFile, "--no-restore"],
    restoreCommand: ["aspire", "restore", "--apphost", appHostFile, "--non-interactive"],
    env: {
      KOMBIFY_ASPIRE_PROFILE: profile,
      KOMBIFY_FOCUS_SERVICE: component.aspire?.focusService || context.repo.aspireFocusService || context.repo.id,
      KOMBIFY_REPOS_ROOT: workspaceRoot,
    },
  };
}

function buildAspireStopPlan(context, component, options) {
  const manifest = loadManifest(options);
  const workspaceRoot = resolveWorkspaceRoot(options);
  const appHostPath = manifest.aspireAppHost || "kombify-Core/aspire/apphost.cs";
  const appHost = path.resolve(workspaceRoot, appHostPath);
  const appHostCwd = path.dirname(appHost);
  const appHostFile = path.basename(appHost);

  return {
    status: options["dry-run"] ? "dry-run" : "running",
    source: "aspire",
    action: "stop",
    repo: context.repo.id,
    component: component.id,
    appHost,
    cwd: appHostCwd,
    command: ["aspire", "stop", "--apphost", appHostFile, "--non-interactive"],
  };
}

function executePlan(plan, options) {
  if (options["dry-run"]) {
    return plan;
  }

  if (plan.source === "aspire" && plan.action === "start") {
    return executeAspireStartPlan(plan, options);
  }

  if (plan.source === "aspire" && plan.action === "stop") {
    return executeAspireStopPlan(plan, options);
  }

  const [command, ...args] = plan.command;
  const env = { ...process.env, ...(plan.env || {}) };
  const result = spawnSync(command, args, {
    cwd: plan.cwd,
    env,
    encoding: "utf-8",
    stdio: options.json ? "pipe" : "inherit",
    windowsHide: true,
  });

  if (result.status === 0) {
    return {
      ...plan,
      status: "ok",
      exitCode: 0,
      stdout: result.stdout || "",
      stderr: result.stderr || "",
    };
  }

  return {
    ...plan,
    status: "failed",
    exitCode: result.status ?? 1,
    error: result.error ? result.error.message : undefined,
    stdout: result.stdout || "",
    stderr: result.stderr || "",
  };
}

function executeAspireStartPlan(plan, options) {
  fs.mkdirSync(LOCAL_LOG_DIR, { recursive: true });
  fs.mkdirSync(LOCAL_STATE_DIR, { recursive: true });

  const env = { ...process.env, ...(plan.env || {}) };
  const [restoreCommand, ...restoreArgs] = plan.restoreCommand;
  const restore = spawnSync(restoreCommand, restoreArgs, {
    cwd: plan.cwd,
    env,
    encoding: "utf-8",
    stdio: options.json ? "pipe" : "inherit",
    windowsHide: true,
  });

  if (restore.status !== 0) {
    return {
      ...plan,
      status: "failed",
      exitCode: restore.status ?? 1,
      error: restore.error ? restore.error.message : undefined,
      stdout: restore.stdout || "",
      stderr: restore.stderr || "",
    };
  }

  const startedAt = new Date().toISOString();
  const logBase = `${stateKey(plan)}-${startedAt.replace(/[:.]/g, "-")}`;
  const stdoutPath = path.join(LOCAL_LOG_DIR, `${logBase}.out.log`);
  const stderrPath = path.join(LOCAL_LOG_DIR, `${logBase}.err.log`);
  const stdoutFd = fs.openSync(stdoutPath, "a");
  const stderrFd = fs.openSync(stderrPath, "a");
  const [command, ...args] = plan.command;

  const child = spawn(command, args, {
    cwd: plan.cwd,
    env,
    detached: true,
    stdio: ["ignore", stdoutFd, stderrFd],
    windowsHide: true,
  });

  fs.closeSync(stdoutFd);
  fs.closeSync(stderrFd);
  child.unref();

  const timeoutMs = Number(options["start-timeout-ms"] || options["start-timeout"] || 240000);
  const wait = waitForAspireAppHost(plan, child.pid, timeoutMs);
  const state = {
    pid: child.pid,
    startedAt,
    repo: plan.repo,
    component: plan.component,
    mode: plan.mode,
    cwd: plan.cwd,
    appHost: plan.appHost,
    stdoutPath,
    stderrPath,
    env: plan.env,
  };
  fs.writeFileSync(statePath(plan), `${JSON.stringify(state, null, 2)}\n`, "utf-8");

  if (!wait.ok) {
    const kill = killProcessTree(child.pid);
    const cleanup = cleanupAspireContainers(options);
    if (fs.existsSync(statePath(plan))) {
      fs.rmSync(statePath(plan), { force: true });
    }
    return {
      ...plan,
      status: "failed",
      exitCode: 1,
      pid: child.pid,
      stdout: [restore.stdout, kill.stdout, cleanup.stdout].filter(Boolean).join("\n"),
      stderr: [restore.stderr, wait.error, kill.stderr, cleanup.stderr].filter(Boolean).join("\n"),
      logs: { stdoutPath, stderrPath },
    };
  }

  return {
    ...plan,
    status: "ok",
    exitCode: 0,
    pid: child.pid,
    stdout: restore.stdout || "",
    stderr: restore.stderr || "",
    logs: { stdoutPath, stderrPath },
  };
}

function executeAspireStopPlan(plan, options) {
  const state = readState(plan);
  const [command, ...args] = plan.command;
  const stop = spawnSync(command, args, {
    cwd: plan.cwd,
    encoding: "utf-8",
    stdio: options.json ? "pipe" : "inherit",
    windowsHide: true,
  });

  const kill = state?.pid ? killProcessTree(state.pid) : { status: "skipped", stdout: "", stderr: "" };
  const cleanup = cleanupAspireContainers(options);
  if (fs.existsSync(statePath(plan))) {
    fs.rmSync(statePath(plan), { force: true });
  }

  return {
    ...plan,
    status: stop.status === 0 || kill.status === 0 || cleanup.status === 0 ? "ok" : "failed",
    exitCode: stop.status === 0 || kill.status === 0 || cleanup.status === 0 ? 0 : 1,
    stdout: [stop.stdout, kill.stdout, cleanup.stdout].filter(Boolean).join("\n"),
    stderr: [stop.stderr, kill.stderr, cleanup.stderr].filter(Boolean).join("\n"),
  };
}

function waitForAspireAppHost(plan, pid, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (!isProcessRunning(pid)) {
      return { ok: false, error: `Aspire AppHost process ${pid} exited before registration.` };
    }

    const result = spawnSync("aspire", ["ps", "--non-interactive"], {
      cwd: plan.cwd,
      encoding: "utf-8",
      windowsHide: true,
    });
    const output = `${result.stdout || ""}\n${result.stderr || ""}`;
    if (result.status === 0 && output.includes(path.basename(plan.appHost))) {
      return { ok: true };
    }

    sleepSync(2000);
  }

  return { ok: false, error: `Timeout waiting ${timeoutMs}ms for Aspire AppHost registration.` };
}

function sleepSync(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

function isProcessRunning(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

function killProcessTree(pid) {
  if (!isProcessRunning(pid)) {
    return { status: 0, stdout: "", stderr: "" };
  }

  if (process.platform === "win32") {
    const result = spawnSync("taskkill", ["/PID", String(pid), "/T", "/F"], {
      encoding: "utf-8",
      windowsHide: true,
    });
    return {
      status: result.status ?? 1,
      stdout: result.stdout || "",
      stderr: result.stderr || "",
    };
  }

  try {
    process.kill(-pid, "SIGTERM");
    return { status: 0, stdout: "", stderr: "" };
  } catch (error) {
    return { status: 1, stdout: "", stderr: error instanceof Error ? error.message : String(error) };
  }
}

function cleanupAspireContainers(options) {
  const list = spawnSync("docker", ["ps", "-a", "--format", "{{.Names}}"], {
    encoding: "utf-8",
    windowsHide: true,
  });
  if (list.status !== 0) {
    return {
      status: list.status ?? 1,
      stdout: list.stdout || "",
      stderr: list.stderr || "",
    };
  }

  const resourcePattern = new RegExp(`^kombify-(?:${ASPIRE_RESOURCE_NAMES.join("|")})-[a-z0-9]+$`);
  const names = String(list.stdout || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((name) => resourcePattern.test(name));

  if (names.length === 0) {
    return { status: 0, stdout: "", stderr: "" };
  }

  const remove = spawnSync("docker", ["rm", "-f", ...names], {
    encoding: "utf-8",
    stdio: options.json ? "pipe" : "inherit",
    windowsHide: true,
  });
  return {
    status: remove.status ?? 1,
    stdout: remove.stdout || "",
    stderr: remove.stderr || "",
  };
}

function stateKey(plan) {
  return `${normalizeId(plan.repo)}-${normalizeId(plan.component)}`;
}

function statePath(plan) {
  return path.join(LOCAL_STATE_DIR, `aspire-${stateKey(plan)}.json`);
}

function readState(plan) {
  const file = statePath(plan);
  if (!fs.existsSync(file)) {
    return null;
  }
  return JSON.parse(fs.readFileSync(file, "utf-8"));
}

function resolveRepoContext(repoId, options) {
  const manifest = loadManifest(options);
  const workspaceRoot = resolveWorkspaceRoot(options);
  const normalized = normalizeId(repoId);
  const repo = manifest.repos.find(
    (candidate) =>
      normalizeId(candidate.id) === normalized ||
      normalizeId(candidate.name || "") === normalized ||
      normalizeId(candidate.path) === normalized,
  );

  if (!repo) {
    throw new Error(`Unknown repo '${repoId}'. Run 'list' to see known repos.`);
  }

  return {
    manifest,
    workspaceRoot,
    repo,
    repoPath: path.resolve(workspaceRoot, repo.path),
  };
}

function resolveComponent(repo, componentId) {
  const components = repo.components || [];
  if (components.length === 0) {
    throw new Error(`Repo '${repo.id}' has no components configured.`);
  }
  if (!componentId) {
    return components[0];
  }
  const component = components.find((candidate) => candidate.id === componentId);
  if (!component) {
    throw new Error(`Repo '${repo.id}' has no component '${componentId}'.`);
  }
  return component;
}

function loadManifest(options) {
  const manifestPath = path.resolve(options.manifest || DEFAULT_MANIFEST);
  if (!fs.existsSync(manifestPath)) {
    throw new Error(`Manifest not found: ${manifestPath}`);
  }
  const base = JSON.parse(fs.readFileSync(manifestPath, "utf-8"));
  const localManifestPath = options["local-manifest"]
    ? path.resolve(options["local-manifest"])
    : DEFAULT_LOCAL_MANIFEST;

  if (!fs.existsSync(localManifestPath)) {
    return base;
  }

  const override = JSON.parse(fs.readFileSync(localManifestPath, "utf-8"));
  return mergeManifest(base, override);
}

function mergeManifest(base, override) {
  return {
    ...base,
    ...override,
    requiredMiseTasks: override.requiredMiseTasks || base.requiredMiseTasks,
    aspireProfiles: {
      ...(base.aspireProfiles || {}),
      ...(override.aspireProfiles || {}),
    },
    repos: mergeRepos(base.repos || [], override.repos || []),
  };
}

function mergeRepos(baseRepos, overrideRepos) {
  const byId = new Map(baseRepos.map((repo) => [repo.id, structuredClone(repo)]));
  for (const overrideRepo of overrideRepos) {
    const current = byId.get(overrideRepo.id) || {};
    byId.set(overrideRepo.id, {
      ...current,
      ...overrideRepo,
      components: mergeComponents(current.components || [], overrideRepo.components || []),
    });
  }
  return [...byId.values()];
}

function mergeComponents(baseComponents, overrideComponents) {
  const byId = new Map(baseComponents.map((component) => [component.id, structuredClone(component)]));
  for (const overrideComponent of overrideComponents) {
    const current = byId.get(overrideComponent.id) || {};
    byId.set(overrideComponent.id, {
      ...current,
      ...overrideComponent,
      gates: {
        ...(current.gates || {}),
        ...(overrideComponent.gates || {}),
      },
      aspire: {
        ...(current.aspire || {}),
        ...(overrideComponent.aspire || {}),
        tasks: {
          ...(current.aspire?.tasks || {}),
          ...(overrideComponent.aspire?.tasks || {}),
        },
        profiles: {
          ...(current.aspire?.profiles || {}),
          ...(overrideComponent.aspire?.profiles || {}),
        },
      },
    });
  }
  return [...byId.values()];
}

function resolveWorkspaceRoot(options) {
  return path.resolve(options["workspace-root"] || DEFAULT_WORKSPACE_ROOT);
}

function readRepoMiseTasks(repoPath) {
  const misePath = path.join(repoPath, "mise.toml");
  if (!fs.existsSync(misePath)) {
    return new Set();
  }
  return parseMiseTasks(fs.readFileSync(misePath, "utf-8"));
}

function parseMiseTasks(text) {
  const tasks = new Set();
  const pattern = /^\s*\[tasks\.((?:"[^"]+")|(?:[^\]\s]+))\]\s*$/gm;
  let match;
  while ((match = pattern.exec(text)) !== null) {
    const raw = match[1];
    tasks.add(raw.startsWith('"') ? raw.slice(1, -1) : raw);
  }
  return tasks;
}

function normalizeId(value) {
  return String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function firstLine(value) {
  return String(value || "").trim().split(/\r?\n/)[0] || null;
}

function collectSecretEnvironment() {
  const result = {};
  for (const [key, value] of Object.entries(process.env).sort(([left], [right]) => left.localeCompare(right))) {
    if (SECRET_KEY_PATTERN.test(key)) {
      result[key] = value ? "[REDACTED]" : "";
    }
  }
  return result;
}

function redact(value, key = "") {
  if (SECRET_KEY_PATTERN.test(key)) {
    return value ? "[REDACTED]" : value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => redact(item));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([entryKey, entryValue]) => [entryKey, redact(entryValue, entryKey)]));
  }
  return value;
}

function writeReport(reportPath, payload) {
  const resolved = path.resolve(reportPath);
  fs.mkdirSync(path.dirname(resolved), { recursive: true });
  const generatedAt = new Date().toISOString();
  const receipt = buildReceipt(payload, generatedAt);
  const report = {
    schema: "kombify-local-gate-report",
    generatedAt,
    host: os.hostname(),
    ...(receipt ? { receipt } : {}),
    payload: redact(payload),
    environment: collectSecretEnvironment(),
  };
  fs.writeFileSync(resolved, `${JSON.stringify(report, null, 2)}\n`, "utf-8");
}

function buildReceipt(payload, generatedAt) {
  if (!payload || typeof payload !== "object" || !payload.repo) {
    return null;
  }

  return {
    schema: "kombify-local-preflight-receipt",
    generatedAt,
    host: os.hostname(),
    repo: payload.repo,
    component: payload.component,
    gate: payload.gate,
    mode: payload.mode,
    action: payload.action,
    source: payload.source,
    status: payload.status,
    exitCode: payload.exitCode,
    cwd: payload.cwd,
    command: payload.command,
    git: collectGitMetadata(payload.cwd),
  };
}

function collectGitMetadata(cwd) {
  if (!cwd) {
    return { found: false };
  }

  const root = runGit(cwd, ["rev-parse", "--show-toplevel"]);
  const sha = runGit(cwd, ["rev-parse", "HEAD"]);
  if (root.status !== 0 || sha.status !== 0) {
    return {
      found: false,
      root: root.stdout || null,
      error: firstLine(root.stderr || sha.stderr),
    };
  }

  const branch = runGit(cwd, ["branch", "--show-current"]);
  const status = runGit(cwd, ["status", "--porcelain"]);
  return {
    found: true,
    root: root.stdout,
    branch: branch.stdout || null,
    sha: sha.stdout,
    dirty: Boolean(status.stdout),
  };
}

function runGit(cwd, args) {
  const result = spawnSync("git", args, {
    cwd,
    encoding: "utf-8",
    windowsHide: true,
  });
  return {
    status: result.status ?? 1,
    stdout: String(result.stdout || "").trim(),
    stderr: String(result.stderr || "").trim(),
  };
}

function finish(result, options, exitCode) {
  if (options.report) {
    writeReport(options.report, result);
  }

  if (options.json) {
    process.stdout.write(`${JSON.stringify(redact(result), null, 2)}\n`);
  } else {
    process.stdout.write(formatHuman(result));
  }

  process.exit(exitCode);
}

function formatHuman(result) {
  if (result.tools) {
    const lines = ["Kombify local gate doctor", ""];
    for (const tool of result.tools) {
      lines.push(`${tool.found ? "OK" : "MISSING"} ${tool.name}${tool.version ? ` (${tool.version})` : ""}`);
      if (!tool.found) {
        lines.push(`  ${tool.installHint}`);
      }
    }
    lines.push("");
    lines.push(`Status: ${result.status}`);
    return `${lines.join("\n")}\n`;
  }

  if (result.repos && result.requiredMiseTasks) {
    const lines = ["Kombify mise task audit", ""];
    for (const repo of result.repos) {
      const suffix = repo.missingTasks.length ? `missing: ${repo.missingTasks.join(", ")}` : "ok";
      lines.push(`${repo.id}: ${suffix}`);
    }
    lines.push("");
    lines.push(`Status: ${result.status}`);
    return `${lines.join("\n")}\n`;
  }

  if (result.command) {
    const env = result.env ? ` env=${JSON.stringify(redact(result.env))}` : "";
    return `${result.status}: ${result.command.join(" ")} (source=${result.source}; cwd=${result.cwd})${env}\n`;
  }

  if (result.source === "smoke") {
    if (result.status === "dry-run") {
      return `${result.status}: smoke ${result.urls.join(", ")} (repo=${result.repo}; component=${result.component})\n`;
    }
    if (result.status === "skipped") {
      return `${result.status}: smoke ${result.reason} (repo=${result.repo}; component=${result.component})\n`;
    }
    const checks = (result.checks || []).map((check) => `${check.ok ? "OK" : "FAIL"} ${check.url}`).join("\n");
    return `${checks}\nStatus: ${result.status}\n`;
  }

  if (result.repos) {
    return `${result.repos.map((repo) => `${repo.id}\t${repo.path}`).join("\n")}\n`;
  }

  if (result.usage) {
    return result.usage;
  }

  return `${JSON.stringify(redact(result), null, 2)}\n`;
}

function help() {
  return {
    status: "ok",
    usage: `Kombify local gate

Usage:
  node scripts/kombi-local-gate.mjs doctor [--json] [--report <path>]
  node scripts/kombi-local-gate.mjs audit [--json] [--workspace-root <path>] [--manifest <path>]
  node scripts/kombi-local-gate.mjs list [--json]
  node scripts/kombi-local-gate.mjs run <repo> --gate quick|standard|full [--dry-run] [--json]
  node scripts/kombi-local-gate.mjs up <repo> --mode local|saas|selfhosted|hybrid|integration [--keep] [--dry-run] [--json]
  node scripts/kombi-local-gate.mjs down <repo> [--dry-run] [--json]
  node scripts/kombi-local-gate.mjs smoke <repo> [--mode local|saas|selfhosted|hybrid|integration] [--component <id>] [--retries <n>] [--timeout-ms <ms>] [--dry-run] [--json]
`,
  };
}

main();
