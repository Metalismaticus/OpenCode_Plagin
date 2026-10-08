import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { Engine } from '../.opencode/studio/runtime/engine.mjs'
import { Store } from '../.opencode/studio/runtime/store.mjs'
import { editAllowed, shellAllowed } from '../.opencode/studio/runtime/policy.mjs'
import { runChecks } from '../.opencode/studio/runtime/checks.mjs'
import { repo, owner, coder, reviewer } from './helpers.mjs'

test('implementation → independent review → checkpoint → real verification → owner acceptance', async (t) => {
  const r = repo(t); await r.start(); await r.submit(); await r.approve(); await r.checkpoint()
  const verified = await r.call('verify'); assert.equal(verified.passed, true); assert.equal(verified.results[0].exit_code, 0)
  await assert.rejects(r.call('accept', { owner_quote: 'Всё' }), /observed/)
  r.engine.observeOwner(owner.sessionID, 'принимаю всё')
  assert.equal((await r.call('accept', { owner_quote: 'принимаю всё' })).status, 'accepted')
})
test('the concept chat cannot implement or silently become a dev chat', async (t) => {
  const r = repo(t); await r.call('bind', { mode: 'concept' })
  await assert.rejects(r.call('create', { card: r.card }), /concept chat/)
  await assert.rejects(r.call('bind', { mode: 'development' }), /separate chat/)
  assert.equal(shellAllowed(r.engine, owner, 'godot --editor'), false)
  assert.equal(shellAllowed(r.engine, owner, 'python -X utf8 tools/roadmap_check.py'), true)
  assert.equal(shellAllowed(r.engine, owner, 'git status; godot --editor'), false)
})
test('card requires player criteria and verbatim source words', async (t) => {
  const r = repo(t); await r.call('bind', { mode: 'development' })
  await assert.rejects(r.call('create', { card: { ...r.card, acceptance: [] } }), /acceptance/)
  await assert.rejects(r.call('create', { card: { ...r.card, owner_words: 'Я придумал это за владельца' } }), /verbatim/)
  await assert.rejects(r.call('create', { card: { ...r.card, sources: ['docs/missing.md'] } }), /missing task source/)
})
test('task scope cannot include dirty pre-existing work', async (t) => {
  const r = repo(t); fs.writeFileSync(path.join(r.root, 'tree.js'), 'owner work\n')
  await r.call('bind', { mode: 'development' }); await assert.rejects(r.call('create', { card: r.card }), /pre-existing/)
})
test('task id is not overwritten by a retry', async (t) => {
  const r = repo(t); await r.start(); await assert.rejects(r.call('create', { card: r.card }), /already exists/)
})
test('worker cannot promote itself to coordinator or review itself', async (t) => {
  const r = repo(t); await r.start(); await r.submit()
  await assert.rejects(r.call('review', { verdict: 'APPROVED' }, coder), /wrong task role/)
  await assert.rejects(r.call('verify', {}, coder), /primary coordinator/)
  await assert.rejects(r.call('accept', { owner_quote: 'Всё' }, reviewer), /primary coordinator/)
})
test('review approval requires both spec/quality and every criterion', async (t) => {
  const r = repo(t); await r.start(); await r.submit()
  await assert.rejects(r.call('review', { verdict: 'APPROVED', spec: 'PASS', quality: 'FAIL', criteria: ['proof'], notes: [] }, reviewer), /both spec and quality/)
  await assert.rejects(r.call('review', { verdict: 'APPROVED', spec: 'PASS', quality: 'PASS', criteria: [], notes: [] }, reviewer), /every acceptance/)
})
test('exactly three repair rounds; reviewer is fresh each round', async (t) => {
  const r = repo(t); await r.start()
  for (let round = 1; round <= 3; round++) {
    if (round > 1) await r.call('begin', {}, { ...coder, sessionID: `ses-code-${round}` })
    const worker = round > 1 ? { ...coder, sessionID: `ses-code-${round}` } : coder
    await r.call('submit', { report: r.report }, worker)
    if (round > 1) await assert.rejects(r.call('review', { verdict: 'CHANGES_REQUESTED', notes: ['Удар не работает'] }, reviewer), /fresh reviewer/)
    const result = await r.call('review', { verdict: 'CHANGES_REQUESTED', notes: ['Удар не работает'] }, { ...reviewer, sessionID: round === 1 ? reviewer.sessionID : `ses-review-${round}` })
    assert.equal(result.round, round)
    assert.equal(result.status, round === 3 ? 'failed' : 'changes_requested')
  }
  await assert.rejects(r.call('begin', {}, coder), /failed/)
})
test('disk changes after submit or review invalidate approvals', async (t) => {
  const r = repo(t); await r.start(); await r.submit()
  fs.writeFileSync(path.join(r.root, 'tree.js'), 'export const health = 8\n')
  await assert.rejects(r.approve(), /changed during review/)
})
test('out-of-scope implementation is detected before report reaches reviewer', async (t) => {
  const r = repo(t); await r.start(); fs.writeFileSync(path.join(r.root, 'other.js'), 'export const changed = true\n')
  await assert.rejects(r.submit(), /outside task/)
})
test('concurrent concept Markdown stays outside the item commit', async (t) => {
  const r = repo(t); await r.start(); fs.appendFileSync(path.join(r.root, 'docs/BATCH.md'), '\nНовая заметка владельца')
  await r.submit(); await r.approve(); await r.checkpoint()
  assert.match(r.git('status', '--porcelain'), /docs\/BATCH.md/)
})
test('unreported changed planned file is detected', async (t) => {
  const r = repo(t); r.card.files.push('other.js'); await r.start()
  fs.writeFileSync(path.join(r.root, 'other.js'), 'export const changed = true\n')
  await assert.rejects(r.submit(), /absent from report/)
})
test('failed checks cannot be replaced by claimed green exit codes', async (t) => {
  const r = repo(t); r.card.checks[0].command = `"${process.execPath}" -e "process.exit(7)"`
  await r.start(); await r.submit(); await r.approve(); await r.checkpoint()
  const result = await r.call('verify'); assert.equal(result.passed, false); assert.equal(result.results[0].exit_code, 7)
  r.engine.observeOwner(owner.sessionID, 'принимаю всё')
  await assert.rejects(r.call('accept', { owner_quote: 'принимаю всё' }), /checkpointed/)
})
test('empty checks require an honest verification limitation', async (t) => {
  const r = repo(t); r.card.checks = []
  await r.call('bind', { mode: 'development' }); await assert.rejects(r.call('create', { card: r.card }), /verification_limit/)
  r.card.verification_limit = 'Автоматического стенда пока нет'
  await r.call('create', { card: r.card })
})
test('later product changes invalidate verification; Markdown-only changes do not', async (t) => {
  const r = repo(t); await r.start(); await r.submit(); await r.approve(); await r.checkpoint(); await r.call('verify')
  fs.appendFileSync(path.join(r.root, 'docs/BATCH.md'), '\nЗаметка')
  r.engine.observeOwner(owner.sessionID, 'принимаю всё')
  fs.writeFileSync(path.join(r.root, 'other.js'), 'export const changed = true\n'); r.git('add', 'other.js'); r.git('commit', '-m', 'Other game change')
  await assert.rejects(r.call('accept', { owner_quote: 'принимаю всё' }), /changed since verification/)
})
test('checkpoint cannot include BATCH or someone else’s files', async (t) => {
  const r = repo(t); await r.start(); await r.submit(); await r.approve()
  fs.appendFileSync(path.join(r.root, 'docs/BATCH.md'), '\nПартия готова')
  r.git('add', 'tree.js', 'docs/BATCH.md'); r.git('commit', '-m', 'Item 1: reaction')
  await assert.rejects(r.call('checkpoint', { commit: r.git('rev-parse', 'HEAD') }), /out-of-scope/)
})
test('ordinary user message is not evidence of acceptance', async (t) => {
  const r = repo(t); await r.start(); await r.submit(); await r.approve(); await r.checkpoint(); await r.call('verify')
  r.engine.observeOwner(owner.sessionID, 'Я ещё не посмотрел')
  await assert.rejects(r.call('accept', { owner_quote: 'Я ещё не посмотрел' }), /explicit decision/)
})
test('a question selection survives later reason questions without a fabricated quote', async (t) => {
  const r = repo(t); await r.start(); await r.submit(); await r.approve(); await r.checkpoint(); await r.call('verify')
  r.engine.observeOwner(owner.sessionID, 'Всё', 'question', 'acceptance')
  r.engine.observeOwner(owner.sessionID, 'Ещё одна заметка', 'question')
  assert.equal((await r.call('accept', { owner_quote: 'Всё' })).status, 'accepted')
})
test('rejection stores observed owner reason and does not pretend to revert files', async (t) => {
  const r = repo(t); await r.start(); await r.submit(); await r.approve(); await r.checkpoint()
  r.engine.observeOwner(owner.sessionID, 'Нет, зарубки почти не видно', 'question')
  await assert.rejects(r.call('reject', { owner_quote: 'Нет', reason: 'Я придумал причину' }), /observed/)
  const result = await r.call('reject', { owner_quote: 'Нет', reason: 'зарубки почти не видно' })
  assert.equal(result.status, 'rejected'); assert.match(fs.readFileSync(path.join(r.root, 'tree.js'), 'utf8'), /9/)
})
test('state survives a fresh engine after context loss', async (t) => {
  const r = repo(t); await r.start(); await r.submit()
  const resumed = new Engine(r.root)
  const result = await resumed.execute({ action: 'get', id: r.card.id }, owner)
  assert.equal(result.status, 'reviewing'); assert.equal(result.round, 1); assert.match(result.next, /reviewer/)
})
test('fresh coordinator adopts interrupted task only from owner instruction', async (t) => {
  const r = repo(t); await r.start(); await r.submit()
  const fresh = { sessionID: 'ses-new-owner', agent: 'studio' }
  await r.call('bind', { mode: 'development' }, fresh)
  await assert.rejects(r.call('adopt', { owner_quote: 'Продолжи' }, fresh), /observed/)
  r.engine.observeOwner(fresh.sessionID, 'Продолжи эту партию')
  assert.equal((await r.call('adopt', { owner_quote: 'Продолжи эту партию' }, fresh)).status, 'reviewing')
})
test('worktree engine shares canonical state with the main project', async (t) => {
  const r = repo(t); const slot = path.join(r.temporary, 'slot')
  r.git('worktree', 'add', '-b', 'wave/p1', slot)
  const other = new Engine(slot)
  assert.equal(other.store.directory, r.engine.store.directory)
})
test('edits are denied to reviewer and outside an executor’s active card', async (t) => {
  const r = repo(t); await r.start()
  assert.equal(editAllowed(r.engine, coder, [path.join(r.root, 'tree.js')]), true)
  assert.equal(editAllowed(r.engine, coder, [path.join(r.root, 'other.js')]), false)
  assert.equal(editAllowed(r.engine, reviewer, [path.join(r.root, 'tree.js')]), false)
  await r.submit(); assert.equal(editAllowed(r.engine, coder, [path.join(r.root, 'tree.js')]), false)
})
test('failed state transaction cannot partially save a report', async (t) => {
  const r = repo(t); await r.start(); const before = r.engine.store.read()
  await assert.rejects(r.call('submit', { report: { ...r.report, files: ['missing.js'] } }, coder), /scope/)
  assert.deepEqual(r.engine.store.read(), before)
})
test('state lock prevents concurrent writers instead of losing task updates', async (t) => {
  const r = repo(t); await r.start(); fs.writeFileSync(path.join(r.engine.store.directory, 'workflow.lock'), 'busy')
  assert.throws(() => r.engine.store.transaction(() => {}), /busy/)
})
test('scope cannot traverse to another project', async (t) => {
  const r = repo(t); r.card.files = ['../other.js']; await r.call('bind', { mode: 'development' })
  await assert.rejects(r.call('create', { card: r.card }), /unsafe file/)
})
test('heavy checks are serialized across task verification', async (t) => {
  let finish
  const r = repo(t, { runChecks: () => new Promise((resolve) => { finish = resolve }) })
  await r.start(); await r.submit(); await r.approve(); await r.checkpoint()
  const running = r.call('verify')
  await assert.rejects(r.call('verify'), /verifying/)
  finish([{ exit_code: 0 }]); assert.equal((await running).passed, true)
})
test('check execution can be cancelled', async () => {
  const control = new AbortController(); control.abort()
  await assert.rejects(runChecks('.', [{ name: 'cancelled', command: 'echo never', timeout_ms: 1000 }], control.signal), /cancelled/)
})
test('already satisfied task has no fabricated commit, but still needs review and checks', async (t) => {
  const r = repo(t); await r.call('bind', { mode: 'development' }); await r.call('create', { card: r.card }); await r.call('begin', {}, coder)
  await r.call('submit', { report: { ...r.report, files: [], nothing_to_change: 'Уже реализовано' } }, coder); await r.approve()
  await r.call('checkpoint', { commit: r.git('rev-parse', 'HEAD') })
  assert.equal((await r.call('verify')).passed, true)
})
test('active verification cannot be recovered as if the process had died', async (t) => {
  let finish
  const r = repo(t, { runChecks: () => new Promise((resolve) => { finish = resolve }) })
  await r.start(); await r.submit(); await r.approve(); await r.checkpoint()
  const running = r.call('verify')
  await assert.rejects(r.call('recover'), /still alive/)
  finish([{ exit_code: 0 }]); await running
})
test('clean wave merge relocates review to main and requires verification there', async (t) => {
  const r = repo(t); const slot = path.join(r.temporary, 'slot')
  r.git('worktree', 'add', '-b', 'wave/p1', slot)
  await r.call('bind', { mode: 'development' }); await r.call('create', { card: r.card, worktree: slot }); await r.call('begin', {}, coder)
  fs.writeFileSync(path.join(slot, 'tree.js'), 'export const health = 9\n'); await r.submit(); await r.approve()
  r.git('-C', slot, 'add', 'tree.js'); r.git('-C', slot, 'commit', '-m', 'Item 1: reaction')
  const sha = r.git('-C', slot, 'rev-parse', 'HEAD'); await r.call('checkpoint', { commit: sha })
  r.git('merge', '--ff-only', 'wave/p1')
  await r.call('relocate', { worktree: r.root }); assert.equal((await r.call('verify')).passed, true)
})
test('a fresh id cannot reset a failed same-step review loop', async (t) => {
  const r = repo(t); await r.start()
  await assert.rejects(r.call('create', { card: { ...r.card, id: 'batch-p1-again' } }), /resetting rounds/)
})
test('an owner decision observed before review cannot accept the later result', async (t) => {
  const r = repo(t); await r.start(); r.engine.observeOwner(owner.sessionID, 'принимаю всё')
  await r.submit(); await r.approve(); await r.checkpoint(); await r.call('verify')
  await assert.rejects(r.call('accept', { owner_quote: 'принимаю всё' }), /predates/)
})
