import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import plugin from '../.opencode/plugins/studio.ts'
import { runPython } from '../.opencode/studio/runtime/python.mjs'
import { repo, owner, coder, reviewer, copyTree } from './helpers.mjs'

const project = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
async function host(t) {
  const r = repo(t)
  copyTree(path.join(project, '.opencode'), path.join(r.root, '.opencode'))
  // Plugin files are installed configuration, not uncommitted product code.
  r.git('add', '.opencode'); r.git('commit', '-m', 'Install studio')
  const hooks = new Map(), tools = new Map(), storage = new Map()
  const sessions = new Map([owner, coder, reviewer].map((actor) => [actor.sessionID, { id: actor.sessionID, projectID: 'project', agent: actor.agent, parentID: actor.parentID }]))
  const register = (domain) => ({ hook: async (name, callback) => hooks.set(`${domain}.${name}`, callback) })
  const ctx = {
    location: { directory: r.root, project: { id: 'project' } },
    session: { ...register('session'), get: async ({ sessionID }) => sessions.get(sessionID), context: async () => [] },
    permission: register('permission'),
    tool: { ...register('tool'), transform: async (callback) => callback({ add: (tool) => tools.set(tool.name, tool) }) },
    storage: { get: async (key) => storage.get(key), set: async (key, value) => storage.set(key, value) },
    event: { subscribe: async function* () {} },
  }
  const cleanup = await plugin.setup(ctx); t.after(cleanup)
  const call = (input, actor = owner) => tools.get('studio_workflow').execute(input, { sessionID: actor.sessionID, signal: new AbortController().signal })
  return { ...r, hooks, tools, sessions, call }
}

test('V2 adapter registers workflow, permissions, tool/context/prompt hooks', async (t) => {
  const h = await host(t)
  assert.ok(h.tools.has('studio_workflow'))
  for (const name of ['tool.execute.before', 'tool.execute.after', 'session.prompt', 'session.context', 'permission.evaluate']) assert.ok(h.hooks.has(name), name)
  assert.match((await h.call({ action: 'bind', mode: 'concept' })).content, /concept/)
})
test('adapter derives worker identity from server, not forged input', async (t) => {
  const h = await host(t)
  await h.call({ action: 'bind', mode: 'development' })
  await assert.rejects(h.call({ action: 'create', card: h.card, agent: 'studio' }, coder), /primary coordinator/)
})
test('permission hook blocks concept code edits and product launches', async (t) => {
  const h = await host(t); await h.call({ action: 'bind', mode: 'concept' })
  const edit = { sessionID: owner.sessionID, agent: 'studio', action: 'edit', resources: [path.join(h.root, 'tree.js')], effect: 'allow' }
  await h.hooks.get('permission.evaluate')(edit); assert.equal(edit.effect, 'deny')
  const shell = { ...edit, action: 'shell', resources: ['godot --editor'], effect: 'allow' }
  await h.hooks.get('permission.evaluate')(shell); assert.equal(shell.effect, 'deny')
})
test('original shell guard is really invoked with the V2 working directory', async (t) => {
  const h = await host(t)
  await assert.rejects(h.hooks.get('tool.execute.before')({ tool: 'shell', input: { command: 'git add -A', workdir: h.root } }), /поимённо|назвать|файлы|add/i)
})
test('unavailable guard fails closed', async (t) => {
  const h = await host(t); fs.unlinkSync(path.join(h.root, '.opencode/studio/hooks/guard_git.py'))
  await assert.rejects(h.hooks.get('tool.execute.before')({ tool: 'shell', input: { command: 'git status' } }), /guard_git|No such file/)
})
test('context re-injects only a small continuation summary after compaction', async (t) => {
  const h = await host(t); await h.call({ action: 'bind', mode: 'development' }); await h.call({ action: 'create', card: h.card })
  const event = { agent: 'executor', sessionID: coder.sessionID, system: [] }
  h.hooks.get('session.context')(event)
  assert.match(event.system[0].text, /batch-p1/); assert.match(event.system[0].text, /ready/)
  assert.ok(event.system[0].text.length < 2500)
})
test('question answer is stored as user evidence; unrelated question does not grant acceptance', async (t) => {
  const h = await host(t); await h.call({ action: 'bind', mode: 'development' })
  await h.hooks.get('tool.execute.before')({ tool: 'question', sessionID: owner.sessionID, input: { questions: [{ question: 'Какой цвет?' }] } })
  await h.hooks.get('tool.execute.after')({ tool: 'question', sessionID: owner.sessionID, status: 'completed', result: { content: 'Синий' } })
  assert.equal(h.engine.store.read().sessions[owner.sessionID].owner_evidence.intent, null)
  await h.hooks.get('tool.execute.before')({ tool: 'question', sessionID: owner.sessionID, input: { questions: [{ question: 'Партия: что принимаете?' }] } })
  await h.hooks.get('tool.execute.after')({ tool: 'question', sessionID: owner.sessionID, status: 'completed', result: { content: 'Всё' } })
  assert.equal(h.engine.store.read().sessions[owner.sessionID].owner_evidence.intent, 'acceptance')
})
test('new session can resolve its default agent at context time', async (t) => {
  const h = await host(t); delete h.sessions.get(owner.sessionID).agent
  await h.hooks.get('session.prompt')({ sessionID: owner.sessionID, prompt: { text: 'Привет' } })
  h.hooks.get('session.context')({ sessionID: owner.sessionID, agent: 'studio', system: [] })
  assert.match((await h.call({ action: 'bind', mode: 'concept' })).content, /concept/)
})
test('Python adapter preserves Cyrillic JSON stdin', async (t) => {
  const r = repo(t); const script = path.join(r.root, 'echo.py')
  fs.writeFileSync(script, 'import json,sys\nprint(json.load(sys.stdin)["text"], end="")\n')
  const result = await runPython(script, { text: 'Русский путь и вопрос' })
  assert.equal(result.code, 0); assert.equal(result.stdout, 'Русский путь и вопрос')
})
test('context detects a worker silently inheriting the coordinator’s model', async (t) => {
  const h = await host(t)
  assert.throws(() => h.hooks.get('session.context')({ sessionID: coder.sessionID, agent: 'executor', model: { providerID: 'opencode-go', id: 'glm-5.3' }, system: [] }), /model routing mismatch/)
  assert.doesNotThrow(() => h.hooks.get('session.context')({ sessionID: coder.sessionID, agent: 'executor-any', model: { providerID: 'owner', id: 'chosen-model' }, system: [] }))
})
